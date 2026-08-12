"""Payload that is executed *inside* the obfuscated process.

This module is never imported by the ``dearmor`` package. Instead
:func:`dearmor.__main__.deobfuscate_file` copies it next to the target script
as ``dearmor.txt``, and the injected ``dearmor.dll`` reads that file and runs
it with ``PyRun_SimpleString``. Because ``PyRun_SimpleString`` executes in the
``__main__`` namespace -- which is also the namespace of the obfuscated script
-- every global defined here shadows the equally named global of the target.

That shadowing is the whole trick: pyarmor emits a call to ``__armor_exit__``
at the end of every obfuscated code object, so defining our own
:func:`__armor_exit__` here hands us control once the runtime has already
decrypted the bytecode in memory.

The high level flow is::

    __armor_exit__()                  # called by the obfuscated script
      -> walk up to the obfuscated frame
      -> deobfuscate_code_object()    # recursively clean the code object
           -> deobfuscate_armor_enter() / deobfuscate_armor_call()
                -> invoke_code_object()   # force pyarmor to decrypt nested code
      -> write_pyc_file()             # dump the result into ./dump

Every name defined at module level leaks into the target's ``__main__``, so
names are kept explicit on purpose.
"""

import inspect
import marshal
import struct
import subprocess
import sys
import tempfile
import types
import typing
from functools import wraps
from pathlib import Path

# CPython opcode numbers. These are stable across the supported interpreters
# (3.6 - 3.9); newer versions renumber the opcode table and are not supported.
LOAD_GLOBAL = 116
SETUP_FINALLY = 122
EXTENDED_ARG = 144
JUMP_FORWARD = 110

# A full ``RETURN_VALUE`` instruction (opcode 0x53 = 83) with a zero argument.
# Patching an instruction with these two bytes cuts a code object short.
RETURN_VALUE_INSTRUCTION = b"S\x00"

# Every instruction is exactly one opcode byte plus one argument byte in the
# wordcode format used since Python 3.6. Arguments wider than a byte are
# prefixed with EXTENDED_ARG instructions, see :func:`read_opcode_argument`.
INSTRUCTION_SIZE = 2

# The constructor arguments of ``types.CodeType``, in the order the constructor
# expects them. Used to copy a code object field by field, see
# :func:`copy_code_object`.
CODE_OBJECT_FIELDS = [
    "co_argcount",
    "co_posonlyargcount",
    "co_kwonlyargcount",
    "co_nlocals",
    "co_stacksize",
    "co_flags",
    "co_code",
    "co_consts",
    "co_names",
    "co_varnames",
    "co_filename",
    "co_name",
    "co_firstlineno",
    "co_lnotab",
    "co_freevars",
    "co_cellvars",
]

# Positional-only parameters (and therefore ``co_posonlyargcount``) only exist
# from Python 3.8 onwards, see PEP 570.
if sys.version_info < (3, 8):
    CODE_OBJECT_FIELDS.remove("co_posonlyargcount")


def get_pyc_magic_number() -> bytes:
    """Return the four byte magic number identifying the running interpreter.

    The magic number is the first field of a ``.pyc`` header and tells a
    decompiler which bytecode version the file contains.
    """
    if sys.version_info >= (3, 4):
        from importlib.util import MAGIC_NUMBER

        return MAGIC_NUMBER
    else:
        import imp

        return imp.get_magic()


MAGIC_NUMBER = get_pyc_magic_number()

# All recovered ``.pyc`` files are written here, relative to the working
# directory of the obfuscated process (which is the directory of the target).
DUMP_DIR = Path("./dump")
DUMP_DIR.mkdir(exist_ok=True)

# ``__armor_exit__`` is called once per obfuscated code object, but only the
# outermost call is interesting -- it is the one whose frame still holds the
# fully decrypted module. This flag makes every later call a no-op.
is_dumping = False


def invoke_code_object(code_object: types.CodeType):
    """Call ``code_object`` with dummy arguments so pyarmor decrypts it.

    Nested functions of an obfuscated module are only decrypted once their
    parent actually runs. The parent is patched beforehand (see
    :func:`deobfuscate_armor_enter`) to return right after the pyarmor
    prologue, so running it decrypts the children without executing any of the
    original logic.

    The arguments are meaningless placeholders; any exception raised by the
    call is swallowed because we only care about the decryption side effect.
    """

    def code_object_host():
        """Throwaway function used as a carrier for ``code_object``."""
        pass

    if len(code_object.co_freevars) != 0:
        dump_code_object_disassembly(code_object)
    code_object_host.__code__ = code_object

    positional_argument_count = code_object.co_argcount
    if sys.version_info >= (3, 8):
        arguments = [i for i in range(code_object.co_posonlyargcount)]
        positional_argument_count -= code_object.co_posonlyargcount
    else:
        arguments = []

    # TODO the keyword-only names live at ``co_varnames[co_argcount:]``, so the
    # negative indexing below picks the wrong names (and the subtraction on the
    # next line double counts them). It works in practice only because the call
    # is allowed to fail -- fix it once there is a test that covers keyword-only
    # arguments in an obfuscated file.
    keyword_arguments = {
        code_object.co_varnames[-i]: i for i in range(code_object.co_kwonlyargcount)
    }
    arguments.extend(
        [i for i in range(positional_argument_count - code_object.co_kwonlyargcount)]
    )

    try:
        code_object_host(*arguments, **keyword_arguments)
    except:
        pass


def find_first_opcode(bytecode: bytes, opcode: int) -> int:
    """Return the offset of the first ``opcode`` instruction in ``bytecode``.

    Raises:
        ValueError: if the opcode does not appear in the bytecode at all.
    """
    for offset in range(0, len(bytecode), INSTRUCTION_SIZE):
        if bytecode[offset] == opcode:
            return offset
    raise ValueError("Could not find the opcode")


def read_opcode_argument_bytes(bytecode: bytes, opcode_offset: int) -> bytearray:
    """Collect the argument bytes of the instruction at ``opcode_offset``.

    An instruction only carries a single argument byte, so wider arguments are
    built up by the ``EXTENDED_ARG`` instructions directly preceding it, each
    contributing one more significant byte. The returned bytearray is in
    big endian order, most significant byte first.
    """
    argument_bytes = bytearray()
    argument_bytes.append(bytecode[opcode_offset + 1])

    previous_offset = opcode_offset - INSTRUCTION_SIZE
    while previous_offset >= 0 and bytecode[previous_offset] == EXTENDED_ARG:
        argument_bytes.insert(0, bytecode[previous_offset + 1])
        previous_offset -= INSTRUCTION_SIZE
    return argument_bytes


def read_opcode_argument(bytecode: bytes, opcode_offset: int) -> int:
    """Return the full argument of the instruction at ``opcode_offset``.

    See :func:`read_opcode_argument_bytes` for how ``EXTENDED_ARG`` is folded
    into the result.
    """
    return int.from_bytes(read_opcode_argument_bytes(bytecode, opcode_offset), "big")


def deobfuscate_armor_call(code_object: types.CodeType) -> types.CodeType:
    """Strip the ``__armor__`` wrapper from a code object.

    Code objects guarded by ``__armor__`` start with a ``JUMP_FORWARD`` over
    the encrypted body; the jump target is where pyarmor's own epilogue lives.
    We cut the object short right after the epilogue, run it so the runtime
    decrypts the body in place, and finally keep only the decrypted body.
    """
    jump_offset = find_first_opcode(code_object.co_code, JUMP_FORWARD)
    body_end = read_opcode_argument(code_object.co_code, jump_offset)

    # Six bytes (three instructions) past the body is the pyarmor epilogue that
    # follows it; returning there stops execution once decryption is done.
    return_offset = body_end + 3 * INSTRUCTION_SIZE
    code_object = copy_code_object(
        code_object,
        co_code=code_object.co_code[:return_offset]
        + RETURN_VALUE_INSTRUCTION
        + code_object.co_code[return_offset + INSTRUCTION_SIZE :],
    )

    invoke_code_object(code_object)

    cleaned_names = tuple(name for name in code_object.co_names if name != "__armor__")
    return copy_code_object(
        code_object,
        co_code=code_object.co_code[:body_end],
        co_names=cleaned_names,
    )


def deobfuscate_code_object(code_object):
    """Recursively remove the pyarmor scaffolding from a code object.

    Accepts any constant found in ``co_consts`` -- non code values are returned
    unchanged -- so it can be mapped over a code object's tuples directly.
    """
    if isinstance(code_object, types.CodeType):
        code_object = copy_code_object(
            code_object,
            co_names=tuple(
                deobfuscate_code_object(name) for name in code_object.co_names
            ),
            co_varnames=tuple(
                deobfuscate_code_object(name) for name in code_object.co_varnames
            ),
            co_freevars=tuple(
                deobfuscate_code_object(name) for name in code_object.co_freevars
            ),
            co_cellvars=tuple(
                deobfuscate_code_object(name) for name in code_object.co_cellvars
            ),
            co_consts=tuple(
                deobfuscate_code_object(constant) for constant in code_object.co_consts
            ),
        )

        # TODO I think there is a bug here because the prints are really weird.
        if "pytransform" in code_object.co_freevars:
            # Part of the pyarmor runtime itself (for example
            # ``check_obfuscated_script`` or ``check_mod_pytransform``), not
            # user code -- leave it exactly as it is.
            pass
        elif "__armor__" in code_object.co_names:
            # TODO I don't know when a function uses __armor__ but we should
            # find it and add tests
            code_object = deobfuscate_armor_call(code_object)

        elif "__armor_enter__" in code_object.co_names:
            code_object = deobfuscate_armor_enter(code_object)
        else:
            # Plain, never obfuscated code object.
            pass
    return code_object


def deobfuscate_armor_enter(code_object: types.CodeType) -> types.CodeType:
    """Strip the ``__armor_enter__`` / ``__armor_exit__`` wrapper.

    Such a code object looks roughly like::

        __armor_enter__()      # decrypts the body
        try:                   # SETUP_FINALLY jumping over the body
            <original code>
        finally:
            __armor_exit__()

    We first patch the ``POP_TOP`` that discards the ``__armor_enter__`` result
    into a ``RETURN_VALUE`` and run the result, which decrypts the body (and,
    recursively, any nested code objects) without executing it. What is left is
    the ``try`` block, whose size is the ``SETUP_FINALLY`` argument.
    """
    # The two bytes of the LOAD_GLOBAL instruction that pushes __armor_enter__.
    # TODO this breaks when the name index does not fit in a single byte, in
    # which case the LOAD_GLOBAL is prefixed with EXTENDED_ARG instructions.
    load_enter_function = b"".join(
        byte_value.to_bytes(1, byteorder="big")
        for byte_value in [LOAD_GLOBAL, code_object.co_names.index("__armor_enter__")]
    )
    # Skip the LOAD_GLOBAL and the CALL_FUNCTION that follows it to land on the
    # POP_TOP consuming the return value of __armor_enter__.
    pop_top_offset = (
        code_object.co_code.find(load_enter_function) + 2 * INSTRUCTION_SIZE
    )
    patched_code = (
        code_object.co_code[:pop_top_offset]
        + RETURN_VALUE_INSTRUCTION
        + code_object.co_code[pop_top_offset + INSTRUCTION_SIZE :]
    )
    code_object = copy_code_object(code_object, co_code=patched_code)

    invoke_code_object(code_object)

    cleaned_names = tuple(
        name for name in code_object.co_names if not name.startswith("__armor")
    )

    # Keep only the body of the ``try`` block: the SETUP_FINALLY argument is
    # the offset of the ``finally`` handler relative to the instruction, so the
    # body spans from just after SETUP_FINALLY up to that handler.
    try_offset = find_first_opcode(code_object.co_code, SETUP_FINALLY)
    finally_offset = try_offset + read_opcode_argument(code_object.co_code, try_offset)

    original_code = code_object.co_code[try_offset + INSTRUCTION_SIZE : finally_offset]
    # The original trailing return was part of the code we just cut away.
    # TODO this adds `return None` to everything? what?
    original_code += RETURN_VALUE_INSTRUCTION
    return copy_code_object(code_object, co_names=cleaned_names, co_code=original_code)


def dump_code_object_disassembly(code_object: types.CodeType):
    """Debug helper that disassembles a code object with ``pycdas``.

    ``dis`` cannot be used here: on some interpreter versions it raises while
    disassembling the half patched code objects we produce. Requires ``pycdas``
    (from pycdc) to be on ``PATH``.
    """
    disassembly_path = tempfile.mktemp()
    write_pyc_file(disassembly_path, code_object)
    subprocess.Popen(["pycdas", disassembly_path]).communicate()


# TODO can I import the other module to invoke it?


def __armor_exit__():
    """Entry point called by the obfuscated script -- do not rename.

    pyarmor emits a call to this name at the end of every obfuscated code
    object, and because this module is executed in the target's ``__main__``
    namespace our definition wins over the runtime's. Only the first call does
    any work; it walks up to the outermost obfuscated frame, deobfuscates its
    code object and writes it to :data:`DUMP_DIR`.
    """
    global is_dumping
    if not is_dumping:
        is_dumping = True
        frame = inspect.currentframe()
        while (
            frame.f_back.f_back != None
        ):  # NOTE the frame before None is the obfuscated one
            frame = frame.f_back
        code_object = deobfuscate_code_object(frame.f_code)

        # ``co_filename`` of a frozen module looks like ``<frozen name>``.
        dump_name = code_object.co_filename.replace("<frozen ", "").replace(">", "")
        if dump_name.endswith(".pyc"):
            pass
        elif dump_name.endswith(".py"):
            dump_name += "c"
        else:
            dump_name += ".pyc"

        write_pyc_file(DUMP_DIR / dump_name, code_object)


def _pack_uint32(value) -> bytes:
    """Convert integer to 32-bit little-endian bytes"""
    return struct.pack("<I", value)


def code_object_to_pyc_bytes(
    code_object: types.CodeType, mtime: int = 0, source_size: int = 0
) -> bytearray:
    """Serialise a code object (``PyCodeObject*``) into ``.pyc`` file content.

    The args mtime and source_size are inconsequential metadata in the .pyc
    file.
    """

    # Add the magic number that indicates the version of Python the bytecode is for
    #
    # The .pyc may not decompile if this four-byte value is wrong. Either hardcode the
    # value for the target version (eg. b'\x33\x0D\x0D\x0A' instead of MAGIC_NUMBER)
    # or see trymagicnum.py to step through different values to find a valid one.
    pyc_content = bytearray(MAGIC_NUMBER)

    # Handle extra 32-bit field in header from Python 3.7 onwards
    # See: https://www.python.org/dev/peps/pep-0552
    if sys.version_info >= (3, 7):
        # Blank bit field value to indicate traditional pyc header
        pyc_content.extend(_pack_uint32(0))

    pyc_content.extend(_pack_uint32(int(mtime)))

    # Handle extra 32-bit field for source size from Python 3.2 onwards
    # See: https://www.python.org/dev/peps/pep-3147/
    if sys.version_info >= (3, 2):
        pyc_content.extend(_pack_uint32(source_size))

    pyc_content.extend(marshal.dumps(code_object))

    return pyc_content


def fill_missing_from_original(func):
    """Let a keyword-only function fall back to an original object's attributes.

    The decorated function gains a leading positional parameter, the original
    object. Every keyword argument the caller omits is taken from the attribute
    of the same name on that object, which is what makes
    :func:`copy_code_object` a "replace these fields, keep the rest" helper.
    """
    signature = inspect.signature(func)
    parameter_names = list(signature.parameters.keys())

    @wraps(func)
    def fill_missing_wrapper(original_object, **kwargs):
        bound_arguments = signature.bind_partial(**kwargs).arguments
        for parameter_name in parameter_names:
            if parameter_name not in bound_arguments:
                bound_arguments[parameter_name] = getattr(
                    original_object, parameter_name
                )
        return func(**bound_arguments)

    # Advertise the original object in the signature of the wrapper.
    # NOTE ``Signature.replace`` returns a new signature instead of mutating in
    # place, so the added parameter is currently dropped. Only introspection is
    # affected, never the actual call.
    parameters = list(signature.parameters.values())
    parameters.insert(
        0, inspect.Parameter("original_object", inspect.Parameter.POSITIONAL_ONLY)
    )
    signature.replace(parameters=parameters)
    fill_missing_wrapper.__signature__ = signature
    return fill_missing_wrapper


def to_keyword_only_parameters(names) -> typing.List[inspect.Parameter]:
    """Build one optional keyword-only parameter per name, defaulting to None."""
    return [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=None)
        for name in names
    ]


def keyword_only_signature(names):
    """Give the decorated function a keyword-only parameter for every name.

    Used to turn a ``**kwargs`` function into one with a real, introspectable
    signature, so that :func:`fill_missing_from_original` can discover which
    attributes it needs to copy.
    """

    def decorator(func):
        signature = inspect.Signature(parameters=to_keyword_only_parameters(names))

        @wraps(func)
        def keyword_only_wrapper(**kwargs):
            bound_arguments = signature.bind(**kwargs)
            bound_arguments.apply_defaults()
            return func(**bound_arguments.kwargs)

        keyword_only_wrapper.__signature__ = signature
        return keyword_only_wrapper

    return decorator


@fill_missing_from_original
@keyword_only_signature(CODE_OBJECT_FIELDS)
def copy_code_object(**kwargs) -> types.CodeType:
    """Create a copy of a code object with some fields replaced.

    Called as ``copy_code_object(original, co_code=..., co_names=...)``: every
    field that is not passed explicitly is copied from ``original``.
    """
    constructor_arguments = [kwargs[field] for field in CODE_OBJECT_FIELDS]
    return types.CodeType(*constructor_arguments)


def write_pyc_file(
    file_path: typing.Union[str, Path], code_object: types.CodeType
) -> None:
    """Write ``code_object`` to ``file_path`` as a ``.pyc`` file."""
    with open(str(file_path), "wb") as pyc_file:
        pyc_file.write(code_object_to_pyc_bytes(code_object))
