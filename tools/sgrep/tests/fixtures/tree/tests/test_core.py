from src.core import find_needle


def test_find_needle():
    assert find_needle(["a", "needle"]) == "needle"


def test_find_needle_missing():
    assert find_needle(["a"]) is None
