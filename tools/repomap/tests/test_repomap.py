import os
import re
import subprocess
import sys

import repomap

REPOMAP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "repomap.py")
REPO = os.path.join(os.path.dirname(__file__), "fixtures", "repo")
PREFIX = REPO.replace("\\", "/") + "/"

_LINECACHE = {}


def lineno(rel, needle, nth=1):
    """1-indexed line of the nth occurrence of needle in a fixture file."""
    path = os.path.join(REPO, rel.replace("/", os.sep))
    if path not in _LINECACHE:
        with open(path, encoding="utf-8") as fh:
            _LINECACHE[path] = fh.read().splitlines()
    hits = [i for i, l in enumerate(_LINECACHE[path], 1) if needle in l]
    return hits[nth - 1]


def run(argv, capsys):
    code = repomap.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def full(capsys, *extra):
    code, out, err = run([REPO, *extra], capsys)
    assert code == 0, err
    return out


def sym_line(rel, needle, rest):
    return "  %s%s:%d %s" % (PREFIX, rel, lineno(rel, needle), rest)


def ref_headers(out):
    """File-outline header paths in output order."""
    return [l.split("  [refs")[0] for l in out.splitlines()
            if re.match(r"^\S.*  \[refs \d+\](  \(\d+ symbols?\))?$", l)]


def est(out):
    return len(out.rstrip("\n").encode("utf-8")) // 4 + 1


# ----------------------------------------------------------------- pruning

def test_tree_prunes_vendored_and_generated_dirs(capsys):
    out = full(capsys)
    for absent in ("node_modules", "dist", "__pycache__", "hidden",
                   "bundled", "pyc"):
        assert absent not in out
    assert "README.md" in out


def test_gitignore_entries_pruned(capsys):
    out = full(capsys)
    assert "generated" not in out
    assert "generated_fn" not in out
    assert "secret.txt" not in out


# -------------------------------------------------------------- extraction

def test_python_outline(capsys):
    out = full(capsys)
    assert sym_line("src/app.py", "class App", "class App(Base) — Run the "
                    "app.") in out
    assert sym_line("src/app.py", "def main", "def main(argv) — Entry "
                    "point.") in out
    assert "def start" not in out  # methods are not top-level


def test_ts_outline(capsys):
    out = full(capsys)
    assert sym_line("web/index.ts", "export function mount",
                    "export function mount(el: Element): void — Mount the "
                    "view onto an element.") in out
    assert sym_line("web/index.ts", "export class View",
                    "export class View") in out
    assert sym_line("web/index.ts", "export const handler",
                    "export const handler = (ev: Event): void") in out
    assert "draw" not in "\n".join(
        l for l in out.splitlines() if ":" in l and "index.ts:" in l)


def test_go_outline(capsys):
    out = full(capsys)
    assert sym_line("go/server.go", "type Config struct",
                    "type Config struct — Config holds settings.") in out
    assert sym_line("go/server.go", "func (c *Config) Load",
                    "func (c *Config) Load(path string) error — Load reads "
                    "settings from a file.") in out
    assert sym_line("go/server.go", "func Serve",
                    "func Serve(addr string) error — Serve starts "
                    "listening.") in out


def test_rust_outline(capsys):
    out = full(capsys)
    assert sym_line("rust/lib.rs", "pub struct Point",
                    "pub struct Point — A point in 2-D space.") in out
    assert sym_line("rust/lib.rs", "impl Point", "impl Point") in out
    assert sym_line("rust/lib.rs", "pub trait Shape",
                    "pub trait Shape — Common shape behaviour.") in out
    assert sym_line("rust/lib.rs", "pub fn combine",
                    "pub fn combine(a: i32, b: i32) -> i32 — Sums two "
                    "numbers.") in out
    assert "origin" not in out  # impl methods are not top-level


def test_c_outline(capsys):
    out = full(capsys)
    assert sym_line("cpp/core.c", "#define MAX_LEN",
                    "#define MAX_LEN 128") in out
    assert sym_line("cpp/core.c", "struct Buffer",
                    "struct Buffer — A growable byte buffer.") in out
    assert sym_line("cpp/core.c", "void free_buffer",
                    "void free_buffer(char *buf) — Frees the buffer "
                    "storage.") in out
    assert sym_line("cpp/core.c", "int run_core",
                    "int run_core(int level)") in out


def test_fallback_outline_for_unsupported_language(capsys):
    out = full(capsys)
    assert sym_line("misc/tool.lua", "function greet",
                    "function greet(name) — Greets by name.") in out


# ----------------------------------------------------------------- ranking

def test_files_ordered_by_reference_count(capsys):
    out = full(capsys)
    headers = ref_headers(out)
    assert headers[0] == PREFIX + "src/util.py"   # referenced by app.py
    assert headers[1] == PREFIX + "src/app.py"    # referenced by index.ts
    rest = headers[2:]
    assert rest == sorted(rest)  # zero-ref ties break by path


def test_output_is_deterministic(capsys):
    assert full(capsys) == full(capsys)


def test_ranking_labeled_heuristic(capsys):
    assert "(ranking: heuristic" in full(capsys)


# ------------------------------------------------------------------- focus

def test_focus_narrows_to_subtree(capsys):
    out = full(capsys, "--focus", "web")
    headers = ref_headers(out)
    assert headers[0] == PREFIX + "web/index.ts"
    # focus file keeps full detail
    assert "export function mount(el: Element): void" in out
    # every other file collapses to its header line — no symbols at all
    assert "def parse(text)" not in out
    assert sym_line("src/util.py", "def parse", "func parse") not in out
    assert PREFIX + "src/util.py" + "  [refs " in out
    assert "symbols)" in out
    assert "collapsed to one line" in out


def test_test_function_runs_collapse_to_a_count(capsys, tmp_path):
    """A well-tested file should not cost more to map than a bare one."""
    (tmp_path / "test_suite.py").write_text(
        "def helper():\n    pass\n\n"
        + "".join("def test_case_%d():\n    pass\n\n" % i for i in range(12)),
        encoding="utf-8")
    code, out, err = run([str(tmp_path)], capsys)
    assert code == 0, err
    assert "12 test functions (test_case_0 …)" in out
    for i in range(1, 12):
        assert "test_case_%d" % i not in out
    assert "def helper()" in out          # non-test symbols still listed


def test_short_test_runs_are_left_alone(capsys, tmp_path):
    (tmp_path / "test_pair.py").write_text(
        "def test_a():\n    pass\n\ndef test_b():\n    pass\n",
        encoding="utf-8")
    code, out, err = run([str(tmp_path)], capsys)
    assert code == 0, err
    assert "test_a" in out and "test_b" in out
    assert "test functions" not in out


def test_focus_missing_path_errors(capsys):
    code, out, err = run([REPO, "--focus", "nope/nowhere"], capsys)
    assert code == 2
    assert "--focus path not found" in err


# ------------------------------------------------------------- token budget

def test_budget_drops_low_rank_files_first(capsys):
    out = full(capsys)
    budget = est(out) - 5
    capped = full(capsys, "--max-tokens", str(budget))
    assert est(capped) <= budget
    assert "outlines dropped for --max-tokens" in capped
    headers = ref_headers(capped)
    assert headers[0] == PREFIX + "src/util.py"       # top rank survives
    assert "def parse(text)" in capped                # signatures survive


def test_budget_degrades_in_order_and_stays_within(capsys):
    out = full(capsys)
    stages = []
    for budget in range(est(out) + 20, 90, -20):
        capped = full(capsys, "--max-tokens", str(budget))
        assert est(capped) <= budget
        if "signatures dropped" in capped:
            stage = "names"
            assert "def parse(text)" not in capped
            assert re.search(r"src/util\.py:\d+ func parse", capped)
        elif "tree only" in capped:
            stage = "tree"
            assert not ref_headers(capped)
        elif "outlines dropped" in capped:
            stage = "drop"
        else:
            stage = "full"
        stages.append(stage)
    order = ["full", "drop", "names", "tree"]
    ranks = [order.index(s) for s in stages]
    assert ranks == sorted(ranks)          # detail only ever decreases
    assert set(stages) >= {"drop", "names", "tree"}


def test_budget_never_truncates_mid_entry(capsys):
    sym = re.compile(r"^  \S+:\d+ \S.*$")
    for budget in (400, 250, 150, 100):
        capped = full(capsys, "--max-tokens", str(budget))
        for line in capped.splitlines():
            if line.startswith("  ") and re.match(r"^  \S+:\d+", line):
                assert sym.match(line), line


def test_tree_only_keeps_tree(capsys):
    capped = full(capsys, "--max-tokens", "110")
    assert "tree only" in capped
    assert "util.py" in capped
    assert "[refs" not in capped


# ------------------------------------------------------------------ errors

def test_missing_dir_errors(capsys):
    code, out, err = run([os.path.join(REPO, "no_such_dir")], capsys)
    assert code == 2
    assert "not a directory" in err


# --------------------------------------------------------------- encoding

def test_non_ascii_content_survives_a_cp1252_console(tmp_path):
    """Docstrings echoed into an outline must round-trip byte-for-byte; a
    mangled line copied back into an Edit is a silent corruption. In-process
    capsys can't see this — pytest's capture replaces sys.stdout with a
    stream reconfigure() does not apply to — so run the CLI for real."""
    (tmp_path / "probe.py").write_text(
        'def f():\n    """Map file\u2192keys \u2014 one way."""\n    return 1\n',
        encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="cp1252")
    proc = subprocess.run([sys.executable, REPOMAP, str(tmp_path)],
                          capture_output=True, env=env)
    assert proc.returncode == 0, proc.stderr
    assert "\u2014".encode("utf-8") in proc.stdout
    assert "\u2192".encode("utf-8") in proc.stdout
    assert b"?" not in proc.stdout


# ------------------------------------------- default token cap (ADR-007)

def _wide_repo(tmp_path, dirs=12, files=8, funcs=12):
    for d in range(dirs):
        sub = tmp_path / ("pkg%02d" % d)
        sub.mkdir()
        for f in range(files):
            (sub / ("mod%d.py" % f)).write_text(
                "\n".join("def func_%d_%d_%d(alpha, beta, gamma):\n"
                          "    return %d" % (d, f, i, i)
                          for i in range(funcs)), encoding="utf-8")
    return str(tmp_path)


def test_default_max_tokens_is_on():
    assert repomap.DEFAULT_MAX_TOKENS > 0


def test_default_budget_caps_a_large_map(tmp_path, capsys):
    """Orientation is read at the start of a task, when context is most
    valuable - the worst moment to emit an unbounded map."""
    where = _wide_repo(tmp_path)
    code, out, err = run([where], capsys)
    assert code == 0, err
    assert est(out) <= repomap.DEFAULT_MAX_TOKENS
    assert "--max-tokens" in out    # and it says what it took away


def test_max_tokens_zero_restores_unbounded_output(tmp_path, capsys):
    where = _wide_repo(tmp_path)
    _, capped, _ = run([where], capsys)
    code, unbounded, err = run([where, "--max-tokens", "0"], capsys)
    assert code == 0, err
    assert len(unbounded) > len(capped)


def test_small_repo_is_untouched_by_the_default(tmp_path, capsys):
    (tmp_path / "only.py").write_text("def f():\n    return 1\n",
                                      encoding="utf-8")
    _, deflt, _ = run([str(tmp_path)], capsys)
    _, unbounded, _ = run([str(tmp_path), "--max-tokens", "0"], capsys)
    assert deflt == unbounded


# ------------------------------------------------ v0.4.0 review fixes

def _pairwise_rank(files):
    """The pre-0.4.0 O(files²) ranking, kept as the reference the
    document-frequency version must reproduce exactly."""
    scores = {}
    for f in files:
        score = 0
        for g in files:
            if g is f:
                continue
            if f["stem"] and f["stem"] in g["tokens"]:
                score += 2
            score += sum(1 for n in f["names"] if n in g["tokens"])
        scores[f["rel"]] = score
    return scores


def test_document_frequency_rank_matches_the_pairwise_scores():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for root in (REPO, os.path.dirname(here)):       # fixture + all tools
        _, files, _ = repomap.scan(root, repomap._load_gitignore(root))
        want = _pairwise_rank(files)
        repomap.rank(files)
        assert {f["rel"]: f["score"] for f in files} == want


def test_wide_flat_directory_fits_the_budget(tmp_path, capsys):
    """Collapsing depth never shrinks a directory's own listing, so a root
    of 3,000 files printed ~12,800 tokens against the 3,000 default."""
    for i in range(3000):
        (tmp_path / ("f_%04d.txt" % i)).write_text("x", encoding="utf-8")
    for budget in (3000, 400, 60):
        code, out, _ = run([str(tmp_path), "--max-tokens", str(budget)],
                           capsys)
        assert code == 0
        lines = out.splitlines()
        if budget >= 400:
            assert repomap._est(lines) <= budget
        else:
            # The floor: header, root, one entry, its count, two notes —
            # constant in the file count (its size is the tmp path's).
            assert len(lines) <= 8
        assert re.search(r"… \(\+\d+ more files\)", out)
        assert "--max-tokens %d)" % budget in lines[-1]


def test_bom_and_conditional_python_defs_are_outlined(tmp_path, capsys):
    (tmp_path / "bom.py").write_bytes(
        b"\xef\xbb\xbfdef first():\n    return 1\n")
    (tmp_path / "cond.py").write_text(
        "import sys\n\nif sys.platform == 'win32':\n"
        "    def helper():\n        return 1\nelse:\n"
        "    def helper():\n        return 2\n\n"
        "try:\n    import tomllib\nexcept ImportError:\n"
        "    def load():\n        return {}\n", encoding="utf-8")
    code, out, _ = run([str(tmp_path), "--max-tokens", "0"], capsys)
    assert code == 0
    assert re.search(r"bom\.py:1 def first\(\)", out)
    assert len(re.findall(r"cond\.py:\d+ def helper\(\)", out)) == 2
    assert re.search(r"cond\.py:13 def load\(\)", out)


def test_ts_decl_after_a_multiline_template_is_top_level(tmp_path, capsys):
    """The line closing a template literal was skipped whole; a `{` after
    the backtick never opened, depth went negative-clamped, and the next
    nested declaration could read as top-level (or the next top-level one
    be missed once depth drifted up)."""
    (tmp_path / "t.ts").write_text(
        "export function first() {\n"
        "  const q = sql(`SELECT *\n"
        "    FROM t`).then((r) => {\n"
        "    return r;\n"
        "  });\n"
        "  function inner() { return q; }\n"   # depth 1, read as 0 before
        "  return inner();\n"
        "}\n"
        "export function second() {\n"
        "  return 2;\n"
        "}\n", encoding="utf-8")
    code, out, _ = run([str(tmp_path), "--max-tokens", "0"], capsys)
    assert code == 0
    assert "inner" not in out
    assert re.search(r"t\.ts:9 export function second\(\)", out)
