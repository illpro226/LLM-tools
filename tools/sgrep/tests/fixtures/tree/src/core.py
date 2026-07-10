"""Core module fixture."""

# needle lookup helper
DEFAULT = "needle-default"


def find_needle(haystack):
    for item in haystack:
        if "needle" in item:
            return item
    return None
