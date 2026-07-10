"""Fixture utilities."""


def parse(text):
    """Parse config text into a dict."""
    return {"raw": text}


def render_map(data):
    return str(data)


class Cache:
    """Tiny in-memory cache."""

    store = {}
