import os
import re

import repomap

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
            if re.match(r"^\S.*  \[refs \d+\]$", l)]


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

def test_focus_expands_subtree_and_compresses_rest(capsys):
    out = full(capsys, "--focus", "web")
    headers = ref_headers(out)
    assert headers[0] == PREFIX + "web/index.ts"
    # focus file keeps full detail
    assert "export function mount(el: Element): void" in out
    # non-focus files fall back to names-only
    assert "def parse(text)" not in out
    assert sym_line("src/util.py", "def parse", "func parse") in out


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
