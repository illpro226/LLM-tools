"""Imports foo without being named after it -- import-derived link only."""
from foo import foo


def test_foo_value():
    assert foo() == 1
