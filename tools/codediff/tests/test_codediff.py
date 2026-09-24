import json
import os
import re
import socket
import subprocess
import sys

import pytest

from conftest import g, write

import codediff

CODEDIFF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "codediff.py")

HAS_TOMLLIB = codediff.tomllib is not None


def run(repo, *args, cwd=None):
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull,
               GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run([sys.executable, CODEDIFF, *args],
                          cwd=str(cwd or repo), capture_output=True,
                          text=True, encoding="utf-8", env=env)


def run_json(repo, *args, cwd=None):
    proc = run(repo, "--json", *args, cwd=cwd)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def est_tokens(text):
    return sum(len(l.encode("utf-8")) + 1 for l in text.splitlines()) // 4


# ------------------------------------------------------------- inputs ---

def test_worktree_default(repo):
    proc = run(repo)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.startswith("codediff: working tree vs HEAD")


def test_no_changes(tmp_path):
    from conftest import base_repo
    work = base_repo(tmp_path)
    proc = run(work)
    assert proc.returncode == 0
    assert "no changes" in proc.stdout


def test_unknown_revision_exit_2(repo):
    proc = run(repo, "no-such-ref")
    assert proc.returncode == 2
    assert "unknown revision" in proc.stderr


def test_ref_range_staged_same_model(repo):
    """Working tree vs REF, A..B, and --staged agree for equal content."""
    g(repo, "add", "-A")
    g(repo, "commit", "-m", "change")
    docs = [run_json(repo, "HEAD~1"),          # worktree vs ref
            run_json(repo, "HEAD~1..HEAD")]    # range
    g(repo, "reset", "--soft", "HEAD~1")
    docs.append(run_json(repo, "--staged"))    # index vs HEAD
    for doc in docs:
        doc.pop("target")
    assert docs[0] == docs[1] == docs[2]


def test_subdir_invocation_matches_root(repo):
    at_root = run(repo)
    in_subdir = run(repo, cwd=os.path.join(str(repo), "src"))
    assert at_root.stdout == in_subdir.stdout


# ----------------------------------------------------- classification ---

def test_signature_change_in_api(repo):
    out = run(repo).stdout
    assert "~ def login(user): → def login(user, mfa=None):" in out
    line = next(l for l in out.splitlines() if "def login" in l)
    assert line.rstrip().endswith("src/auth/core.py:4")


def test_rename_not_remove_plus_add(repo):
    out = run(repo).stdout
    assert "~ area → compute_area (renamed)" in out
    assert "- area()" not in out
    assert "+ compute_area()" not in out


def test_const_value_change(repo):
    out = run(repo).stdout
    line = next(l for l in out.splitlines() if "RETRY_COUNT" in l)
    assert "3 → 5" in line


def test_body_details_conditional_and_call(repo):
    out = run(repo).stdout
    line = next(l for l in out.splitlines()
                if l.lstrip().startswith("~ login()"))
    assert "+1 conditional" in line
    assert "+call: verify_mfa" in line


def test_default_value_change(repo):
    out = run(repo).stdout
    line = next(l for l in out.splitlines() if "fetch()" in l)
    assert "default 30 → 60" in line


def test_removed_deprecated(repo):
    out = run(repo).stdout
    assert "- validate_token() (func, public, was deprecated)" in out


# -------------------------------------------------------------- tests ---

def _add_suite(repo, n=29):
    body = "".join("def test_case_%d():\n    assert %d\n\n\n" % (i, i)
                   for i in range(n))
    write(repo, "tests/test_graph.py",
          "def _manifest():\n    return {}\n\n\n" + body)


def test_new_tests_collapse_to_counts_not_api(repo):
    """The whole point of the summary is signal ordering: 29 test names must
    not bury the one genuinely new piece of public surface."""
    _add_suite(repo)
    doc = run_json(repo)
    assert not [e for e in doc["api"] if "test_case" in e["text"]]
    assert not [e for e in doc["behavior"] if "test_case" in e["text"]]
    entry = next(e for e in doc["tests"] if e["path"] == "tests/test_graph.py")
    assert entry["text"] == "+29 tests, +1 helper"


def test_tests_section_rendered_with_its_own_heading(repo):
    _add_suite(repo)
    out = run(repo).stdout
    assert "Tests" in out
    assert "+29 tests, +1 helper" in out
    assert "test_case_0" not in out


def test_test_symbols_do_not_drive_the_behavior_delta_flag(repo):
    """A better-tested change must not read as a riskier one."""
    before = [f for f in run_json(repo)["risk_flags"]
              if "large behavior delta" in f["text"]]
    _add_suite(repo)
    after = [f for f in run_json(repo)["risk_flags"]
             if "large behavior delta" in f["text"]]
    assert before == after


def test_changed_test_body_reported_as_a_count(repo):
    write(repo, "tests/test_core.py",
          "from src.auth.core import login\n\n\n"
          "def test_login():\n    assert login('u', mfa='x')\n")
    doc = run_json(repo)
    entry = next(e for e in doc["tests"] if e["path"] == "tests/test_core.py")
    assert entry["text"] == "~1 test"


def test_mechanical_formatting_one_line(repo):
    out = run(repo).stdout
    fmt_lines = [l for l in out.splitlines() if "src/fmt.py" in l]
    assert len(fmt_lines) == 1
    assert "formatting/comment-only" in fmt_lines[0]


def test_mechanical_imports_reshuffled(repo):
    out = run(repo).stdout
    app_lines = [l for l in out.splitlines() if "src/app.py" in l]
    assert len(app_lines) == 1
    assert "imports reshuffled" in app_lines[0]


def test_js_signature_change(repo):
    doc = run_json(repo)
    js = [e for e in doc["api"] if e["path"] == "src/widget.js"]
    assert len(js) == 1
    assert "render(el) → " in js[0]["text"]
    assert "render(el, opts)" in js[0]["text"]


# --------------------------------------------------------------- risk ---

def test_sensitive_path_flag_with_reason(repo):
    out = run(repo).stdout
    line = next(l for l in out.splitlines()
                if "sensitive path: 'auth'" in l)
    assert re.search(r"src/auth/core\.py:\d+", line)


def test_public_api_flag(repo):
    out = run(repo).stdout
    assert "public API surface touched" in out


def test_no_ordinal_grade(repo):
    out = run(repo).stdout
    for grade in ("HIGH", "MEDIUM", "LOW"):
        assert grade not in out


@pytest.mark.skipif(not HAS_TOMLLIB, reason="tomllib requires Python 3.11+")
def test_keywords_configurable(repo):
    write(repo, ".codediff.toml",
          '[risk]\nkeywords = ["shapes"]\n')
    out = run(repo).stdout
    assert "sensitive path: 'shapes'" in out
    assert "sensitive path: 'auth'" not in out


def test_note_without_index(repo):
    out = run(repo).stdout
    assert "no .repoindex index" in out


def test_tests_table_stale_flag(indexed_repo):
    """auth/core.py has a covering test that did not change."""
    out = run(indexed_repo).stdout
    line = next(l for l in out.splitlines()
                if "matching tests not changed" in l)
    assert "src/auth/core.py:" in line
    assert "no known tests cover" in out  # fmt/shapes/client have none


def test_tests_changed_clears_stale_flag(indexed_repo):
    write(indexed_repo, "tests/test_core.py",
          "from src.auth.core import login\n\n\n"
          "def test_login():\n    assert login('u', mfa='x')\n")
    out = run(indexed_repo).stdout
    assert "matching tests not changed" not in out


# ------------------------------------------------------------ outputs ---

def test_every_finding_has_path_line(repo):
    out = run(repo).stdout
    findings = [l for l in out.splitlines()
                if l.startswith("  ") and "collapsed" not in l]
    assert findings
    for line in findings:
        assert re.search(r"\S+:\d+$", line.rstrip()), line


def test_json_roundtrip_mirrors_text(repo):
    doc = run_json(repo)
    text = run(repo).stdout
    for sec, title in (("api", "API changes"),
                       ("behavior", "Behavior changes"),
                       ("removed", "Removed"), ("mechanical", "Mechanical")):
        assert isinstance(doc[sec], list)
        for e in doc[sec]:
            assert set(e) == {"text", "path", "line"}
        block = text.split(title, 1)[1].split("\n\n", 1)[0]
        assert len([l for l in block.splitlines() if l.startswith("  ")]) \
            == len(doc[sec])
    assert doc["risk_flags"]


def test_max_tokens_collapses_mechanical_first(repo):
    full = run(repo).stdout
    budget = est_tokens(full) - 1
    capped = run(repo, "--max-tokens", str(budget)).stdout
    assert "(reduced for --max-tokens: mechanical collapsed to a count)" \
        in capped
    assert "Mechanical: 2 (collapsed for --max-tokens)" in capped
    assert est_tokens(capped) <= budget


def test_max_tokens_never_drops_risk(repo):
    capped = run(repo, "--max-tokens", "30").stdout
    assert "Risk flags" in capped
    assert "sensitive path: 'auth'" in capped


def test_determinism(repo):
    assert run(repo).stdout == run(repo).stdout


def test_version():
    proc = subprocess.run([sys.executable, CODEDIFF, "--version"],
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "codediff %s" % codediff.__version__


# ------------------------------------------------------------ offline ---

def test_offline_no_network(repo, monkeypatch, capsys):
    """Default path opens no sockets (in-process, socket doubles trap)."""
    def _boom(*a, **k):
        raise AssertionError("network access attempted")
    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.setattr(socket, "create_connection", _boom)
    monkeypatch.chdir(str(repo))
    assert codediff.main([]) == 0
    out = capsys.readouterr().out
    assert "Risk flags" in out


# ------------------------------------------- default token cap (ADR-007)

def test_default_max_tokens_is_on():
    assert codediff.DEFAULT_MAX_TOKENS > 0


def test_json_is_not_capped_by_the_default(repo):
    """A truncated payload is not parseable, so --json stays full."""
    data = run_json(repo)
    assert isinstance(data, dict)


# ------------------------------------------------- git discovery ceiling

def test_git_env_sets_a_ceiling_at_home(monkeypatch):
    """Without a ceiling, a run outside any project climbs to $HOME; on a
    machine whose home is itself a repo, that silently adopts it and scans
    the whole home tree -- a multi-minute hang that looks like work."""
    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    monkeypatch.delenv("CODEDIFF_NO_CEILING", raising=False)
    env = codediff._git_env()
    assert env["GIT_CEILING_DIRECTORIES"] == os.path.expanduser("~")


def test_git_env_respects_a_user_set_ceiling(monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", "/somewhere/else")
    monkeypatch.delenv("CODEDIFF_NO_CEILING", raising=False)
    assert codediff._git_env()["GIT_CEILING_DIRECTORIES"] == "/somewhere/else"


def test_git_env_escape_hatch_disables_the_ceiling(monkeypatch):
    """The one repo the ceiling excludes is a repo located exactly at
    $HOME (a dotfiles checkout); this is how you point the tool at it."""
    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    monkeypatch.setenv("CODEDIFF_NO_CEILING", "1")
    assert "GIT_CEILING_DIRECTORIES" not in codediff._git_env()


def test_repo_below_the_ceiling_is_still_found(repo, monkeypatch):
    """The ceiling stops the walk at $HOME; everything under it must still
    resolve normally from a subdirectory."""
    sub = repo / "nested" / "deeper"
    sub.mkdir(parents=True)
    monkeypatch.chdir(sub)
    root = codediff._git("rev-parse", "--show-toplevel").strip()
    assert os.path.realpath(root) == os.path.realpath(str(repo))


# --------------------------------------------------- markdown structure ---
# docs/known-issues/codediff-skips-markdown-so-doc-heavy-diffs-read-as-trivial

DOC_V1 = """\
# Spec

Intro line.

## Layout

Nine top-level entries.

## Commands

```bash
make build
```
"""


def _doc_repo(tmp_path, after, before=DOC_V1):
    from conftest import base_repo
    work = base_repo(tmp_path)
    write(work, "SPEC.md", before)
    g(work, "add", "-A")
    g(work, "commit", "-m", "add spec")
    write(work, "SPEC.md", after)
    return work


def test_markdown_body_change_lands_in_docs_not_unanalyzed(tmp_path):
    repo = _doc_repo(tmp_path, DOC_V1.replace("Nine top-level",
                                              "Thirteen top-level"))
    doc = run_json(repo)
    assert "SPEC.md" not in doc["unanalyzed"]
    texts = [e["text"] for e in doc["docs"]]
    assert any(t.startswith("~ Layout") and "body" in t for t in texts), texts


def test_markdown_fenced_code_change_is_named(tmp_path):
    repo = _doc_repo(tmp_path, DOC_V1.replace("make build", "make release"))
    texts = [e["text"] for e in run_json(repo)["docs"]]
    assert any("Commands" in t and "fenced code changed" in t
               for t in texts), texts


def test_markdown_added_and_removed_sections(tmp_path):
    after = DOC_V1.replace("## Layout\n\nNine top-level entries.\n\n",
                           "## Gotchas\n\nOne bullet.\n\n")
    texts = [e["text"] for e in run_json(_doc_repo(tmp_path, after))["docs"]]
    assert any(t.startswith("+ Gotchas") for t in texts), texts
    assert any(t.startswith("- Layout") for t in texts), texts


def test_markdown_new_document_collapses_to_one_line(tmp_path):
    """A wholly new doc is one fact, like a new test file's count."""
    from conftest import base_repo
    work = base_repo(tmp_path)
    write(work, "NEW.md", DOC_V1)
    entries = [e for e in run_json(work)["docs"] if e["path"] == "NEW.md"]
    assert len(entries) == 1, entries
    assert entries[0]["text"] == "+ new document, 3 sections"


def test_markdown_untouched_sections_are_silent(tmp_path):
    repo = _doc_repo(tmp_path, DOC_V1.replace("Nine top-level",
                                              "Thirteen top-level"))
    texts = [e["text"] for e in run_json(repo)["docs"]]
    assert not any("Commands" in t for t in texts), texts


def test_markdown_whitespace_only_change_is_silent(tmp_path):
    repo = _doc_repo(tmp_path, DOC_V1.replace("Intro line.",
                                              "Intro line.   "))
    assert [e["text"] for e in run_json(repo)["docs"]] == []


def test_markdown_findings_carry_path_line(tmp_path):
    repo = _doc_repo(tmp_path, DOC_V1.replace("Nine top-level",
                                              "Thirteen top-level"))
    for e in run_json(repo)["docs"]:
        assert e["path"] and e["line"] >= 1


def test_docs_section_rendered_with_its_own_heading(tmp_path):
    repo = _doc_repo(tmp_path, DOC_V1.replace("Nine top-level",
                                              "Thirteen top-level"))
    proc = run(repo, "--max-tokens", "0")
    assert proc.returncode == 0, proc.stderr
    assert "Doc changes" in proc.stdout


# ------------------------------------------- unanalyzed stated as a share ---

def test_unanalyzed_note_reports_share_of_files(repo):
    write(repo, "logo.bin", "\0\0\0binary\0\0\0")
    proc = run(repo, "--max-tokens", "0")
    assert re.search(r"\d+ of \d+ files.*not analyzed", proc.stdout), \
        proc.stdout
    assert "logo.bin" in proc.stdout


def test_unanalyzed_share_in_json(repo):
    write(repo, "logo.bin", "\0\0\0binary\0\0\0")
    share = run_json(repo)["unanalyzed_share"]
    assert share["files"] == 1
    assert share["total_files"] > 1
    assert 0 <= share["percent_of_changed_lines"] <= 100


def test_no_unanalyzed_note_when_everything_analyzed(repo):
    proc = run(repo, "--max-tokens", "0")
    assert "not analyzed" not in proc.stdout
    assert run_json(repo)["unanalyzed"] == []


# ------------------------------------------------ v0.4.1 review fixes

def _mini_repo(tmp_path, files):
    work = tmp_path / "mini"
    work.mkdir()
    g(work, "init", "-b", "main")
    for rel, content in files.items():
        write(work, rel, content)
    g(work, "add", "-A")
    g(work, "commit", "-m", "base")
    return work


PAINT_V1 = 'def paint(color="#fff"):\n    x = 1\n    return color\n'


def test_hash_in_a_string_default_is_not_a_comment(tmp_path):
    """Splitting on a bare `#` cut the signature at the quote; it then ran
    into the body, and a body edit was reported as a changed default."""
    work = _mini_repo(tmp_path, {"m.py": PAINT_V1})
    write(work, "m.py", PAINT_V1.replace("x = 1", "x = 2"))
    doc = run_json(work, "--no-update")
    texts = [e["text"] for e in doc["behavior"] + doc["api"]]
    assert texts == ["~ paint()  1 → 2"]
    write(work, "m.py", PAINT_V1.replace('"#fff"', '"#000"'))
    doc = run_json(work, "--no-update")
    texts = [e["text"] for e in doc["behavior"] + doc["api"]]
    assert texts == ['~ paint()  default "#fff" → "#000"']


def test_py_code_separates_comments_from_strings():
    assert codediff._py_code('def f(c="#a"):  # note') == (
        'def f(c="#a"):', 'def f(c=""):')
    assert codediff._py_code("def f(s='(', t=\"it's\"):")[1] == \
        "def f(s='', t=\"\"):"
    assert codediff._py_code(r'x = "a\"#b"  # c')[0] == r'x = "a\"#b"'


def test_bom_python_file_is_analyzed(tmp_path):
    """A BOM is U+FEFF to ast.parse: both sides failed, every symbol
    vanished, and the change summarized as nothing."""
    bom = "\ufeff"
    work = _mini_repo(tmp_path, {"b.py": bom + "def f():\n    return 1\n"})
    write(work, "b.py", bom + "def f():\n    return 2\n")
    doc = run_json(work, "--no-update")
    assert [e["text"] for e in doc["behavior"]] == ["~ f()  1 → 2"]


def test_unanalyzed_list_is_capped_on_reduced_rungs(tmp_path):
    """Every unanalyzed name was listed at every rung, so a diff full of
    assets kept the floor O(files) and the budget unreachable."""
    files = {"asset_%03d.bin" % i: "a\n" for i in range(300)}
    files["m.py"] = PAINT_V1
    work = _mini_repo(tmp_path, files)
    for i in range(300):
        write(work, "asset_%03d.bin" % i, "b\n")
    write(work, "m.py", PAINT_V1.replace("x = 1", "x = 2"))
    full = run(work, "--no-update", "--max-tokens", "0").stdout
    assert "asset_299.bin" in full                    # unbounded: all named
    proc = run(work, "--no-update", "--max-tokens", "300")
    assert proc.returncode == 0
    assert est_tokens(proc.stdout) <= 300
    assert "300 of 301 files" in proc.stdout
    assert "… (+295 more)" in proc.stdout


def test_jest_and_mocha_test_dirs_are_tests(tmp_path):
    """`__tests__/` and `test/` hold tests whatever their files are called;
    they used to be analyzed as source."""
    js = "export function t1() {\n  return 1;\n}\n"
    work = _mini_repo(tmp_path, {"src/__tests__/widget.js": js,
                                 "test/helpers.js": js})
    write(work, "src/__tests__/widget.js", js.replace("1", "2"))
    write(work, "test/helpers.js", js.replace("1", "3"))
    doc = run_json(work, "--no-update")
    assert doc["behavior"] == [] and doc["api"] == []
    assert sorted(e["path"] for e in doc["tests"]) == [
        "src/__tests__/widget.js", "test/helpers.js"]
