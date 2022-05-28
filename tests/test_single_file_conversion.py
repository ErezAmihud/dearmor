import tempfile
import marshal
import types
import os
import subprocess
from pathlib import Path
import shutil
import sys
import pytest
from dearmor.code import DUMP_DIR, code_to_bytecode, get_magic
from dearmor import dearmor_main

PY_CDC = shutil.which("pycdc")
PY_DIR = Path(__file__).parent.resolve() / "py_files"
PY_INJECTOR = Path(__file__).parent.resolve() / "PyInjector.dll"
TEMP_DIR = Path(__file__).parent.resolve() / "temp" / "build"
TESTED_FILES = [
    'simple.py',
    'functions_with_parameters.py',
    'functions_some_called.py',
    'functions_all_called.py',
    'file_with_class.py',
    ]
TESTED_FILES.append(pytest.param('call_break_before_inner.py', marks=pytest.mark.timeout(20)))

# without co_filename, co_name, co_firstlineno, co_lnotab, co_stacksize, co_flags
all_code_data = [
        'co_argcount',
        'co_posonlyargcount',
        'co_kwonlyargcount',
        'co_nlocals',
        'co_code',
        'co_consts',
        'co_names',
        'co_varnames',
        'co_freevars',
        'co_cellvars'
    ]

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as f:
        yield Path(f)

@pytest.fixture
def obfuscation_dir(temp_dir, py_file):
    p = subprocess.Popen(['pyarmor', 'obfuscate', "-O", str(temp_dir), str(PY_DIR / py_file)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.wait() != 0:
        raise ValueError(p.communicate())
    yield Path(temp_dir)


def pyc_to_code(data) -> types.CodeType:
    MAGIC_NUMBER = get_magic()
    data = data[len(MAGIC_NUMBER):] #int32 size
    if sys.version_info >= (3,7):
        data = data[4:] #int32 size
    data = data[4:] #int32 size
    if sys.version_info >= (3,2):
        data = data[4:] #int32 size
    return marshal.loads(data)


def compare_code(code1:types.CodeType, code2:types.CodeType, debug_data):
    assert type(code1) is type(code2), debug_data

    if isinstance(code1, types.CodeType):
        for k in all_code_data:
            compare_code(getattr(code1, k), getattr(code2, k), os.linesep.join([debug_data, f'checking {k}']))
    elif isinstance(code1, (list, tuple)):
        for i, n in enumerate(zip(code1, code2)):
            compare_code(n[0], n[1], os.linesep.join([debug_data, f"check item number {i} {n[0]} and {n[1]}"]))
    else:
        assert code1 == code2, debug_data

@pytest.mark.parametrize('py_file',TESTED_FILES)
def test_convert_by_bytecode(py_file, obfuscation_dir, temp_dir):
    dearmor_main(obfuscation_dir/py_file, Path('out.txt'))

    generated_by_us = open(str((temp_dir / 'dump' / 'mod.pyc').resolve()), 'rb').read()
    generated_by_us = pyc_to_code(generated_by_us)

    compiled_file = compile(open(PY_DIR/py_file, 'r').read(), "<string>", 'exec')
    compare_code(compiled_file, generated_by_us, f"start{os.linesep}")
