import json
import os
import re
import shutil
import subprocess
import sys

import pytest

import sgrep

FIX = os.path.join(os.path.dirname(__file__), "fixtures")
TREE = os.path.join(FIX, "tree")
SGREP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sgrep.py")

RG = shutil.which("rg") or (
    os.environ.get("SGREP_RG")
    if os.path.exists(os.environ.get("SGREP_RG", "")) else None)

needs_rg = pytest.mark.skipif(RG is None, reason="ripgrep not installed")


def canned(name):
    with open(os.path.join(FIX, "rg-output", name), encoding="utf-8") as fh:
        return sgrep.parse_stream(fh)


def by_suffix(files, suffix):
    return next(p for p in files if p.replace("\\", "/").endswith(suffix))


def run(argv, capsys):
    code = sgrep.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def rg_args(*extra):
    return ["--rg", RG, "needle", TREE, *extra]


DEFAULTS = sgrep.load_config.__defaults__  # none; convenience below


def default_conf():
    return dict(sgrep.DEFAULT_WEIGHTS), {"generated": [], "tests": []}


# ----------------------------------------------------------------- parsing

def test_parse_canned_stream_counts_and_texts():
    files = canned("basic.jsonl")
    counts = {p.replace("\\", "/").split("tree/")[1]: files[p]["count"]
              for p in files}
    assert counts == {"src/auth.py": 9, "src/core.py": 4,
                      "tests/test_core.py": 5, "generated/bundle.min.js": 12}
    auth = files[by_suffix(files, "src/auth.py")]
    assert auth["matches"][0] == (4, "def setup_needle():")


def test_parse_is_incremental():
    """The parser accepts any line iterable — no full-buffer requirement."""
    path = os.path.join(FIX, "rg-output", "basic.jsonl")

    def one_at_a_time():
        with open(path, encoding="utf-8") as fh:
            yield from fh

    files = sgrep.parse_stream(one_at_a_time())
    assert len(files) == 4


def test_parse_normalizes_backslash_paths():
    """rg echoes the separator it was given; sgrep must not.

    A directory search on Windows yields `dir\\file.py` while naming the
    same file yields `dir/file.py`, so one run could print both forms for
    one file. Paths are reference values (INVARIANTS: every claim line is
    followable with xread) and must compare equal across calls.
    """
    events = [
        json.dumps({"type": "match", "data": {
            "path": {"text": r"src\auth.py"},
            "lines": {"text": "needle\n"}, "line_number": 4}}),
        json.dumps({"type": "match", "data": {
            "path": {"text": "src/auth.py"},
            "lines": {"text": "needle\n"}, "line_number": 9}}),
    ]
    files = sgrep.parse_stream(events)
    assert list(files) == ["src/auth.py"]
    assert files["src/auth.py"]["count"] == 2


def test_parse_context_events():
    files = canned("context.jsonl")
    entry = files[by_suffix(files, "src/core.py")]
    assert entry["count"] == 4
    assert entry["contexts"]  # -C 1 produced context lines


# ------------------------------------------------------ dedupe and select

def test_over_five_matches_shows_three_distinct_plus_note():
    files = canned("basic.jsonl")
    auth = files[by_suffix(files, "src/auth.py")]
    shown, hidden = sgrep.select_matches(auth, cap=None)
    assert len(shown) == 3
    assert hidden == 6
    texts = [t for _, t in shown]
    # one representative per normalized cluster — not three needle_calls
    assert sum("needle_call" in t for t in texts) == 1
    assert "def setup_needle():" in texts


def test_five_or_fewer_shows_all():
    files = canned("basic.jsonl")
    core = files[by_suffix(files, "src/core.py")]
    shown, hidden = sgrep.select_matches(core, cap=None)
    assert len(shown) == 4
    assert hidden == 0


def test_no_collapse_shows_every_match_in_line_order():
    """"Edit each of these" needs the full list, not a representative."""
    files = canned("basic.jsonl")
    auth = files[by_suffix(files, "src/auth.py")]
    shown, hidden = sgrep.select_matches(auth, cap=None, no_collapse=True)
    assert len(shown) == auth["count"] == 9
    assert hidden == 0
    assert [line for line, _ in shown] == sorted(line for line, _ in shown)
    assert sum("needle_call" in t for _, t in shown) == 7  # collapsed to 1


def test_no_collapse_stays_bounded_by_max_tokens():
    """--no-collapse widens the default, it does not defeat the budget."""
    files = canned("basic.jsonl")
    ranked = sgrep.rank(files, *default_conf())
    lines = sgrep.apply_budget(ranked, files,
                               _Args(max_tokens=60, no_collapse=True))
    assert sgrep._tokens_of(lines) <= 60
    assert any("--no-collapse capped at" in ln for ln in lines)


def test_normalize_clusters_digit_variants():
    assert sgrep.normalize("  needle_call(12)") == sgrep.normalize(
        "needle_call(99)   ")
    assert sgrep.normalize("alpha") != sgrep.normalize("beta")


# ----------------------------------------------------------------- ranking

def test_rank_prefers_src_over_tests_over_generated():
    files = canned("basic.jsonl")
    weights, extra = default_conf()
    ranked = [p.replace("\\", "/").split("tree/")[1]
              for p in sgrep.rank(files, weights, extra)]
    assert ranked == ["src/auth.py", "src/core.py", "tests/test_core.py",
                      "generated/bundle.min.js"]


def test_rank_config_override_changes_order(tmp_path):
    conf = tmp_path / "sgrep.toml"
    conf.write_text("[weights]\ntests = 3.0\n")
    weights, extra = sgrep.load_config(str(conf))
    files = canned("basic.jsonl")
    ranked = sgrep.rank(files, weights, extra)
    assert ranked[0].replace("\\", "/").endswith("tests/test_core.py")


def test_config_extra_class_patterns(tmp_path):
    conf = tmp_path / "sgrep.toml"
    conf.write_text('[classes]\ngenerated = ["*/auth.py"]\n')
    weights, extra = sgrep.load_config(str(conf))
    assert sgrep.classify("tree/src/auth.py", extra) == "generated"


def test_config_rejects_unknown_class(tmp_path):
    conf = tmp_path / "sgrep.toml"
    conf.write_text("[weights]\nbogus = 9.0\n")
    with pytest.raises(sgrep.SgrepError):
        sgrep.load_config(str(conf))


def test_classify_builtins():
    _, extra = default_conf()
    assert sgrep.classify("src/app/main.py", extra) == "src"
    assert sgrep.classify("tests/test_main.py", extra) == "tests"
    assert sgrep.classify("src/app/main.spec.ts", extra) == "tests"
    assert sgrep.classify("node_modules/x/index.js", extra) == "generated"
    assert sgrep.classify("assets/app.min.js", extra) == "generated"


# --------------------------------------------------------------- rendering

def _render(files, **kw):
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    defaults = dict(ctx_radius=0, cap=None, nfiles=len(ranked),
                    counts_only=False, files_only=False)
    defaults.update(kw)
    return sgrep.render(ranked, files, **defaults)


def test_render_grouped_with_headers_and_note():
    files = canned("basic.jsonl")
    lines = _render(files)
    auth = by_suffix(files, "src/auth.py")
    assert lines[0] == "== %s (9 matches) ==" % auth
    assert "%s:4: def setup_needle():" % auth in lines
    assert "(+6 more similar)" in lines
    joined = "\n".join(lines)
    assert joined.index("auth.py") < joined.index("core.py")


def test_render_files_only_and_counts_only():
    files = canned("basic.jsonl")
    fo = _render(files, files_only=True)
    assert len(fo) == 4
    assert fo[0].replace("\\", "/").endswith("src/auth.py")
    co = _render(files, counts_only=True)
    assert len(co) == 5
    assert co[0].split()[0] == "9"
    assert co[-1] == "total: 30 matches in 4 files"


# ------------------------------------------------------------- token cap

class _Args:
    def __init__(self, **kw):
        self.context = kw.get("context", 0)
        self.max_tokens = kw.get("max_tokens", 0)
        self.counts_only = False
        self.files_only = False
        self.no_collapse = kw.get("no_collapse", False)


def test_budget_reduces_context_first():
    files = canned("context.jsonl")
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    full = sgrep.apply_budget(ranked, files, _Args(context=1))
    assert any(":  " not in l and l.rstrip().endswith("-") or "- " in l
               for l in full if ":" in l)  # context lines present (dash form)
    n_ctx_full = sum(1 for l in full if "- " in l and ": " not in l)
    assert n_ctx_full > 0
    tight = sgrep.apply_budget(ranked, files,
                               _Args(context=1,
                                     max_tokens=sgrep._tokens_of(full) - 1))
    n_ctx_tight = sum(1 for l in tight if "- " in l and ": " not in l)
    assert n_ctx_tight < n_ctx_full          # context went first
    assert any(": " in l for l in tight)      # matches survived


def test_budget_then_matches_per_file_then_files():
    files = canned("basic.jsonl")
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    full = sgrep.apply_budget(ranked, files, _Args())
    budgets = []
    b = sgrep._tokens_of(full)
    while b > 32:  # below ~32 tokens no output can satisfy the budget
        b = b * 2 // 3
        budgets.append(max(b, 32))
    prev_headers = len(ranked) + 1
    for b in budgets:
        lines = sgrep.apply_budget(ranked, files, _Args(max_tokens=b))
        assert sgrep._tokens_of(lines) <= b
        headers = sum(1 for l in lines if l.startswith("== "))
        assert headers <= prev_headers or headers == 0
        prev_headers = max(headers, 1)
    # at a tiny budget output converges toward counts, floored at two lines
    tiny = sgrep.apply_budget(ranked, files, _Args(max_tokens=20))
    assert len(tiny) == 2
    assert "elided" in tiny[-1]


def test_budget_dropped_files_note():
    files = canned("basic.jsonl")
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    lines = sgrep.render(ranked, files, 0, None, 2, False, False)
    assert lines[-1] == "(+2 more files with 17 matches)"


# --------------------------------------------------------------- CLI / rg

def test_missing_ripgrep_is_clear_error(capsys):
    code, out, err = run(["--rg", "no-such-rg-binary-xyz", "pattern"], capsys)
    assert code == 2
    assert out == ""
    assert "ripgrep not found" in err and "install" in err


@needs_rg
def test_cli_end_to_end_ranked_digest(capsys):
    code, out, _ = run(rg_args(), capsys)
    assert code == 0
    lines = out.splitlines()
    assert lines[0].startswith("== ") and "auth.py (9 matches)" in lines[0]
    assert "(+6 more similar)" in out
    joined = out.replace("\\", "/")
    assert joined.index("src/auth.py") < joined.index("src/core.py")
    assert joined.index("tests/test_core.py") < joined.index("bundle.min.js")


@needs_rg
def test_cli_files_only_and_counts_only(capsys):
    code, out, _ = run(rg_args("--files-only"), capsys)
    assert code == 0
    assert len(out.splitlines()) == 4
    code, out, _ = run(rg_args("--counts-only"), capsys)
    assert code == 0
    assert out.splitlines()[-1] == "total: 30 matches in 4 files"


@needs_rg
def test_cli_no_matches_exits_one(capsys):
    code, out, _ = run(["--rg", RG, "zz-no-such-pattern-zz", TREE], capsys)
    assert code == 1
    assert out == ""


@needs_rg
def test_cli_bad_pattern_exits_two(capsys):
    code, _, err = run(["--rg", RG, "unclosed(paren", TREE], capsys)
    assert code == 2
    assert "rg failed" in err


@needs_rg
def test_cli_deterministic(capsys):
    _, out1, _ = run(rg_args(), capsys)
    _, out2, _ = run(rg_args(), capsys)
    assert out1 == out2


# --------------------------------------------------------------- encoding

EM_DASH = "\u2014"


def utf8_probe(tmp_path, text):
    """A file whose content the console encoding cannot represent."""
    p = tmp_path / "probe.txt"
    p.write_text(text, encoding="utf-8")
    return p


def run_bytes(argv, cwd, encoding="cp1252"):
    """Subprocess with a non-UTF-8 stdio encoding forced, capturing raw bytes.
    In-process capsys can't see this: pytest's capture replaces sys.stdout
    with a stream reconfigure() does not apply to."""
    env = dict(os.environ, PYTHONIOENCODING=encoding)
    proc = subprocess.run([sys.executable, SGREP, *argv], cwd=str(cwd),
                          capture_output=True, env=env)
    return proc.returncode, proc.stdout


@needs_rg
def test_non_ascii_content_survives_a_cp1252_console(tmp_path):
    """A mangled line copied back into an Edit is a silent corruption, so
    matched content must round-trip byte-for-byte."""
    utf8_probe(tmp_path, "needle a %s here\n" % EM_DASH)
    code, out = run_bytes(["--rg", RG, "needle", "probe.txt"], tmp_path)
    assert code == 0
    assert EM_DASH.encode("utf-8") in out
    assert b"?" not in out


# ------------------------------------------------ default budget (ADR-005)

def _wide_tree(tmp_path, nfiles=40, matches=3, filler=12):
    """Many files, few distinct matches each, distinct surrounding text -
    so nothing is collapsed by the per-file representative logic and the
    budget ladder is what decides the size."""
    for i in range(nfiles):
        lines = []
        for m in range(matches):
            lines += ["pad %d %d %d" % (i, m, k) for k in range(filler)]
            lines.append("needle unique %d %d" % (i, m))
        (tmp_path / ("f%02d.py" % i)).write_text(
            "\n".join(lines), encoding="utf-8")


def test_default_max_tokens_is_on():
    """The ladder must engage without being asked for: an opt-in cap only
    protects callers who already suspected the output would be large."""
    assert sgrep.DEFAULT_MAX_TOKENS > 0


@needs_rg
def test_default_budget_caps_a_large_search(tmp_path):
    _wide_tree(tmp_path)
    code, out = run_bytes(["--rg", RG, "-C", "5", "needle", "."], tmp_path)
    assert code == 0
    text = out.decode("utf-8", "replace")
    assert sgrep._tokens_of(text.splitlines()) <= sgrep.DEFAULT_MAX_TOKENS
    # and it names the flag, so the caller knows a bigger cap is available
    assert "--max-tokens" in text


@needs_rg
def test_max_tokens_zero_restores_unbounded_output(tmp_path):
    _wide_tree(tmp_path)
    _, capped = run_bytes(["--rg", RG, "-C", "5", "needle", "."], tmp_path)
    code, full = run_bytes(
        ["--rg", RG, "-C", "5", "--max-tokens", "0", "needle", "."], tmp_path)
    assert code == 0
    assert len(full) > len(capped)


@needs_rg
def test_small_search_is_untouched_by_the_default(tmp_path):
    """The default must be invisible for ordinary calls - a cap that
    reshapes everyday output would just be a different kind of noise."""
    (tmp_path / "one.py").write_text("a\nneedle here\nb\n", encoding="utf-8")
    _, deflt = run_bytes(["--rg", RG, "needle", "."], tmp_path)
    _, unbounded = run_bytes(["--rg", RG, "--max-tokens", "0", "needle", "."],
                             tmp_path)
    assert deflt == unbounded


def test_context_lines_carry_no_path_prefix():
    """Context lines are situating text, not claims, and sit under a header
    that already names the file. Repeating the path on each one was the
    bulk of sgrep's overhead against raw `rg` (savings_record.md: 193 of
    297 credited calls printed more than the dump they replaced)."""
    files = canned("context.jsonl")
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    out = sgrep.apply_budget(ranked, files, _Args(context=1, max_tokens=0))
    ctx = [l for l in out if re.match(r"^\s*\d+- ", l)]
    assert ctx, "expected context lines"
    for line in ctx:
        assert ".py" not in line.split("- ", 1)[0], line


def test_match_lines_still_carry_path_and_line():
    """The other half of the trade: every line that makes a claim about
    code stays followable with xread (INVARIANTS.md)."""
    files = canned("context.jsonl")
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    out = sgrep.apply_budget(ranked, files, _Args(context=1, max_tokens=0))
    matches = [l for l in out
               if not l.startswith(("==", "(")) and l.strip()
               and not re.match(r"^\s*\d+- ", l)]
    assert matches, "expected match lines"
    for line in matches:
        assert re.match(r"^\S+:\d+: ", line), line


def test_reduced_context_is_announced():
    """Dropped context must not read as absent context."""
    files = canned("context.jsonl")
    weights, extra = default_conf()
    ranked = sgrep.rank(files, weights, extra)
    full = sgrep.apply_budget(ranked, files, _Args(context=3))
    tight = sgrep.apply_budget(
        ranked, files,
        _Args(context=3, max_tokens=sgrep._tokens_of(full) - 1))
    assert tight[0].startswith("(context reduced 3 -> ")
    assert "--max-tokens" in tight[0]
    # no note when nothing was taken away
    assert not full[0].startswith("(context reduced")
