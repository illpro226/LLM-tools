#!/usr/bin/env python3
"""testmap: change-to-test scoper over .repoindex/index.db.

Maps a changed-file set (git diff + untracked, or explicit args) to the
tests that likely cover it, as a layered union tagged by source
(DECISIONS.md ADR-001): recorded coverage rows, convention pairs, and
import-derived links up to --depth N. testmap never parses source in the
lookup path -- the convention/import layers are rows repoindex already
seeded, and transitive links are walked over the index's `imports` table
(ADR-005). The mapped set is a recommendation, never a completeness claim
(ADR-003); the full-suite command stays the caller's fallback.

Output contract (INVARIANTS.md): plain text, deterministic ordering, every
claim line carries a path:line reference, --max-tokens collapses the target
list to a (+N more) count while keeping the run command(s), --json mirrors
the text content.

Exit codes: 0 mapped (possibly to nothing), 1 changed files undeterminable,
2 no index / record prerequisites missing; `record` passes the wrapped test
command's exit code through.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

DB_RELPATH = os.path.join(".repoindex", "index.db")

# Mirrors repoindex's _TEST_STEM_PATTERNS (resolve.py) so both sides of the
# shared `tests` table agree on what a test file is.
_TEST_FILE_PATTERNS = [
    re.compile(r"^test_.+\.py$"), re.compile(r"^.+_test\.py$"),
    re.compile(r"^.+\.(test|spec)\.[jt]sx?$"),
    re.compile(r"^.+_test\.go$"),
]

_EXT_FAMILY = {
    ".py": "python",
    ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
    ".mjs": "js", ".cjs": "js",
    ".go": "go",
}
_LANG_FAMILY = {"python": "python", "javascript": "js", "typescript": "js",
                "go": "go"}
_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

# Layer trust order (ADR-001): coverage is recorded fact, a changed test
# file trivially selects itself, convention beats a stem-matched import.
_RANK = {"coverage": 0, "changed-test": 1, "convention": 2, "import": 3}


def _is_test_file(path):
    base = path.rsplit("/", 1)[-1]
    return any(p.match(base) for p in _TEST_FILE_PATTERNS)


def _family_of(path, languages):
    lang = languages.get(path)
    if lang in _LANG_FAMILY:
        return _LANG_FAMILY[lang]
    ext = os.path.splitext(path)[1].lower()
    return _EXT_FAMILY.get(ext)


def _norm(path, root):
    """Repo-relative posix path for an explicit argument."""
    p = path.replace("\\", "/")
    if os.path.isabs(p):
        p = os.path.relpath(p, root).replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


# --------------------------------------------------------- freshness ---

def ensure_fresh(root, repoindex_cmd=None):
    """Run `repoindex update` so lookups never read a stale index.

    Resolution order: --repoindex flag, TESTMAP_REPOINDEX env var,
    `repoindex` on PATH, then the sibling checkout
    (tools/repoindex/repoindex.py). Returns True if an update ran.
    """
    cmd = repoindex_cmd or os.environ.get("TESTMAP_REPOINDEX") or "repoindex"
    resolved = shutil.which(cmd)
    if resolved is not None:
        # Resolved path, not bare name: Windows PATH shims are .cmd files,
        # which CreateProcess won't resolve from a bare name.
        argv = [resolved, "--root", root, "update"]
    else:
        sibling = os.path.normpath(os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "repoindex", "repoindex.py"))
        if not os.path.isfile(sibling):
            return False
        argv = [sys.executable, sibling, "--root", root, "update"]
    proc = subprocess.run(argv, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write("testmap: `repoindex update` failed:\n" + proc.stderr)
        return False
    return True


def open_db(root, readonly=True):
    db_path = os.path.join(root, DB_RELPATH)
    if not os.path.exists(db_path):
        return None
    if readonly:
        uri = f"file:{db_path.replace(os.sep, '/')}?mode=ro"
        return sqlite3.connect(uri, uri=True)
    return sqlite3.connect(db_path)


# --------------------------------------------------- changed-file set ---

def _git(root, *args):
    proc = subprocess.run(["git", "-C", root, *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def detect_changed(root):
    """Modified (vs HEAD) plus untracked files, repo-relative posix.

    Returns None when git is unavailable or `root` is not the top of a
    work tree (git paths are toplevel-relative, so an enclosing repo's
    answer would not match index paths); a repo with no commits yet
    degrades to untracked-only.
    """
    top = _git(root, "rev-parse", "--show-toplevel")
    if not top or os.path.normcase(os.path.normpath(top[0])) != \
            os.path.normcase(os.path.normpath(root)):
        return None
    untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    if untracked is None:
        return None
    modified = _git(root, "diff", "--name-only", "HEAD") or []
    return sorted(set(modified) | set(untracked))


# ------------------------------------------------------ import graph ---

def _module_stem(module, family):
    """Last component of an import's module string (mirrors rq)."""
    if family == "python":
        return module.lstrip(".").rsplit(".", 1)[-1] or None
    base = module.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if family == "js":
        for ext in _JS_EXTS:
            if base.endswith(ext):
                return base[: -len(ext)]
    return base or None


def build_reverse_imports(conn, languages):
    """importers[target_path] = {importer_path}, from the index's imports
    rows, resolving module strings by file stem within a language family
    (same-directory candidates win, as in rq findcycles)."""
    stems = {}  # (family, stem) -> [path]
    dirs = {}   # (family, last dir component) -> [path], for go packages
    for path in sorted(languages):
        fam = _family_of(path, languages)
        if fam is None:
            continue
        base = path.rsplit("/", 1)[-1]
        stem = base.rsplit(".", 1)[0] if "." in base else base
        stems.setdefault((fam, stem), []).append(path)
        d = path.rsplit("/", 1)[0] if "/" in path else ""
        if d:
            dirs.setdefault((fam, d.rsplit("/", 1)[-1]), []).append(path)

    importers = {}
    for file, module in conn.execute(
            "SELECT DISTINCT file, module FROM imports ORDER BY file, module"):
        fam = _family_of(file, languages)
        if fam is None:
            continue
        stem = _module_stem(module, fam)
        if not stem:
            continue
        cands = list(stems.get((fam, stem), []))
        if fam == "go":
            cands += [p for p in dirs.get((fam, stem), []) if p not in cands]
        same_dir = [p for p in cands
                    if p.rsplit("/", 1)[0] == file.rsplit("/", 1)[0]]
        if same_dir:
            cands = same_dir
        for target in cands:
            if target != file:
                importers.setdefault(target, set()).add(file)
    return importers


# ------------------------------------------------------------ mapping ---

def map_tests(conn, changed, depth):
    """Layered union: {(test_file, target_file): (rank, tag)} keeping the
    most-trusted tag per pair (ADR-001)."""
    languages = dict(conn.execute("SELECT path, language FROM files"))
    indexed = set(languages)
    best = {}

    def record(test_file, target, source, tag=None):
        key = (test_file, target)
        rank = _RANK[source]
        if key not in best or rank < best[key][0]:
            best[key] = (rank, tag or source)

    changed_indexed = [c for c in changed if c in indexed]
    for c in changed_indexed:
        if _is_test_file(c):
            record(c, c, "changed-test")

    if changed_indexed:
        placeholders = ",".join("?" for _ in changed_indexed)
        for test_file, target, source in conn.execute(
                "SELECT test_file, target_file, source FROM tests "
                f"WHERE target_file IN ({placeholders}) "
                "ORDER BY test_file, target_file", changed_indexed):
            if source == "coverage":
                record(test_file, target, "coverage")
            elif source == "convention":
                record(test_file, target, "convention")
            else:  # repoindex 'import' rows are direct imports: depth 1
                record(test_file, target, "import", "import depth 1")

    if depth >= 2 and changed_indexed:
        importers = build_reverse_imports(conn, languages)
        for c in changed_indexed:
            if _is_test_file(c):
                continue
            seen = {c}
            frontier = [c]
            for d in range(1, depth + 1):
                nxt = set()
                for f in frontier:
                    nxt |= importers.get(f, set()) - seen
                seen |= nxt
                for f in sorted(nxt):
                    if _is_test_file(f):
                        record(f, c, "import", f"import depth {d}")
                # tests are leaves; only production files keep expanding
                frontier = [f for f in sorted(nxt) if not _is_test_file(f)]
                if not frontier:
                    break
    return best, languages


# ------------------------------------------------- framework commands ---

def _detect_js_runner(root):
    for name in ("vitest.config.ts", "vitest.config.js", "vitest.config.mts",
                 "vitest.config.mjs", "vitest.workspace.ts"):
        if os.path.exists(os.path.join(root, name)):
            return "vitest"
    for name in ("jest.config.js", "jest.config.ts", "jest.config.cjs",
                 "jest.config.mjs", "jest.config.json"):
        if os.path.exists(os.path.join(root, name)):
            return "jest"
    pkg = os.path.join(root, "package.json")
    if os.path.exists(pkg):
        try:
            with open(pkg, encoding="utf-8") as f:
                text = f.read()
            if '"vitest"' in text:
                return "vitest"
            if '"jest"' in text:
                return "jest"
        except OSError:
            pass
    return None


def run_commands(root, test_files, languages):
    """One ready-to-run command per detected framework, sorted."""
    by_family = {}
    for t in sorted(test_files):
        fam = _family_of(t, languages)
        if fam:
            by_family.setdefault(fam, []).append(t)
    lines = []
    if "python" in by_family:
        lines.append("run: pytest " + " ".join(by_family["python"]))
    if "js" in by_family:
        runner = _detect_js_runner(root)
        files = " ".join(by_family["js"])
        if runner == "vitest":
            lines.append(f"run: npx vitest run {files}")
        elif runner == "jest":
            lines.append(f"run: npx jest {files}")
        else:
            lines.append(f"note: no js test runner detected for: {files}")
    if "go" in by_family:
        pkgs = sorted({t.rsplit("/", 1)[0] if "/" in t else "."
                       for t in by_family["go"]})
        lines.append("run: go test " + " ".join(
            p if p == "." else f"./{p}" for p in pkgs))
    return lines


def fallback_commands(root, changed, languages):
    fams = {_family_of(c, languages) for c in changed}
    lines = []
    if "python" in fams:
        lines.append("fallback: pytest")
    if "js" in fams:
        runner = _detect_js_runner(root)
        if runner:
            lines.append("fallback: npx " +
                         ("vitest run" if runner == "vitest" else "jest"))
    if "go" in fams:
        lines.append("fallback: go test ./...")
    return lines


# ----------------------------------------------------------- renderer ---

def _estimate_tokens(text):
    """tokq's fallback heuristic: bytes / 3.7."""
    return len(text.encode("utf-8", errors="replace")) / 3.7


def render(title, items, notes, as_json=False, max_tokens=None):
    """Collapse the target list to a (+N more) count under the budget;
    notes (the run commands) are never dropped."""
    def _text(cap):
        lines = [title] if title else []
        shown = items if cap is None else items[:cap]
        lines.extend(it["text"] for it in shown)
        if cap is not None and len(items) > cap:
            lines.append(f"  (+{len(items) - cap} more)")
        lines.extend(notes)
        return "\n".join(lines) + ("\n" if lines else "")

    def _js(cap):
        shown = items if cap is None else items[:cap]
        return json.dumps({
            "title": title,
            "targets": [it["data"] for it in shown],
            "omitted": 0 if cap is None else max(0, len(items) - cap),
            "notes": notes,
        }) + "\n"

    fmt = _js if as_json else _text
    out = fmt(None)
    if max_tokens is None or _estimate_tokens(out) <= max_tokens:
        return out
    for cap in range(max(len(items) - 1, 0), -1, -1):
        out = fmt(cap)
        if _estimate_tokens(out) <= max_tokens:
            return out
    return out  # count-only floor: cannot summarize harder


# ------------------------------------------------------------ map cmd ---

def cmd_map(args):
    root = os.path.abspath(args.root)
    if not args.no_update:
        ensure_fresh(root, args.repoindex)
    conn = open_db(root)
    if conn is None:
        sys.stderr.write("testmap: no index at .repoindex/index.db and "
                         "`repoindex` is unavailable -- run "
                         "`repoindex build` first\n")
        return 2

    if args.files:
        changed = sorted({_norm(f, root) for f in args.files})
    else:
        changed = detect_changed(root)
        if changed is None:
            sys.stderr.write("testmap: cannot determine changed files -- "
                             "not a git work tree (or git missing); pass "
                             "files explicitly\n")
            conn.close()
            return 1

    if not changed:
        conn.close()
        sys.stdout.write(render(None, [], ["note: no changed files"],
                                as_json=args.json,
                                max_tokens=args.max_tokens))
        return 0

    best, languages = map_tests(conn, changed, args.depth)
    conn.close()

    items = []
    for (test_file, target), (_rank, tag) in sorted(best.items()):
        items.append({
            "text": f"{test_file}:1  covers {target}  ({tag})",
            "data": {"test_file": test_file, "target_file": target,
                     "source": tag},
        })
    title = f"tests for {len(changed)} changed file(s):" if items else None
    if items:
        mapped = {target for _, target in best}
        unmapped = [c for c in changed
                    if c in languages and c not in mapped]
        notes = [f"note: no tests mapped for {c}:1" for c in unmapped]
        notes += run_commands(root, {t for t, _ in best}, languages)
    else:
        notes = [f"note: no tests mapped for {len(changed)} changed file(s)"]
        notes += fallback_commands(root, changed, languages)
    sys.stdout.write(render(title, items, notes, as_json=args.json,
                            max_tokens=args.max_tokens))
    return 0


# --------------------------------------------------------- record cmd ---

def _pytest_args(cmd):
    """Args after the pytest entry point, or None if this isn't pytest."""
    if not cmd:
        return None
    if os.path.basename(cmd[0]).startswith("pytest"):
        return cmd[1:]
    for i, tok in enumerate(cmd):
        if tok == "-m" and i + 1 < len(cmd) and cmd[i + 1] == "pytest":
            return cmd[i + 2:]
    return None


def _context_to_test_file(context, test_files):
    """Map a coverage context string to a repo test file.

    Handles pytest-cov style 'tests/test_x.py::test_y|run' and coverage.py
    dynamic_context=test_function dotted names ('tests.test_x.test_y' or
    'test_x.TestC.test_y' depending on how pytest imported the module).
    """
    if not context:
        return None
    head = context.split("|", 1)[0]
    if "::" in head:
        path = head.split("::", 1)[0].replace("\\", "/")
        return path if path in test_files else None
    dotted = {}
    for path in test_files:
        mod = path[:-3] if path.endswith(".py") else path
        dotted.setdefault(mod.replace("/", "."), []).append(path)
        dotted.setdefault(mod.rsplit("/", 1)[-1], []).append(path)
    matches = set()
    for prefix, paths in dotted.items():
        if head == prefix or head.startswith(prefix + "."):
            matches.update(paths)
    if len(matches) == 1:
        return matches.pop()
    # prefer the longest full-path match when basenames collide
    full = [p for p in matches
            if head.startswith(p[:-3].replace("/", "."))]
    return full[0] if len(full) == 1 else None


def cmd_record(args):
    root = os.path.abspath(args.root)
    cmd = list(args.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    pytest_args = _pytest_args(cmd)
    if pytest_args is None:
        sys.stderr.write("testmap record: only pytest is supported so far "
                         "(DECISIONS.md ADR-007) -- usage: "
                         "testmap record -- pytest [ARGS]\n")
        return 2
    try:
        import coverage  # noqa: F401
    except ImportError:
        sys.stderr.write("testmap record: coverage.py is required -- "
                         "pip install coverage\n")
        return 2

    if not args.no_update:
        ensure_fresh(root, args.repoindex)
    conn = open_db(root, readonly=False)
    if conn is None:
        sys.stderr.write("testmap: no index at .repoindex/index.db -- run "
                         "`repoindex build` first\n")
        return 2

    tmpdir = tempfile.mkdtemp(prefix="testmap-")
    data_file = os.path.join(tmpdir, "coverage.db")
    rcfile = os.path.join(tmpdir, "coveragerc")
    with open(rcfile, "w", encoding="utf-8") as f:
        f.write("[run]\ndynamic_context = test_function\n"
                "relative_files = True\n"
                f"data_file = {data_file}\n")

    proc = subprocess.run(
        [sys.executable, "-m", "coverage", "run", "--rcfile", rcfile,
         "-m", "pytest", *pytest_args], cwd=root)

    if not os.path.exists(data_file):
        sys.stderr.write("testmap record: no coverage data produced\n")
        conn.close()
        return proc.returncode or 2

    indexed = {row[0] for row in conn.execute("SELECT path FROM files")}
    test_files = {p for p in indexed if _is_test_file(p)}

    from coverage import CoverageData
    data = CoverageData(basename=data_file)
    data.read()
    links = set()
    for measured in data.measured_files():
        target = measured.replace("\\", "/")
        if os.path.isabs(target):
            target = os.path.relpath(target, root).replace("\\", "/")
        if target not in indexed or target in test_files:
            continue
        contexts = set()
        for ctxs in (data.contexts_by_lineno(measured) or {}).values():
            contexts.update(ctxs)
        for ctx in contexts:
            test_file = _context_to_test_file(ctx, test_files)
            if test_file is not None:
                links.add((test_file, target))

    seen_tests = sorted({t for t, _ in links})
    if seen_tests:
        placeholders = ",".join("?" for _ in seen_tests)
        conn.execute("DELETE FROM tests WHERE source = 'coverage' "
                     f"AND test_file IN ({placeholders})", seen_tests)
    for test_file, target in sorted(links):
        conn.execute("INSERT INTO tests (test_file, target_file, source) "
                     "VALUES (?, ?, 'coverage')", (test_file, target))
    conn.commit()
    conn.close()
    print(f"testmap record: {len(links)} coverage link(s) from "
          f"{len(seen_tests)} test file(s) -> {DB_RELPATH}")
    return proc.returncode


# --------------------------------------------------------------- main ---

def _shared_flags(parser):
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    parser.add_argument("--repoindex", default=None,
                        help="repoindex command for the freshness guard "
                             "(default: repoindex on PATH or the sibling "
                             "checkout; env TESTMAP_REPOINDEX)")
    parser.add_argument("--no-update", action="store_true",
                        help="skip the automatic `repoindex update`")


def _pin_utf8():
    """Test and target paths are echoed verbatim; a cp1252 console default
    would replace anything non-ASCII with `?`."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def main(argv=None):
    _pin_utf8()
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv[:1] == ["record"]:
        parser = argparse.ArgumentParser(
            prog="testmap record",
            description="run the suite under coverage and write file->test "
                        "rows into the shared index (source=coverage)")
        _shared_flags(parser)
        parser.add_argument("cmd", nargs=argparse.REMAINDER,
                            help="test command after `--`, e.g. -- pytest")
        args = parser.parse_args(argv[1:])
        return cmd_record(args)

    parser = argparse.ArgumentParser(
        prog="testmap",
        description="map changed files to the tests that cover them "
                    "(`testmap record -- pytest` records exact coverage)")
    _shared_flags(parser)
    parser.add_argument("files", nargs="*",
                        help="changed files (default: git diff --name-only "
                             "HEAD + untracked)")
    parser.add_argument("--depth", type=int, default=2,
                        help="max transitive import depth (default 2)")
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of text")
    parser.add_argument("--max-tokens", type=int, default=None,
                        help="token budget; the target list collapses to "
                             "a count")
    args = parser.parse_args(argv)
    return cmd_map(args)


if __name__ == "__main__":
    sys.exit(main())
