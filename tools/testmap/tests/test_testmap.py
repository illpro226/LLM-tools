import json
import sqlite3
import subprocess

import pytest

import testmap


def connect(repo):
    return sqlite3.connect(str(repo / ".repoindex" / "index.db"))


def run_map(capsys, *argv):
    code = testmap.main(["--no-update", *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


# ------------------------------------------------------ convention layer

def test_convention_pair_python(repo, capsys):
    code, out, _ = run_map(capsys, "--root", str(repo), "py/foo.py")
    assert code == 0
    assert "tests_py/test_foo.py:1  covers py/foo.py  (convention)" in out
    assert "run: pytest" in out
    assert "tests_py/test_foo.py" in out.split("run: pytest", 1)[1]


def test_convention_pair_typescript(repo, capsys):
    # the spec file also imports ./bar, and repoindex's seeder records a
    # both-ways pair as its import link, so that is the tag shown
    code, out, _ = run_map(capsys, "--root", str(repo), "ts/bar.ts")
    assert code == 0
    assert "ts/bar.spec.ts:1  covers ts/bar.ts  (import depth 1)" in out
    assert "run: npx vitest run ts/bar.spec.ts" in out


def test_convention_pair_go(repo, capsys):
    code, out, _ = run_map(capsys, "--root", str(repo),
                           "go/mathutil/mathutil.go")
    assert code == 0
    assert ("go/mathutil/mathutil_test.go:1  covers "
            "go/mathutil/mathutil.go  (convention)") in out
    assert "run: go test ./go/mathutil" in out


# ---------------------------------------------------------- import layer

def test_direct_import_depth1(repo, capsys):
    """test_integration imports foo but is not named after it."""
    _, out, _ = run_map(capsys, "--root", str(repo), "py/foo.py")
    assert ("tests_py/test_integration.py:1  covers py/foo.py  "
            "(import depth 1)") in out


def test_two_hops_found_at_default_depth(repo, capsys):
    _, out, _ = run_map(capsys, "--root", str(repo), "py/chain_b.py")
    assert ("tests_py/test_chain_a.py:1  covers py/chain_b.py  "
            "(import depth 2)") in out


def test_two_hops_excluded_at_depth_1(repo, capsys):
    _, out, _ = run_map(capsys, "--root", str(repo), "--depth", "1",
                        "py/chain_b.py")
    assert "test_chain_a" not in out
    assert "no tests mapped" in out
    assert "fallback: pytest" in out


def test_three_hops_needs_depth_3(repo, capsys):
    _, out, _ = run_map(capsys, "--root", str(repo), "py/chain_c.py")
    assert "test_chain_a" not in out
    _, out, _ = run_map(capsys, "--root", str(repo), "--depth", "3",
                        "py/chain_c.py")
    assert ("tests_py/test_chain_a.py:1  covers py/chain_c.py  "
            "(import depth 3)") in out


def test_changed_test_file_selects_itself(repo, capsys):
    _, out, _ = run_map(capsys, "--root", str(repo),
                        "tests_py/test_foo.py")
    assert ("tests_py/test_foo.py:1  covers tests_py/test_foo.py  "
            "(changed-test)") in out
    assert "run: pytest tests_py/test_foo.py" in out


# --------------------------------------------------------- coverage layer

def _seed_coverage(repo, test_file, target):
    conn = connect(repo)
    conn.execute("INSERT INTO tests (test_file, target_file, source) "
                 "VALUES (?, ?, 'coverage')", (test_file, target))
    conn.commit()
    conn.close()


def test_coverage_preferred_over_import(repo, capsys):
    _seed_coverage(repo, "tests_py/test_chain_a.py", "py/chain_b.py")
    _, out, _ = run_map(capsys, "--root", str(repo), "py/chain_b.py")
    assert ("tests_py/test_chain_a.py:1  covers py/chain_b.py  "
            "(coverage)") in out
    assert "import depth" not in out


def test_coverage_preferred_over_convention(repo, capsys):
    _seed_coverage(repo, "tests_py/test_foo.py", "py/foo.py")
    _, out, _ = run_map(capsys, "--root", str(repo), "py/foo.py")
    assert "tests_py/test_foo.py:1  covers py/foo.py  (coverage)" in out


# ----------------------------------------------------------- record mode

def test_record_writes_coverage_rows(repo, capsys):
    pytest.importorskip("coverage")
    # a stale coverage row for a seen test file must be replaced
    _seed_coverage(repo, "tests_py/test_chain_a.py", "py/foo.py")

    code = testmap.main(["record", "--root", str(repo), "--no-update",
                         "--", "pytest", "-q"])
    assert code == 0

    conn = connect(repo)
    rows = set(conn.execute(
        "SELECT test_file, target_file FROM tests "
        "WHERE source = 'coverage'").fetchall())
    conn.close()
    assert ("tests_py/test_chain_a.py", "py/chain_a.py") in rows
    assert ("tests_py/test_chain_a.py", "py/chain_b.py") in rows
    assert ("tests_py/test_chain_a.py", "py/chain_c.py") in rows
    assert ("tests_py/test_integration.py", "py/foo.py") in rows
    assert ("tests_py/test_chain_a.py", "py/foo.py") not in rows

    # recorded rows beat the depth limit: chain_c now maps at default depth
    capsys.readouterr()
    _, out, _ = run_map(capsys, "--root", str(repo), "py/chain_c.py")
    assert ("tests_py/test_chain_a.py:1  covers py/chain_c.py  "
            "(coverage)") in out


def test_record_rejects_non_pytest(repo, capsys):
    code = testmap.main(["record", "--root", str(repo), "--no-update",
                         "--", "go", "test", "./..."])
    assert code == 2
    assert "only pytest" in capsys.readouterr().err


# ------------------------------------------------------- change detection

def _git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t",
                    "-c", "user.name=t", *args],
                   check=True, capture_output=True)


def _committed_repo(repo):
    _git(repo, "init")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    return repo


def test_detects_modified_and_untracked(repo, capsys):
    _committed_repo(repo)
    chain_b = repo / "py" / "chain_b.py"
    chain_b.write_text(chain_b.read_text() + "\n# touched\n")
    (repo / "py" / "brand_new.py").write_text("def novel():\n    return 2\n")

    changed = testmap.detect_changed(str(repo))
    assert "py/chain_b.py" in changed
    assert "py/brand_new.py" in changed

    _, out, _ = run_map(capsys, "--root", str(repo))
    assert ("tests_py/test_chain_a.py:1  covers py/chain_b.py  "
            "(import depth 2)") in out


def test_clean_tree_reports_no_changes(repo, capsys):
    _committed_repo(repo)
    code, out, _ = run_map(capsys, "--root", str(repo))
    assert code == 0
    assert "note: no changed files" in out


def test_no_git_and_no_args_fails(repo, capsys):
    code, _, err = run_map(capsys, "--root", str(repo))
    assert code == 1
    assert "cannot determine changed files" in err


def test_no_index_exits_2(tmp_path, capsys):
    code, _, err = run_map(capsys, "--root", str(tmp_path), "x.py")
    assert code == 2
    assert "no index" in err


# ------------------------------------------------------- freshness guard

def test_lookup_runs_repoindex_update_first(repo, capsys):
    (repo / "py" / "newmod.py").write_text("def fresh():\n    return 3\n")
    (repo / "tests_py" / "test_newmod.py").write_text(
        "def test_fresh():\n    assert True\n")
    code = testmap.main(["--root", str(repo), "py/newmod.py"])
    out = capsys.readouterr().out
    assert code == 0
    assert ("tests_py/test_newmod.py:1  covers py/newmod.py  "
            "(convention)") in out


# ----------------------------------------------------------------- output

def test_output_is_deterministic(repo, capsys):
    args = ("--root", str(repo), "py/foo.py", "py/chain_b.py", "ts/bar.ts",
            "go/mathutil/mathutil.go")
    _, first, _ = run_map(capsys, *args)
    _, second, _ = run_map(capsys, *args)
    assert first == second
    lines = [l for l in first.splitlines() if "covers" in l]
    assert lines == sorted(lines)


def test_max_tokens_collapses_targets_not_commands(repo, capsys):
    args = ("--root", str(repo), "--max-tokens", "40", "py/foo.py",
            "py/chain_b.py", "ts/bar.ts", "go/mathutil/mathutil.go")
    _, out, _ = run_map(capsys, *args)
    assert "more)" in out
    assert "run: " in out


def test_unmapped_indexed_file_is_noted(repo, capsys):
    _, out, _ = run_map(capsys, "--root", str(repo), "py/foo.py",
                        "py/chain_c.py")
    assert "note: no tests mapped for py/chain_c.py:1" in out
    assert "run: pytest" in out


def test_json_mirrors_text(repo, capsys):
    _, out, _ = run_map(capsys, "--root", str(repo), "--json", "py/foo.py")
    doc = json.loads(out)
    assert {"test_file": "tests_py/test_foo.py", "target_file": "py/foo.py",
            "source": "convention"} in doc["targets"]
    assert any(n.startswith("run: pytest") for n in doc["notes"])
    assert doc["omitted"] == 0


# ------------------------------------------------------------- unit bits

def test_context_to_test_file_formats():
    tests = {"tests_py/test_chain_a.py", "other/test_chain_a.py",
             "tests_py/test_foo.py"}
    f = testmap._context_to_test_file
    assert f("tests_py/test_foo.py::test_x|run", tests) == \
        "tests_py/test_foo.py"
    assert f("tests_py.test_foo.test_x", tests) == "tests_py/test_foo.py"
    assert f("test_foo.test_x", tests) == "tests_py/test_foo.py"
    # ambiguous basename with no full-path winner stays unmapped
    assert f("test_chain_a.test_y", tests) is None
    assert f("tests_py.test_chain_a.test_y", tests) == \
        "tests_py/test_chain_a.py"
    assert f("", tests) is None


# ------------------------------------------------ stderr encoding (INVARIANTS)

def test_pin_utf8_covers_stderr():
    """Error text carries the same non-ASCII punctuation as normal output
    and is read by the same agent; a cp1252 console would emit invalid
    UTF-8 bytes. stdout was pinned long before stderr was."""
    import io as _io
    import sys as _sys
    saved = _sys.stdout, _sys.stderr
    try:
        _sys.stdout = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252")
        _sys.stderr = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252")
        testmap._pin_utf8()
        assert _sys.stdout.encoding.lower().replace("-", "") == "utf8"
        assert _sys.stderr.encoding.lower().replace("-", "") == "utf8"
    finally:
        _sys.stdout, _sys.stderr = saved
