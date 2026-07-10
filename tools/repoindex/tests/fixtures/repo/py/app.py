"""Wires mathutil and shapes together; hosts a call cycle and module state."""
from mathutil import add
from shapes import Rectangle, Square as Sq

counter = 0


def bump():
    """Write to the module-level counter."""
    global counter
    counter = counter + 1
    return counter


def report():
    """Read the module-level counter."""
    return counter


def ping(n):
    if n <= 0:
        return "done"
    return pong(n - 1)


def pong(n):
    if n <= 0:
        return "done"
    return ping(n - 1)


def build_shapes():
    r = Rectangle(2, 3)
    s = Sq(3)
    return add(r.area(), s.area())


def identity_shape(shape: Rectangle) -> Rectangle:
    """Type-annotated identity fn -- exercises a resolvable type-use ref."""
    return shape
