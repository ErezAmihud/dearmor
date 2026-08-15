import sys

import pytest

from dearmor.pyarmor8 import assemble_exception_table, parse_exception_table

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 11), reason="exception tables were added in 3.11"
)


def test_parses_a_known_table():
    # The table CPython 3.12 emits for a single ``48 to 68 -> 70 [1] lasti``.
    assert parse_exception_table(b"\x98\x0b\x23\x03") == [(48, 70, 70, 1, True)]


@pytest.mark.parametrize(
    "entries",
    [
        [],
        [(48, 70, 70, 1, True)],
        [(0, 2, 4, 0, False)],
        [(32, 122, 152, 0, False), (152, 178, 180, 1, True)],
        [(1 << 12, 1 << 13, 1 << 14, 5, True)],  # forces multi byte varints
    ],
)
def test_round_trips(entries):
    assert parse_exception_table(assemble_exception_table(entries)) == entries


def test_matches_the_interpreter():
    def sample():
        try:
            return 1 / 0
        except ZeroDivisionError:
            return "caught"
        finally:
            pass

    table = sample.__code__.co_exceptiontable
    assert assemble_exception_table(parse_exception_table(table)) == table
