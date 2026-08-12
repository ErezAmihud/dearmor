"""End to end tests: obfuscate a file with pyarmor, then recover it again.

Each test obfuscates one of the sample files in ``py_files``, runs dearmor on
the result and asserts that the dumped code object matches what the plain
``compile`` of the same source produces.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from types import CodeType

import pytest

from dearmor import deobfuscate_file

from .utils import compare_code, pyc_to_code

PY_FILES_DIR: Path = Path(__file__).parent.resolve() / "py_files"

# pyarmor and the injection need a path the target process can reach; TEMP_PATH
# lets CI point that at a shared location instead of the system temp directory.
TEMP_DIR: Path = (
    Path(os.environ["TEMP_PATH"]).absolute()
    if "TEMP_PATH" in os.environ
    else Path(tempfile.gettempdir())
)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

TESTED_FILES = [
    "simple.py",
    "functions_with_parameters.py",
    "functions_some_called.py",
    "functions_all_called.py",
    "file_with_class.py",
    pytest.param("call_break_before_inner.py", marks=pytest.mark.timeout(20)),
]


@pytest.fixture
def temp_dir():
    """Yield a scratch directory for one obfuscate/dearmor round trip."""
    if "TEMP_PATH" not in os.environ:
        with tempfile.TemporaryDirectory() as temp_dir_path:
            yield Path(temp_dir_path)
    else:
        yield Path(tempfile.TemporaryDirectory(dir=TEMP_DIR).name)


@pytest.fixture
def obfuscated_file(temp_dir, py_file, pyarmor_flags):
    """Obfuscate ``py_file`` with pyarmor and yield the path of the result."""
    pyarmor_process = subprocess.Popen(
        [
            "pyarmor",
            "obfuscate",
            *pyarmor_flags,
            "-O",
            str(temp_dir),
            str(PY_FILES_DIR / py_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if pyarmor_process.wait() != 0:
        raise ValueError(pyarmor_process.communicate())
    yield temp_dir / py_file


@pytest.mark.parametrize(
    "pyarmor_flags",
    (
        [],
        ["--enable-suffix"],
    ),
)
@pytest.mark.parametrize("py_file", TESTED_FILES)
def test_single_file(py_file, obfuscated_file, temp_dir):
    """Dearmoring an obfuscated file reproduces the original bytecode."""
    deobfuscate_file(obfuscated_file)

    dump_path = (temp_dir / "dump" / (py_file + "c")).resolve()
    with open(str(dump_path), "rb") as dumped_pyc:
        dearmored_code: CodeType = pyc_to_code(dumped_pyc.read())

    with open(PY_FILES_DIR / py_file, "r") as original_source:
        expected_code: CodeType = compile(original_source.read(), "<string>", "exec")

    compare_code(expected_code, dearmored_code, f"start{os.linesep}")
