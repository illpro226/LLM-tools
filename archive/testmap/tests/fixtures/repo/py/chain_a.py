"""Head of the import chain a -> b -> c; only chain_a has a test."""
from chain_b import func_b


def func_a():
    return func_b() + 1
