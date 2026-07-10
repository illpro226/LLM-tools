"""Shape hierarchy: a 3-deep inheritance chain plus an ABC implementation."""
from abc import ABC, abstractmethod


class Shape(ABC):
    """Abstract base -- the interface every shape implements."""

    @abstractmethod
    def area(self):
        ...


class Rectangle(Shape):
    """Implements Shape."""

    def __init__(self, w, h):
        self.w = w
        self.h = h

    def area(self):
        return self.w * self.h


class Square(Rectangle):
    """Inherits from Rectangle: Square -> Rectangle -> Shape."""

    def __init__(self, side):
        super().__init__(side, side)
