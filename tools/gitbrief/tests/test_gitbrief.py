import os
import shutil
import subprocess

import pytest

import gitbrief

from conftest import g

pytestmark = pytest.mark.skipif(shutil.which("git") is None,
                                reason="git not on PATH")


def run(argv, capsys):
    code = gitbrief.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def ok(argv, capsys):
    code, out, err = run(argv, capsys)
    assert code == 0, err
    return out


def snapshot(repo):
    """Repo state fingerprint: HEAD + full porcelain status."""
    head = g(repo, "rev-parse", "--verify", "-q", "HEAD")
    status = g(repo, "status", "--porcelain=v1", "--untracked-files=all")
    return head + status


# ------------------------------------------------------------ default view

def test_default_branch_and_drift(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok([], capsys)
    assert out.splitlines()[0] == \
        "branch main → origin/main (ahead 2, behind 1)"


def test_default_status_diffstat_table(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok([], capsys)
    assert "staged (1 file, +4 -0):" in out
    assert "unstaged (2 files, +2 -1):" in out
    assert "untracked (1 file, +3 -0):" in out
    lines = [" ".join(l.split()) for l in out.splitlines()]
    assert "M a.py +4 -0" in lines         # staged row
    assert "M a.py +1 -1" in lines         # unstaged row
    assert "M b.txt +1 -0" in lines
    assert "? notes.txt +3 -0" in lines


def test_default_last_five_commits(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok([], capsys)
    tail = out[out.index("last commits:"):].splitlines()[1:]
    assert len(tail) == 5
    assert tail[0] == "  %s ahead two (Test)" % \
        g(repo, "rev-parse", "--short", "HEAD").strip()
    assert "ahead one" in tail[1]
    assert "extend history" in tail[2]
    assert "fix parser bug (Alice)" in tail[3]
    assert "start history" in tail[4]


def test_default_no_commits_repo(tmp_path, monkeypatch, capsys):
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    g(fresh, "init", "-b", "main")
    (fresh / "x.txt").write_text("hello\n")
    monkeypatch.chdir(fresh)
    out = ok([], capsys)
    assert "branch main (no upstream)" in out
    assert "untracked (1 file, +1 -0):" in out
    assert "no commits yet" in out


def test_default_budget_collapses_table_to_counts(repo, monkeypatch,
                                                  capsys):
    monkeypatch.chdir(repo)
    full_out = ok([], capsys)
    budget = gitbrief._est(full_out.splitlines()) - 5
    out = ok(["--max-tokens", str(budget)], capsys)
    assert gitbrief._est(out.splitlines()) <= budget
    assert "staged (1 file, +4 -0):" in out      # counts survive
    assert "M a.py" not in out                   # rows dropped first


# ------------------------------------------------------------------- hunks

def test_hunks_headers_with_one_context_line(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["hunks"], capsys)
    assert "a.py (2 hunks, +5 -1)" in out
    assert "b.txt (1 hunk, +1 -0)" in out
    assert "  @@" in out
    body = [l for l in out.splitlines() if l.startswith("  ")]
    context = [l for l in body if l.startswith("   ")]
    assert context, "1-context-line mode should include context lines"
    # -U1: never two consecutive context lines inside a hunk
    for prev, cur in zip(body, body[1:]):
        assert not (prev.startswith("   ") and cur.startswith("   "))


def test_hunks_file_filter(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["hunks", "b.txt"], capsys)
    assert "b.txt (1 hunk" in out
    assert "a.py" not in out


def test_hunks_budget_drops_context_then_bodies(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    full_out = ok(["hunks"], capsys)
    budget = gitbrief._est(full_out.splitlines()) - 3
    out = ok(["hunks", "--max-tokens", str(budget)], capsys)
    assert gitbrief._est(out.splitlines()) <= budget
    assert "(reduced for --max-tokens" in out
    tiny = ok(["hunks", "--max-tokens", "25"], capsys)
    assert gitbrief._est(tiny.splitlines()) <= 25
    assert "a.py (2 hunks, +5 -1)" in tiny       # counts never dropped


# -------------------------------------------------------------------- show

def test_show_matches_raw_git_diff(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["show", "b.txt"], capsys)
    raw = g(repo, "diff", "HEAD", "--no-renames", "--", "b.txt")
    assert out.replace("\r\n", "\n") == raw.replace("\r\n", "\n")


def test_show_untracked_errors(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    code, out, err = run(["show", "notes.txt"], capsys)
    assert code == 2
    assert "untracked" in err


def test_show_unchanged_file(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["show", "hist.txt"], capsys)
    assert out.strip() == "no changes in hist.txt"


# --------------------------------------------------------------------- log

def test_log_grep(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["log", "--grep", "parser"], capsys)
    lines = out.strip().splitlines()
    assert len(lines) == 1
    assert "fix parser bug (Alice)" in lines[0]


def test_log_author(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["log", "--author", "Alice"], capsys)
    lines = out.strip().splitlines()
    assert len(lines) == 1
    assert "fix parser bug" in lines[0]


def test_log_count(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    out = ok(["log", "-n", "3"], capsys)
    assert len(out.strip().splitlines()) == 3


def test_log_budget_elides_with_note(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    full_out = ok(["log", "-n", "7"], capsys)
    budget = gitbrief._est(full_out.splitlines()) - 3
    out = ok(["log", "-n", "7", "--max-tokens", str(budget)], capsys)
    assert gitbrief._est(out.splitlines()) <= budget
    assert "more commits elided" in out


# ---------------------------------------------------------------------- pr

def test_pr_commits_and_diffstat(pr_repo, monkeypatch, capsys):
    monkeypatch.chdir(pr_repo)
    out = ok(["pr", "main"], capsys)
    assert out.startswith("pr vs main (merge-base ")
    assert "commits (3):" in out
    for msg in ("rework python symbols", "add ts helper", "add data"):
        assert msg in out
    assert "diffstat (3 files," in out
    lines = [" ".join(l.split()) for l in out.splitlines()]
    mb = g(pr_repo, "merge-base", "main", "HEAD").strip()
    for stat in g(pr_repo, "diff", "--numstat", "--no-renames", mb,
                  "HEAD").splitlines():
        plus, minus, path = stat.split("\t")
        assert "%s +%s -%s" % (path, plus, minus) in lines


def test_pr_changed_symbols(pr_repo, monkeypatch, capsys):
    monkeypatch.chdir(pr_repo)
    out = ok(["pr", "main"], capsys)
    assert "changed symbols (heuristic" in out
    sym = {l.split()[0]: l.strip() for l in out.splitlines()
           if l.startswith("  a.py") or l.startswith("  web.ts")}
    assert "+gamma" in sym["a.py"]
    assert "-legacy" in sym["a.py"]
    assert "~alpha" in sym["a.py"]
    assert "beta" not in sym["a.py"]          # untouched symbol stays out
    assert "+helper" in sym["web.ts"]
    assert "(1 file not analyzed: data.csv)" in out


def test_pr_unknown_base_errors(pr_repo, monkeypatch, capsys):
    monkeypatch.chdir(pr_repo)
    code, out, err = run(["pr", "no-such-branch"], capsys)
    assert code == 2
    assert "unknown base revision" in err


def test_pr_budget_drops_symbols_then_rows(pr_repo, monkeypatch, capsys):
    monkeypatch.chdir(pr_repo)
    full_out = ok(["pr", "main"], capsys)
    budget = gitbrief._est(full_out.splitlines()) - 3
    out = ok(["pr", "main", "--max-tokens", str(budget)], capsys)
    assert gitbrief._est(out.splitlines()) <= budget
    assert "changed symbols" not in out          # symbols dropped first
    assert "diffstat (3 files," in out
    tiny = ok(["pr", "main", "--max-tokens", "30"], capsys)
    assert gitbrief._est(tiny.splitlines()) <= 30
    assert "diffstat (3 files," in tiny          # totals never dropped
    assert "commits (3):" in tiny                # counts never dropped


# --------------------------------------------------------------- read-only

def test_every_mode_is_read_only(repo, pr_repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    before = snapshot(repo)
    for argv in ([], ["hunks"], ["show", "b.txt"], ["log", "-n", "3"]):
        ok(argv, capsys)
        assert snapshot(repo) == before, "mode %r mutated state" % argv
    monkeypatch.chdir(pr_repo)
    before = snapshot(pr_repo)
    ok(["pr", "main"], capsys)
    assert snapshot(pr_repo) == before


# ------------------------------------------------------------ determinism

def test_output_is_deterministic(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert ok([], capsys) == ok([], capsys)
    assert ok(["hunks"], capsys) == ok(["hunks"], capsys)


def test_outside_repo_errors(tmp_path, monkeypatch, capsys):
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.chdir(plain)
    # The host's home dir may itself be a git repo (it is on this machine);
    # a ceiling keeps git from walking up and "finding" it, which would
    # turn this test into a multi-minute status scan of the whole home tree.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    code, out, err = run([], capsys)
    assert code == 2
    assert "git" in err


# ------------------------------------------- default token cap (ADR-006)

def test_default_max_tokens_is_on():
    assert gitbrief.DEFAULT_MAX_TOKENS > 0


def test_default_budget_caps_a_large_hunks_view(repo, monkeypatch, capsys):
    """`hunks` on a big working diff is exactly the call that floods a
    context window, and never the call anyone thinks to guard."""
    big = repo / "big_change.py"
    big.write_text("\n".join("added_%d = %d  # padding padding padding" % (i, i)
                             for i in range(3000)), encoding="utf-8")
    g(repo, "add", "big_change.py")
    out = ok(["hunks"], capsys)
    assert gitbrief._est(out.splitlines()) <= gitbrief.DEFAULT_MAX_TOKENS


def test_max_tokens_zero_restores_unbounded_output(repo, monkeypatch, capsys):
    big = repo / "big_change.py"
    big.write_text("\n".join("added_%d = %d  # padding padding padding" % (i, i)
                             for i in range(3000)), encoding="utf-8")
    g(repo, "add", "big_change.py")
    monkeypatch.chdir(repo)
    capped = ok(["hunks"], capsys)
    unbounded = ok(["hunks", "--max-tokens", "0"], capsys)
    assert len(unbounded) > len(capped)


def test_small_diff_is_untouched_by_the_default(repo, monkeypatch, capsys):
    """The default must be invisible for ordinary calls."""
    monkeypatch.chdir(repo)
    deflt = ok([], capsys)
    unbounded = ok(["--max-tokens", "0"], capsys)
    assert deflt == unbounded
