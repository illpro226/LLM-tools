import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
REPOINDEX_DIR = Path(__file__).resolve().parents[2] / "repoindex"
sys.path.insert(0, str(REPOINDEX_DIR))

FIXTURE_REPO = Path(__file__).parent / "fixtures" / "repo"


@pytest.fixture
def repo(tmp_path):
    """A private copy of the fixture repo with a built index."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, dest)
    from repoindex import cli as repoindex_cli
    assert repoindex_cli.build(str(dest)) == 0
    return dest
