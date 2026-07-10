"""Sample module for xread tests."""

import math

GREETING = "hello"


# Compute the hypotenuse of a right triangle.
# Used by the query-mode tests.
def hypot(a, b):
    """Return the hypotenuse length."""
    return math.sqrt(a * a + b * b)


def _cache(func):
    """Tiny memoizing decorator."""
    seen = {}

    def wrapper(*args):
        if args not in seen:
            seen[args] = func(*args)
        return seen[args]

    return wrapper


@_cache
def slow_square(n):
    """Square a number, memoized."""
    return n * n


class Greeter:
    """Greets people in a configurable language."""

    def __init__(self, language="en"):
        self.language = language

    # The main entry point for greetings.
    @_cache
    def greet(self, name):
        """Return a greeting for name."""
        if self.language == "en":
            return "%s, %s!" % (GREETING, name)
        return "hola, %s!" % name

    async def greet_async(self, name):
        return self.greet(name)


def farewell(name):
    """Say goodbye."""
    return "bye, %s" % name
