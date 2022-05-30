import shutil
import tempfile
import os
import subprocess
from pathlib import Path
import pytest
from traitlets import ValidateHandler

from .utils import pyc_to_code, compare_code
from dearmor import dearmor_main

PY_DIR = Path(__file__).parent.resolve() / "py_files"
TEMP_DIR = Path(__file__).parent.resolve() / "temp" / "build"
TESTED_FILES = [
    'simple.py',
    'functions_with_parameters.py',
    'functions_some_called.py',
    'functions_all_called.py',
    'file_with_class.py',
    ]
TESTED_FILES.append(pytest.param('call_break_before_inner.py', marks=pytest.mark.timeout(20)))

@pytest.fixture
def temp_dir():
    a = Path(__file__).parent / 'temp'
    if a.exists():
        shutil.rmtree(str(a))
    a.mkdir(exist_ok=True)
    yield a

    #with tempfile.TemporaryDirectory() as f:
    #    yield Path(f)

@pytest.fixture
def obfuscation_file(temp_dir, py_file):    
    p = subprocess.Popen(['pyarmor', 'obfuscate', "-O", str(temp_dir), str(PY_DIR / py_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.wait() != 0:
        raise ValueError(p.communicate())
    yield temp_dir / py_file

# TODO test multiple
# TODO 

@pytest.mark.parametrize('py_file',TESTED_FILES)
def test_single_file(py_file, obfuscation_file, temp_dir):
    dearmor_main(obfuscation_file, Path('out.txt'))

    generated_by_us = open(str((temp_dir / 'dump' / (py_file+'c')).resolve()), 'rb').read()
    generated_by_us = pyc_to_code(generated_by_us)

    compiled_file = compile(open(PY_DIR/py_file, 'r').read(), "<string>", 'exec')
    compare_code(compiled_file, generated_by_us, f"start{os.linesep}")

@pytest.mark.skip("this is not ready yet")
@pytest.mark.parametrize('py_file',[str(Path('entry_script') / 'a.py')])
def test_entry_script(py_file, obfuscation_file, temp_dir):
    dearmor_main(temp_dir / os.path.basename(py_file), Path('out.txt'))

    for i in ['a.py', 'b.py']:
        generated_by_us = open(str((temp_dir / 'dump' / (i+'c')).resolve()), 'rb').read()
        generated_by_us = pyc_to_code(generated_by_us)

        compiled_file = compile(open(PY_DIR / py_file, 'r').read(), "<string>", 'exec')
        compare_code(compiled_file, generated_by_us, f"start{os.linesep}")
