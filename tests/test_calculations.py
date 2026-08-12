"""Tests for reading instruction arguments out of raw bytecode."""

import pytest

from dearmor.code import (
    EXTENDED_ARG,
    SETUP_FINALLY,
    read_opcode_argument,
    read_opcode_argument_bytes,
)


@pytest.mark.parametrize(
    "bytecode,opcode_offset,expected_argument_bytes",
    [
        # [EXTENDED_ARG, 5, SETUP_FINALLY, 114]
        [b"\x90\x05zr", 2, b"\x05r"],
        # [SETUP_FINALLY, 9, EXTENDED_ARG, 5, SETUP_FINALLY, 114], read at the
        # second SETUP_FINALLY, which is extended by the EXTENDED_ARG before it
        [b"z\t\x90\x05zr", 4, b"\x05r"],
        # the same bytecode read at the first SETUP_FINALLY, which is not
        # preceded by any EXTENDED_ARG and therefore has a single argument byte
        [b"z\t\x90\x05zr", 0, b"\x09"],
        # [EXTENDED_ARG, 1, EXTENDED_ARG, 33, SETUP_FINALLY, 9], two chained
        # EXTENDED_ARGs make up a three byte argument
        [b"\x90\x01\x90!z\t", 4, b"\x01!\t"],
    ],
)
def test_read_opcode_argument_bytes(bytecode, opcode_offset, expected_argument_bytes):
    assert (
        read_opcode_argument_bytes(bytecode, opcode_offset) == expected_argument_bytes
    )


@pytest.mark.parametrize(
    "bytecode,opcode_offset,expected_argument",
    [
        # [EXTENDED_ARG, 5, SETUP_FINALLY, 114] -> 0x0572
        [b"\x90\x05zr", 2, 1394],
        [b"z\t\x90\x05zr", 4, 1394],
        # [SETUP_FINALLY, 9, ...] read at offset 0 -> 0x09
        [b"z\t\x90\x05zr", 0, 9],
        # [EXTENDED_ARG, 1, EXTENDED_ARG, 33, SETUP_FINALLY, 9] -> 0x012109
        [b"\x90\x01\x90!z\t", 4, 73993],
    ],
)
def test_read_opcode_argument(bytecode, opcode_offset, expected_argument):
    assert read_opcode_argument(bytecode, opcode_offset) == expected_argument
