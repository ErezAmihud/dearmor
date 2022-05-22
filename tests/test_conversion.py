import ast
import marshal
import tokenize
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
TEMP_DIR = Path(__file__).parent.resolve() / "temp"
TESTED_FILES = os.listdir(str(Path(__file__).parent.resolve() / "py_files"))
TESTED_FILES.remove("functions_with_parameters.py")
TESTED_FILES.remove("file_with_class.py")

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

@pytest.fixture(scope='session')
def temp_dir():
    TEMP_DIR.mkdir(exist_ok=True)
    yield TEMP_DIR
    shutil.rmtree(str(TEMP_DIR))


@pytest.fixture(scope='session')
def create_obfuscation(temp_dir):
    p = subprocess.Popen(['pyarmor', 'obfuscate', "-O", str(temp_dir), *os.listdir(str(PY_DIR))], cwd=str(PY_DIR), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.poll() != 0:
        raise ValueError(f"Something went wrong when trying to obfuscate.{os.linesep}STDOUT: {stdout}{os.linesep}STDERR: {stderr}")
    yield temp_dir


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
def test_convert_by_bytecode(py_file, create_obfuscation, temp_dir):
    file_name = str(PY_DIR/py_file)
    with open(file_name, 'rb') as f:
        expected = compile(f.read(), file_name, 'exec')
    
    DUMP_DIR.mkdir(exist_ok=True)
    with open(str(DUMP_DIR/(py_file+'c')), 'wb') as f:
        f.write(code_to_bytecode(expected))


    dearmor_main(create_obfuscation/py_file, PY_INJECTOR, Path('out.txt'))

    generated_by_us = open(str((create_obfuscation / 'dump' / 'mod.pyc').resolve()), 'rb').read()
    generated_by_us = pyc_to_code(generated_by_us)

    compare_code(expected, generated_by_us, f"start{os.linesep}")


def compare_ast(node1, node2, debug_data):
    assert type(node1) is type(node2), debug_data
    
    if isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in ('lineno', 'col_offset', 'ctx', 'end_lineno'):
                continue
            compare_ast(v, getattr(node2, k), os.linesep.join([debug_data, f'checking {k}']))
    elif isinstance(node1, list):
        for i, n in enumerate(zip(node1, node2)):
            compare_ast(n[0], n[1], os.linesep.join([debug_data, f'item number {i}']))
    else:
        assert node1 == node2, debug_data

# TODO this ast test is dependent on pycdc and the comments in the code, which I don't like
@pytest.mark.skip
@pytest.mark.parametrize('py_file',TESTED_FILES)
def test_convert_by_pycdc(py_file, create_obfuscation, temp_dir):
    dearmor_main(create_obfuscation/py_file, PY_INJECTOR, Path('out.txt'))

    p = subprocess.Popen([PY_CDC, "-i", str(temp_dir / 'dump' / 'mod.pyc'), "-o", str(temp_dir / 'dump' / 'mod.py')], cwd=str(temp_dir) , stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout, _ = p.communicate()
    if p.poll()!=0:
        raise ValueError(f"PYCDC could not parse the pyc file.{os.linesep}{stdout}")

    #subprocess.Popen([sys.executable, '-m', 'black', str(temp_dir / 'dump' / 'mod.py')]).communicate()
    with tokenize.open(str(temp_dir / 'dump' / 'mod.py')) as f:
        f.readline() # clean the comments from pycdc
        f.readline()
        f.readline()
        tree1_source = f.read()
        tree1 = ast.parse(tree1_source)
        
    with tokenize.open(str(PY_DIR / py_file)) as f:
        tree2_source = f.read()
        tree2 = ast.parse(tree2_source)
    assert tree2_source == tree1_source
    assert ast.dump(tree1) == ast.dump(tree2)
    compare_ast(tree2, tree1)
