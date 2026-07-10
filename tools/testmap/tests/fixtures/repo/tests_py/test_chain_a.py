"""Imports only chain_a; reaches chain_b/chain_c transitively at runtime."""
from chain_a import func_a


def test_func_a():
    assert func_a() == 3
