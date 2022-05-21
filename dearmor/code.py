from functools import wraps
import typing
import struct
from pathlib import Path
import marshal
import sys,inspect,dis,types
import inspect

def get_magic():
    if sys.version_info >= (3,4):
        from importlib.util import MAGIC_NUMBER
        return MAGIC_NUMBER
    else:
        import imp
        return imp.get_magic()

MAGIC_NUMBER = get_magic()
DUMP_DIR = Path("./dump")
DUMP_DIR.mkdir(exist_ok=True)

started_exiting=False

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

def __armor_exit__():
    global started_exiting
    if not started_exiting:
        started_exiting = True
        frame = inspect.currentframe()
        while frame.f_back.f_back != None: # NOTE the frame before None is the obfuscated one
            frame = frame.f_back
        code = frame.f_code
        code = output_code(code)
        marshal_to_pyc(DUMP_DIR/'mod.pyc', code) # TODO change to indicative name


def _pack_uint32(val):
    """ Convert integer to 32-bit little-endian bytes """
    return struct.pack("<I", val)

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

def remove_pyarmor_code(code:types.CodeType):
    """
    removes all of pyarmor code from a given function and keep only the needed code

    The steps are:
    * remove all the pyarmor specific names in constants
    * remove all the random code that pyarmor adds at the start of the functions by finding the try-finally that wraps the whole thing
    * using the try finally find the last relevant opcode of the function
    * add RETURN_VALUE to the end of the function

    """
    # TODO exit on __armor_enter__
    exec(code)
    # remove names
    names = tuple(n for n in code.co_names if not n.startswith('__armor')) # remove the pyarmor functions
    code = copy_code_obj(code, co_names=names)
    code = copy_code_obj(code, co_flags=code.co_flags^0x22000000) # remove weird flags

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
    raw_code += chr(83).encode() # add return_value op
    raw_code += chr(0).encode() # add return_value op
    return copy_code_obj(code, co_code=raw_code)

def marshal_to_pyc(file_path:typing.Union[str, Path], code:types.CodeType):
    file_path = str(file_path)
    pyc_code = code_to_bytecode(code)
    with open(file_path, 'wb') as f:
        f.write(pyc_code)
