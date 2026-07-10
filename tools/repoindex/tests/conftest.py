import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FIXTURE_REPO = Path(__file__).parent / "fixtures" / "repo"


@pytest.fixture
def repo(tmp_path):
    """A private copy of the shared fixture repo (build/update write into it)."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, dest)
    return dest
