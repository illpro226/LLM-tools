"""Covers mathutil via a direct import -- source=import test link."""
from mathutil import add


def test_add():
    assert add(2, 3) == 5
