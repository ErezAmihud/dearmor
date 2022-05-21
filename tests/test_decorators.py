from argparse import Namespace

import pytest
from ..code import orig_or_new

def test_set():
    @orig_or_new
    def inner(a=None):
        assert a == 'new'
    
    inner(None, a='new')

def test_from_attr():
    @orig_or_new
    def inner(a=None):
        assert a == 5
    
    inner(Namespace(a=5))


def test_multiple_values():
    @orig_or_new
    def inner(a=None, b=None, c=None, d=None):
        assert a == 5
        assert b == 3
        assert c == 1
        assert d == 8
    
    inner(Namespace(a=5,c=1),b=3, d=8)


def test_no_suitable_arg():
    @orig_or_new
    def inner(a=None, b=None, c=None, d=None):
        pass
    
    with pytest.raises(AttributeError): # NOTE this is the error raised from Namespace when an attribute is not found
        inner(Namespace(c=1),b=3, d=8)
