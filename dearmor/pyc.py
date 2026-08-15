"""Writing recovered code objects out as ``.pyc`` files."""

import marshal
import struct
import sys
from pathlib import Path


def get_magic():
    if sys.version_info >= (3, 4):
        from importlib.util import MAGIC_NUMBER

        return MAGIC_NUMBER
    import imp

    return imp.get_magic()


MAGIC_NUMBER = get_magic()


def _pack_uint32(value):
    """Convert integer to 32-bit little-endian bytes"""
    return struct.pack("<I", value)


def code_to_bytecode(code, mtime=0, source_size=0):
    """Serialise *code* into the byte content of a ``.pyc`` file.

    ``mtime`` and ``source_size`` are inconsequential metadata.
    """
    data = bytearray(MAGIC_NUMBER)

    # Extra 32-bit bit field from Python 3.7 onwards, see PEP 552.  Zero means
    # a traditional timestamp-based header.
    if sys.version_info >= (3, 7):
        data.extend(_pack_uint32(0))

    data.extend(_pack_uint32(int(mtime)))

    # Extra 32-bit source size field from Python 3.2 onwards, see PEP 3147.
    if sys.version_info >= (3, 2):
        data.extend(_pack_uint32(source_size))

    data.extend(marshal.dumps(code))
    return bytes(data)


def marshal_to_pyc(file_path, code):
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(code_to_bytecode(code))
    return file_path
