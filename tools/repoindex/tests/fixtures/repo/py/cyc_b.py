"""Other half of the import cycle (whole-module import back to cyc_a)."""
import cyc_a


def beta():
    return 1


def gamma():
    """Calls back across the cycle; itself uncalled (dead, exported)."""
    return cyc_a.alpha()
