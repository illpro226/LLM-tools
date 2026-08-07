"""Makes py/ importable when pytest runs inside this fixture repo."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "py"))
