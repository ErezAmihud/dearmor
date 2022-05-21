from functools import wraps
import typing
import struct
from pathlib import Path
import shutil
import marshal
import os,sys,inspect,re,dis,json,types
import inspect

# TODO load function by calling it...
# TODO find a better way to load a function - so that it won't execute what is inside (in case of mallicious)

# TODO if the first function called exits before we generate our exit function I think everything probably will fail - we should load the function after
# TODO do it without using the dll injection method - to make it look much nicer    

def get_magic():
    if sys.version_info >= (3,4):
        from importlib.util import MAGIC_NUMBER
        return MAGIC_NUMBER
    else:
        import imp
        return imp.get_magic()

MAGIC_NUMBER = get_magic()
DUMP_DIR = Path("./dump")
if DUMP_DIR.exists():
    shutil.rmtree(str(DUMP_DIR))
DUMP_DIR.mkdir()
IGNORED_FUNCTIONS = []

def get_function_name(func):
    return f'{func.__module__}.{func.__qualname__}'

def ignore_function(func):
    IGNORED_FUNCTIONS.append(get_function_name(func))
    return func


ignore_function(get_function_name)
ignore_function(ignore_function)
if 'pyarmor_runtime' in locals(): # for testing
    ignore_function(pyarmor_runtime)
ignore_function(get_magic)

done=False

@ignore_function
def output_code(obj):
    if isinstance(obj, types.CodeType):
        obj = remove_pyarmor_code(obj)
        obj = copy_code_obj(
            obj,
            co_names=tuple(output_code(name) for name in obj.co_names),
            co_varnames=tuple(output_code(name) for name in obj.co_varnames),
            co_freevars=tuple(output_code(name) for name in obj.co_freevars),
            co_cellvars=tuple(output_code(name) for name in obj.co_cellvars),
            co_consts=tuple(output_code(name) for name in obj.co_consts)
        )

    return obj

@ignore_function
def __armor_exit__():
    global done
    if not done:
        frame = inspect.currentframe()
        while frame.f_back.f_back != None: # NOTE the frame before None is the obfuscated one
            frame = frame.f_back
        code = frame.f_code 
        code = output_code(code)
        marshal_to_pyc(DUMP_DIR/'mod.pyc', code)
    done=True


@ignore_function
def _pack_uint32(val):
    """ Convert integer to 32-bit little-endian bytes """
    return struct.pack("<I", val)

@ignore_function
def code_to_bytecode(code, mtime=0, source_size=0):
    """
    Serialise the passed code object (PyCodeObject*) to bytecode as a .pyc file
    The args mtime and source_size are inconsequential metadata in the .pyc file.
    """

    # Add the magic number that indicates the version of Python the bytecode is for
    #
    # The .pyc may not decompile if this four-byte value is wrong. Either hardcode the
    # value for the target version (eg. b'\x33\x0D\x0D\x0A' instead of MAGIC_NUMBER)
    # or see trymagicnum.py to step through different values to find a valid one.
    data = bytearray(MAGIC_NUMBER)

    # Handle extra 32-bit field in header from Python 3.7 onwards
    # See: https://www.python.org/dev/peps/pep-0552
    if sys.version_info >= (3,7):
        # Blank bit field value to indicate traditional pyc header
        data.extend(_pack_uint32(0))

    data.extend(_pack_uint32(int(mtime)))

    # Handle extra 32-bit field for source size from Python 3.2 onwards
    # See: https://www.python.org/dev/peps/pep-3147/
    if sys.version_info >= (3,2):
        data.extend(_pack_uint32(source_size))

    data.extend(marshal.dumps(code))

    return data

@ignore_function
def orig_or_new(func):
    sig = inspect.signature(func)
    kwarg_params = list(sig.parameters.keys())
    @wraps(func)
    def wrapee(orig, **kwargs):
        binding = sig.bind_partial(**kwargs)
        new_kwargs = binding.arguments
        for k in kwarg_params:
            if k not in new_kwargs:
                new_kwargs[k] = getattr(orig, k)
        return func(**new_kwargs)

    # add the original_object to the signature of the function
    orig_params = list(sig.parameters.values())
    orig_params.insert(0, inspect.Parameter("original_object", inspect.Parameter.POSITIONAL_ONLY))
    sig.replace(parameters=orig_params)
    wrapee.__signature__ = sig
    return wrapee

@ignore_function
@orig_or_new
def copy_code_obj(
    co_argcount=None,
    co_posonlyargcount=None,
    co_kwonlyargcount=None,
    co_nlocals=None,
    co_stacksize=None,
    co_flags=None,
    co_code=None,
    co_consts=None,
    co_names=None,
    co_varnames=None,
    co_filename=None,
    co_name=None,
    co_firstlineno=None,
    co_lnotab=None,
    co_freevars=None,
    co_cellvars=None
    ):
    """
    create a copy of code object with different paramters.
    If a parameter is None then the default is the previous code object values
    """
    return types.CodeType(
        co_argcount,
        co_posonlyargcount,
        co_kwonlyargcount,
        co_nlocals,
        co_stacksize,
        co_flags,
        co_code,
        co_consts,
        co_names,
        co_varnames,
        co_filename,
        co_name,
        co_firstlineno,
        co_lnotab,
        co_freevars,
        co_cellvars
    )

@ignore_function
def remove_pyarmor_code(code:types.CodeType):
    """
    removes all of pyarmor code from a given function and keep only the needed code

    The steps are:
    1. remove all the pyarmor specific names in constants
    2. remove all the random code that pyarmor adds at the start of the functions by finding the try-finally that wraps the whole thing
    3. using the try finally find the last relevant opcode of the function

    """
    # remove names
    names = tuple(n for n in code.co_names if not n.startswith('__armor')) # remove the pyarmor functions
    code = copy_code_obj(code, co_names=names)

    # remove until try except (the reason for totally removing is that dis.get_instructions raises an exception in some versions)
    raw_code = code.co_code
    try_start = raw_code.find(122)
    raw_code = raw_code[try_start:]
    code = copy_code_obj(code, co_names=names, co_code=raw_code)

    # remove the try-finally and keep only the code it contains
    itera = dis.get_instructions(code)
    try_block = next(itera)
    first_op = next(itera)
    raw_code = raw_code[first_op.offset:try_block.arg]
    return copy_code_obj(code, co_code=raw_code)

@ignore_function
def marshal_to_pyc(file_path:typing.Union[str, Path], code:types.CodeType):
    file_path = str(file_path)
    pyc_code = code_to_bytecode(code)
    with open(file_path, 'wb') as f:
        f.write(pyc_code)
