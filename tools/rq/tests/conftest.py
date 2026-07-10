import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
REPOINDEX_DIR = Path(__file__).resolve().parents[2] / "repoindex"
sys.path.insert(0, str(REPOINDEX_DIR))

FIXTURE_REPO = REPOINDEX_DIR / "tests" / "fixtures" / "repo"


@pytest.fixture(scope="session")
def indexed_repo(tmp_path_factory):
    """One shared copy of the repoindex fixture repo with a built index.

    Session-scoped: rq only reads the DB, so tests can share it. Tests that
    mutate the repo (freshness guard) make their own copy.
    """
    dest = tmp_path_factory.mktemp("rq") / "repo"
    shutil.copytree(FIXTURE_REPO, dest)
    from repoindex import cli as repoindex_cli
    assert repoindex_cli.build(str(dest)) == 0
    return dest


@pytest.fixture
def mutable_repo(tmp_path):
    """A private copy with a built index, for tests that touch files."""
    dest = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, dest)
    from repoindex import cli as repoindex_cli
    assert repoindex_cli.build(str(dest)) == 0
    return dest


@pytest.fixture
def seeded_db(tmp_path):
    """Hand-seeded index matching the repoindex schema, for plumbing unit
    tests that need shapes the fixture repo doesn't have (an inheritance
    cycle, two import cycles of different sizes, an external base class,
    a coverage-tagged file)."""
    root = tmp_path / "seeded"
    (root / ".repoindex").mkdir(parents=True)
    from repoindex import db as dbmod
    conn = dbmod.connect(str(root / ".repoindex" / "index.db"))
    dbmod.init_schema(conn)
    conn.executemany(
        "INSERT INTO files (path, language, mtime, hash) VALUES (?, ?, 0, 'x')",
        [("a.py", "python"), ("b.py", "python"), ("c.py", "python"),
         ("d.py", "python"), ("e.py", "python"), ("solo.py", "python"),
         ("test_a.py", "python")])
    conn.executemany(
        "INSERT INTO symbols (qualname, kind, file, line_start, line_end, "
        "exported) VALUES (?, ?, ?, ?, ?, ?)",
        [("a.py::Alpha", "class", "a.py", 1, 10, 1),
         ("b.py::Beta", "class", "b.py", 1, 10, 1),
         ("a.py::covered_fn", "func", "a.py", 12, 14, 1),
         ("solo.py::lonely", "func", "solo.py", 1, 2, 1)])
    # Inheritance cycle Alpha <-> Beta (renderer must not hang).
    conn.executemany(
        "INSERT INTO inherits (file, line, child, parent) VALUES (?, ?, ?, ?)",
        [("a.py", 1, "a.py::Alpha", "Beta"),
         ("b.py", 1, "b.py::Beta", "Alpha"),
         # External base: defined outside the repo, only named here.
         ("a.py", 1, "a.py::Alpha", "ExternalBase")])
    # Import cycles: 3-file a->b->c->a and 2-file d<->e.
    conn.executemany(
        "INSERT INTO imports (file, line, module, symbol, alias) "
        "VALUES (?, ?, ?, NULL, NULL)",
        [("a.py", 1, "b"), ("b.py", 1, "c"), ("c.py", 1, "a"),
         ("d.py", 1, "e"), ("e.py", 1, "d")])
    conn.execute(
        "INSERT INTO tests (test_file, target_file, source) "
        "VALUES ('test_a.py', 'a.py', 'import')")
    conn.commit()
    conn.close()
    return root
