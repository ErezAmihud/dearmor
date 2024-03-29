import os
import sys
import types
import marshal
from dearmor.code import get_magic, code_attrs


def pyc_to_code(data) -> types.CodeType:
    MAGIC_NUMBER = get_magic()
    data = data[len(MAGIC_NUMBER) :]  # int32 size
    if sys.version_info >= (3, 7):
        data = data[4:]  # int32 size
    data = data[4:]  # int32 size
    if sys.version_info >= (3, 2):
        data = data[4:]  # int32 size
    return marshal.loads(data)


unwanted_code_attrs = [
    "co_filename",
    "co_name",
    "co_firstlineno",
    "co_lnotab",
    "co_stacksize",
    "co_flags",
]
all_code_data = list(filter(lambda x: x not in unwanted_code_attrs, code_attrs))


def compare_code(code1: types.CodeType, code2: types.CodeType, debug_data):
    assert type(code1) is type(code2), debug_data

    if isinstance(code1, types.CodeType):
        for k in all_code_data:
            compare_code(
                getattr(code1, k),
                getattr(code2, k),
                os.linesep.join([debug_data, f"checking {k}"]),
            )
    elif isinstance(code1, (list, tuple)):
        for i, n in enumerate(zip(code1, code2)):
            compare_code(
                n[0],
                n[1],
                os.linesep.join(
                    [debug_data, f"check item number {i} {n[0]} and {n[1]}"]
                ),
            )
    else:
        assert code1 == code2, debug_data
