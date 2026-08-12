"""Tests for the ``fill_missing_from_original`` decorator.

The decorator backs a keyword-only function with an "original" object: any
argument the caller leaves out is read from the attribute of the same name.
That is what lets ``copy_code_object`` replace a few fields of a code object
and inherit the rest.
"""

from argparse import Namespace

import pytest

from dearmor.code import fill_missing_from_original


def test_explicit_argument_wins():
    """A passed keyword argument is used instead of the original attribute."""

    @fill_missing_from_original
    def assert_argument(a=None):
        assert a == "new"

    assert_argument(None, a="new")


def test_missing_argument_taken_from_original():
    """An omitted argument falls back to the attribute of the original."""

    @fill_missing_from_original
    def assert_argument(a=None):
        assert a == 5

    assert_argument(Namespace(a=5))


def test_arguments_are_merged_per_name():
    """Each argument independently comes from the call or from the original."""

    @fill_missing_from_original
    def assert_arguments(a=None, b=None, c=None, d=None):
        assert a == 5
        assert b == 3
        assert c == 1
        assert d == 8

    assert_arguments(Namespace(a=5, c=1), b=3, d=8)


def test_missing_on_both_sides_raises():
    """An argument that neither side provides is an error, never a silent None."""

    @fill_missing_from_original
    def do_nothing(a=None, b=None, c=None, d=None):
        pass

    with pytest.raises(
        AttributeError
    ):  # NOTE this is the error raised from Namespace when an attribute is not found
        do_nothing(Namespace(c=1), b=3, d=8)
