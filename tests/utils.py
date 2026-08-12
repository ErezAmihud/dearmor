"""Helpers shared by the test suite."""

import marshal
import os
import sys
import types

from dearmor.code import CODE_OBJECT_FIELDS, get_pyc_magic_number

# Sizes of the 32-bit header fields that follow the magic number in a .pyc
# file, see dearmor.code.code_object_to_pyc_bytes for how they are written.
HEADER_FIELD_SIZE = 4


def pyc_to_code(pyc_content) -> types.CodeType:
    """Parse the content of a ``.pyc`` file back into a code object.

    The header layout depends on the interpreter version, so the fields are
    skipped under the same conditions that produced them.
    """
    body = pyc_content[len(get_pyc_magic_number()) :]
    if sys.version_info >= (3, 7):
        body = body[HEADER_FIELD_SIZE:]  # bit field (PEP 552)
    body = body[HEADER_FIELD_SIZE:]  # mtime
    if sys.version_info >= (3, 2):
        body = body[HEADER_FIELD_SIZE:]  # source size (PEP 3147)
    return marshal.loads(body)


# Fields that legitimately differ between a compiled file and a dearmored one:
# the obfuscated file has a different name and line numbers, and pyarmor's
# scaffolding leaves the stack size and flags altered.
IGNORED_CODE_FIELDS = [
    "co_filename",
    "co_name",
    "co_firstlineno",
    "co_lnotab",
    "co_stacksize",
    "co_flags",
]
COMPARED_CODE_FIELDS = [
    field for field in CODE_OBJECT_FIELDS if field not in IGNORED_CODE_FIELDS
]


def compare_code(expected, actual, debug_data):
    """Assert that two code objects are equivalent, field by field.

    Nested code objects (inside ``co_consts``) and the name tuples are compared
    recursively so that a mismatch points at the exact field that differs.

    Args:
        expected: The code object -- or one of its field values -- to expect.
        actual: The value produced by dearmor.
        debug_data: Human readable trail of the fields walked so far, reported
            when an assertion fails.
    """
    assert type(expected) is type(actual), debug_data

    if isinstance(expected, types.CodeType):
        for field in COMPARED_CODE_FIELDS:
            compare_code(
                getattr(expected, field),
                getattr(actual, field),
                os.linesep.join([debug_data, f"checking {field}"]),
            )
    elif isinstance(expected, (list, tuple)):
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            compare_code(
                expected_item,
                actual_item,
                os.linesep.join(
                    [
                        debug_data,
                        f"check item number {index} {expected_item} and {actual_item}",
                    ]
                ),
            )
    else:
        assert expected == actual, debug_data
