"""Half of a deliberate import cycle: cyc_a -> cyc_b -> cyc_a."""
from cyc_b import beta


def alpha():
    return beta() + 1
