import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

collect_ignore = ["fixtures"]  # the fixture tree contains a fake test module
