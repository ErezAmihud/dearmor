import tempfile
import os
import subprocess
import typing
from types import CodeType
from pathlib import Path
import pytest

from .utils import pyc_to_code, compare_code
from dearmor import dearmor_main

PY_DIR: Path = Path(__file__).parent.resolve() / "py_files"
TEMP_DIR: Path = Path(os.environ["TEMP_PATH"]).absolute() if "TEMP_PATH" in os.environ else Path(tempfile.gettempdir())
TEMP_DIR.mkdir(parents=True, exist_ok=True)

TESTED_FILES = [
    'simple.py',
    'functions_with_parameters.py',
    'functions_some_called.py',
    'functions_all_called.py',
    'file_with_class.py',
    pytest.param('call_break_before_inner.py', marks=pytest.mark.timeout(20))
    ]

@pytest.fixture
def temp_dir():
    if "TEMP_PATH" not in os.environ:
        with tempfile.TemporaryDirectory() as f:
            yield Path(f)
    else:
        yield Path(tempfile.TemporaryDirectory(dir=TEMP_DIR).name)

    
@pytest.fixture
def obfuscation_file(temp_dir, py_file, pyarmor_flags):
    p = subprocess.Popen(['pyarmor', 'obfuscate', *pyarmor_flags, "-O", str(temp_dir), str(PY_DIR / py_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.wait() != 0:
        raise ValueError(p.communicate())
    yield temp_dir / py_file

@pytest.mark.parametrize("pyarmor_flags", (
    [],
    ["--enable-suffix"],
))
@pytest.mark.parametrize('py_file',TESTED_FILES)
def test_single_file(py_file, obfuscation_file, temp_dir):
    dearmor_main(obfuscation_file)

    generated_by_us = open(str((temp_dir / 'dump' / (py_file+'c')).resolve()), 'rb').read()
    generated_by_us: CodeType = pyc_to_code(generated_by_us)

    compiled_file: CodeType = compile(open(PY_DIR/py_file, 'r').read(), "<string>", 'exec')

    compare_code(compiled_file, generated_by_us, f"start{os.linesep}")
