"""Fixture for module-level constant extraction."""

import re

SIMPLE = "one line"

# An attached comment belongs to the binding below it.
PATTERN = re.compile(
    r"first alternative"
    r"|second alternative"
    r"|third alternative")

ANNOTATED: int = 42

LEFT, RIGHT = "l", "r"

EXTS = {".py", ".pyi"}

_PRIVATE = 1


class Holder:
    CLASS_LEVEL = "not a module binding"

    def __init__(self):
        self.attr = 1


def fn():
    LOCAL = "not a module binding"
    return LOCAL


Holder.injected = "attribute target binds no new name"
