import tempfile
import subprocess
from functools import wraps
import typing
import struct
from pathlib import Path
import marshal
import sys,inspect,types
import inspect


LOAD_GLOBAL = 116
RETURN_OPCODE = b'S\x00'
SETUP_FINALLY = 122
EXTENDED_ARG = 144
OPCODE_SIZE = 2
JUMP_FORWARD = 110
# TODO more documentation

code_attrs = [ # ordered correctly by types.CodeType type creation
        'co_argcount',
        'co_posonlyargcount',
        'co_kwonlyargcount',
        'co_nlocals',
        'co_stacksize',
        'co_flags',
        'co_code',
        'co_consts',
        'co_names',
        'co_varnames',
        'co_filename',
        'co_name',
        'co_firstlineno',
        'co_lnotab',
        'co_freevars',
        'co_cellvars'
]

if sys.version_info.major < 3 or (sys.version_info.major == 3 and sys.version_info.minor < 8):
    code_attrs.remove('co_posonlyargcount')


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

def execute_code_obj(obj:types.CodeType):    
    def a():
        pass
    if len(obj.co_freevars) != 0:
        print_func_data(obj)
    a.__code__ = obj


    number_of_regular_arguments = obj.co_argcount
    if sys.version_info.major > 3 or (sys.version_info.major == 3 and sys.version_info.minor > 7):
        args = [i for i in range(obj.co_posonlyargcount)]
        number_of_regular_arguments -= obj.co_posonlyargcount
    else:
        args = []
    
    kwargs = {obj.co_varnames[-i]:i for i in range(obj.co_kwonlyargcount)}
    args.extend([i for i in range(number_of_regular_arguments - obj.co_kwonlyargcount)])
    
    try:
        a(*args, **kwargs)
    except:
        pass

def find_first_opcode(co: bytes, op_code: int):
    for i in range(0, len(co), 2):
        if co[i] == op_code:
            return i
    raise ValueError("Could not find the opcode")


def get_arg_bytes(co: bytes, op_code_index: int) -> bytearray:
    """
    This function calculate the argument of a call while considering the EXTENDED_ARG opcodes that may come before that
    """
    result = bytearray()
    result.append(co[op_code_index+1])

    checked_opcode = op_code_index - 2
    while checked_opcode >= 0 and co[checked_opcode] == EXTENDED_ARG:
        result.insert(0, co[checked_opcode + 1])
        checked_opcode-=2
    return result

def calculate_arg(co: bytes, op_code_index: int) -> int:
    return int.from_bytes(get_arg_bytes(co, op_code_index), 'big')

def handle_under_armor(obj: types.CodeType):
    # TODO make handling EXTENDED_ARG a function
    i = find_first_opcode(obj.co_code, JUMP_FORWARD)
    jumping_arg = calculate_arg(obj.co_code, i)
    pop_index = jumping_arg + 6
    obj = copy_code_obj(obj, co_code=obj.co_code[:pop_index] + RETURN_OPCODE + obj.co_code[pop_index+2:])
    
    execute_code_obj(obj)

    new_names = tuple(n for n in obj.co_names if n!= "__armor__")
    return copy_code_obj(obj, co_code=obj.co_code[:jumping_arg], co_names=new_names)

def output_code(obj):
    if isinstance(obj, types.CodeType):
        obj = copy_code_obj(
            obj,
            co_names=tuple(output_code(name) for name in obj.co_names),
            co_varnames=tuple(output_code(name) for name in obj.co_varnames),
            co_freevars=tuple(output_code(name) for name in obj.co_freevars),
            co_cellvars=tuple(output_code(name) for name in obj.co_cellvars),
            co_consts=tuple(output_code(name) for name in obj.co_consts)
        )

        # TODO I think there is a bug here because the prints are really weird.
        if "pytransform" in obj.co_freevars:
            #  obj.co_name not in ["<lambda>", 'check_obfuscated_script', 'check_mod_pytransform']:
            pass
        elif "__armor__" in obj.co_names:
            # TODO I don't know when a function uses __armor__ but we should find it and add tests
            obj = handle_under_armor(obj)

        elif "__armor_enter__" in obj.co_names: 
            obj = handle_armor_enter(obj)
        else:
            pass
    return obj

def handle_armor_enter(obj: types.CodeType):

    load_enter_function = b''.join(i.to_bytes(1, byteorder='big') for i in [LOAD_GLOBAL, obj.co_names.index("__armor_enter__")])
    pop_top_start = obj.co_code.find(load_enter_function) + 4
    new_code = obj.co_code[:pop_top_start] + RETURN_OPCODE + obj.co_code[pop_top_start+2:] # replace the pop_top after __pyarmor_enter__ to return
    obj = copy_code_obj(obj, co_code=new_code)

    execute_code_obj(obj)
    
    names = tuple(n for n in obj.co_names if not n.startswith('__armor')) # remove the pyarmor functions
    raw_code = obj.co_code

    try_start = find_first_opcode(obj.co_code, SETUP_FINALLY)

    size = calculate_arg(obj.co_code, try_start)
    raw_code = raw_code[:try_start+size]

    raw_code = raw_code[try_start+2:]
    raw_code += RETURN_OPCODE # add return # TODO this adds return none to everything? what?
    return copy_code_obj(obj, co_names=names, co_code=raw_code)


def print_func_data(obj: types.CodeType):
    """
    A debug functions that uses cdas to print the code object
    (dis raises error in some python versions)
    """    
    path = tempfile.mktemp()
    marshal_to_pyc(path, obj)
    subprocess.Popen(['pycdas', path]).communicate()

# TODO can I import the other module to invoke it?

def __armor_exit__():
    global started_exiting
    if not started_exiting:
        started_exiting = True
        frame = inspect.currentframe()
        while frame.f_back.f_back != None: # NOTE the frame before None is the obfuscated one
            frame = frame.f_back
        code = frame.f_code
        code = output_code(code)
        filename = code.co_filename.replace("<frozen ", '').replace(">", '')
        if filename.endswith(".pyc"):
            pass
        elif filename.endswith(".py"):
            filename += 'c'
        else:
            filename += '.pyc'

        marshal_to_pyc(DUMP_DIR/filename, code)

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

def array_to_params(names_array):
    return [inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=None) for name in names_array]

def sig_from_array(names_array):
    def decor(f):
        sig = inspect.Signature(parameters=array_to_params(names_array))
        @wraps(f)
        def wrappe(**kwargs):
            bound = sig.bind(**kwargs)
            bound.apply_defaults()
            return f(**bound.kwargs)
        wrappe.__signature__ = sig
        return wrappe
    return decor

@orig_or_new
@sig_from_array(code_attrs)
def copy_code_obj(
    **kwargs
    ):
    """
    create a copy of code object with different paramters.
    If a parameter is None then the default is the previous code object values
    """
    args = [kwargs[name] for name in code_attrs]
    return types.CodeType(
        *args
    )


def marshal_to_pyc(file_path:typing.Union[str, Path], code:types.CodeType):
    file_path = str(file_path)
    pyc_code = code_to_bytecode(code)
    with open(file_path, 'wb') as f:
        f.write(pyc_code)
