import pytest
from dearmor.code import calculate_arg, get_arg_bytes, EXTENDED_ARG, SETUP_FINALLY


@pytest.mark.parametrize(
    "code_bytes,opcode_index,out",
    [
        [b"\x90\x05zr", 2, b"\x05r"],  # [EXTENDED_ARG, 5, SETUP_FINALLY, 114]
        [b"z\t\x90\x05zr", 4, b"\x05r"],
        [
            b"z\t\x90\x05zr",
            0,
            b"\x09",
        ],  # [SETUP_FINALLY, 9, EXTENDED_ARG, 5, SETUP_FINALLY, 114]
        [
            b"\x90\x01\x90!z\t",
            4,
            b"\x01!\t",
        ],  # [EXTENDED_ARG, 1, EXTENDED_ARG, 5, SETUP_FINALLY, 9]
    ],
)
def test_get_arg(code_bytes, opcode_index, out):
    assert get_arg_bytes(code_bytes, opcode_index) == out


@pytest.mark.parametrize(
    "code_bytes,opcode_index,out",
    [
        [b"\x90\x05zr", 2, 1394],  # [EXTENDED_ARG, 5, SETUP_FINALLY, 114]
        [b"z\t\x90\x05zr", 4, 1394],
        [
            b"z\t\x90\x05zr",
            0,
            9,
        ],  # [SETUP_FINALLY, 9, EXTENDED_ARG, 5, SETUP_FINALLY, 114]
        [
            b"\x90\x01\x90!z\t",
            4,
            73993,
        ],  # [EXTENDED_ARG, 1, EXTENDED_ARG, 5, SETUP_FINALLY, 9]
    ],
)
def test_calculate_arg(code_bytes, opcode_index, out):
    assert calculate_arg(code_bytes, opcode_index) == out
