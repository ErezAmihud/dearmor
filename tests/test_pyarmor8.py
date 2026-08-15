"""End to end tests for the PyArmor 8/9 backend.

Each sample script is obfuscated with the installed PyArmor, deobfuscated, and
then the recovered module is executed and compared against what the original
source produces.
"""

import marshal
import subprocess
import sys
import types
from pathlib import Path

import pytest

from dearmor import dearmor_pyarmor8, detect_backend
from dearmor.__main__ import LEGACY, PYARMOR8
from dearmor.pyc import MAGIC_NUMBER

PY_DIR: Path = Path(__file__).parent.resolve() / "py_files"

TESTED_FILES = [
    "simple.py",
    "functions_with_parameters.py",
    "functions_some_called.py",
    "functions_all_called.py",
    "file_with_class.py",
    "call_break_before_inner.py",
]

pytestmark = pytest.mark.skipif(
    subprocess.call(
        [sys.executable, "-m", "pyarmor.cli", "--version"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    != 0,
    reason="needs PyArmor 8 or newer",
)


@pytest.fixture
def obfuscated(tmp_path, py_file):
    output = tmp_path / "obfuscated"
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pyarmor.cli",
            "gen",
            "-O",
            str(output),
            str(PY_DIR / py_file),
        ],
        stdout=subprocess.DEVNULL,
    )
    return output / py_file


def load_pyc(path: Path) -> types.CodeType:
    data = path.read_bytes()[len(MAGIC_NUMBER) :]
    data = data[4:] if sys.version_info >= (3, 7) else data  # PEP 552 bit field
    data = data[4:]  # mtime
    data = data[4:] if sys.version_info >= (3, 2) else data  # source size
    return marshal.loads(data)


def summarize(value):
    """A comparable description of a value defined by a module.

    The recovered module is a different object graph than the original one, so
    classes and instances cannot be compared directly.
    """
    if isinstance(value, types.ModuleType):
        return "module", value.__name__
    if isinstance(value, types.FunctionType):
        code = value.__code__
        return "function", code.co_name, code.co_argcount, code.co_varnames
    if isinstance(value, type):
        return "class", value.__name__, sorted(vars(value))
    if hasattr(value, "__dict__"):
        return "instance", sorted(vars(value).items())
    return "value", value


def run(code, name):
    namespace = {"__name__": name}
    exec(code, namespace)
    return {
        key: summarize(value)
        for key, value in namespace.items()
        if not key.startswith("__")
    }


@pytest.mark.parametrize("py_file", TESTED_FILES)
def test_recovers_the_original_module(py_file, obfuscated, tmp_path):
    output = dearmor_pyarmor8(obfuscated, tmp_path / "dump", timeout=60)
    recovered = load_pyc(output / (Path(py_file).stem + ".pyc"))

    original = compile((PY_DIR / py_file).read_text(), py_file, "exec")
    assert run(recovered, "recovered") == run(original, "recovered")


@pytest.mark.parametrize("py_file", ["functions_all_called.py"])
def test_detects_the_backend(obfuscated):
    assert detect_backend(obfuscated) == PYARMOR8


def test_detects_legacy_scripts(tmp_path):
    script = tmp_path / "legacy.py"
    script.write_text(
        "from pytransform import pyarmor_runtime\npyarmor_runtime()\n"
        "__pyarmor__(__name__, __file__, b'\\x01')\n"
    )
    assert detect_backend(script) == LEGACY


def test_detects_nothing_in_an_unreadable_file(tmp_path):
    assert detect_backend(tmp_path / "missing.py") == LEGACY
