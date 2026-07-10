#!/usr/bin/env python3
"""sgrep — token-budgeted search condenser.

A ripgrep wrapper that post-processes `rg --json` results for LLM
consumption: groups matches by file, deduplicates near-identical hits,
ranks files by match count x path-class weight (src > tests > generated),
and hard-caps total output.

    sgrep PATTERN [PATH...]         condensed, ranked digest
    sgrep PATTERN --files-only      matching file list only
    sgrep PATTERN --counts-only     file list with match counts
    sgrep PATTERN --max-tokens N    reduce: context, then matches per
                                    file, then files shown, in that order

Matching is never reimplemented: ripgrep must be installed (`rg` on PATH,
or point at a binary with --rg / SGREP_RG). Exit codes follow grep: 0
matches found, 1 none, 2 error.
"""

import argparse
import json
import os
import re
import subprocess
import sys

__version__ = "0.1.0"

SHOW_ALL_LIMIT = 5    # files with <= this many matching lines show them all
REPRESENTATIVES = 3   # distinct lines shown when a file exceeds the limit
MAX_STORED = 200      # matches kept per file; the count keeps rising past it

GENERATED_PARTS = {
    "node_modules", "dist", "build", "vendor", "__pycache__", "coverage",
    "target", ".repoindex", "generated", ".next", ".nuxt", ".cache", ".git",
}
GENERATED_NAME = re.compile(
    r"\.min\.|\.bundle\.|\.lock$|^package-lock\.json$|^go\.sum$|\.map$"
    r"|_pb2\.py$|\.generated\.")
TEST_PARTS = {"test", "tests", "__tests__", "spec", "testdata"}
TEST_NAME = re.compile(
    r"^test_|_test\.\w+$|\.test\.\w+$|\.spec\.\w+$|^conftest\.py$")

DEFAULT_WEIGHTS = {"src": 1.0, "tests": 0.5, "generated": 0.2}


class SgrepError(Exception):
    pass


def _tokens_of(lines):
    return sum(len(line) + 1 for line in lines) // 4


# ------------------------------------------------------------------ config

def load_config(path):
    """Weights and extra class patterns from .sgrep.toml, if present."""
    weights = dict(DEFAULT_WEIGHTS)
    extra = {"generated": [], "tests": []}
    if path is None and os.path.exists(".sgrep.toml"):
        path = ".sgrep.toml"
    if path:
        import tomllib
        try:
            with open(path, "rb") as fh:
                cfg = tomllib.load(fh)
        except (OSError, ValueError) as exc:
            raise SgrepError("config %s: %s" % (path, exc))
        for key, value in cfg.get("weights", {}).items():
            if key not in weights:
                raise SgrepError("config %s: unknown class %r (expected "
                                 "src/tests/generated)" % (path, key))
            weights[key] = float(value)
        for key in extra:
            extra[key] = list(cfg.get("classes", {}).get(key, []))
    return weights, extra


def classify(path, extra):
    from fnmatch import fnmatch
    posix = path.replace("\\", "/")
    parts = posix.split("/")
    name = parts[-1]
    dirs = [p.lower() for p in parts[:-1]]
    if (any(p in GENERATED_PARTS for p in dirs) or GENERATED_NAME.search(name)
            or any(fnmatch(posix, pat) for pat in extra["generated"])):
        return "generated"
    if (any(p in TEST_PARTS for p in dirs) or TEST_NAME.search(name)
            or any(fnmatch(posix, pat) for pat in extra["tests"])):
        return "tests"
    return "src"


# ----------------------------------------------------------------- parsing

def parse_stream(lines):
    """Consume an `rg --json` event stream incrementally.

    Returns {path: {"count", "matches": [(line, text)], "contexts": {line:
    text}}}; a match is one matching line (rg emits one event per line).
    """
    files = {}
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except ValueError:
            continue
        kind = event.get("type")
        if kind not in ("match", "context"):
            continue
        data = event["data"]
        path = data["path"].get("text")
        if not path:  # non-UTF-8 path (base64 variant): not worth the cost
            continue
        entry = files.setdefault(
            path, {"count": 0, "matches": [], "contexts": {}})
        text = (data["lines"].get("text") or "").rstrip("\r\n")
        line = data["line_number"]
        if kind == "match":
            entry["count"] += 1
            if len(entry["matches"]) < MAX_STORED:
                entry["matches"].append((line, text))
        elif len(entry["contexts"]) < MAX_STORED * 2:
            entry["contexts"][line] = text
    return files


def run_rg(rg_bin, argv_tail):
    cmd = [rg_bin, "--json", "--no-config", "--sort", "path"] + argv_tail
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True,
                                encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise SgrepError(
            "ripgrep not found (looked for %r); install it — "
            "winget install BurntSushi.ripgrep.MSVC / apt install ripgrep / "
            "brew install ripgrep — or point --rg / SGREP_RG at the binary"
            % rg_bin)
    files = parse_stream(proc.stdout)
    stderr = proc.stderr.read()
    code = proc.wait()
    if code not in (0, 1):
        raise SgrepError("rg failed: %s" % (stderr.strip() or
                                            "exit %d" % code))
    return files


# ------------------------------------------------------- dedupe and ranking

def normalize(text):
    """Collapse whitespace and digit runs so near-identical hits cluster."""
    return re.sub(r"\d+", "0", " ".join(text.split()))


def select_matches(entry, cap):
    """Pick the shown matches for one file.

    Files at or under SHOW_ALL_LIMIT show every match; above it, one
    representative per normalized-content cluster (largest clusters first),
    REPRESENTATIVES at most. `cap` tightens either path under --max-tokens.
    Returns (shown [(line, text)] in line order, hidden count).
    """
    count = entry["count"]
    limit = count if count <= SHOW_ALL_LIMIT else REPRESENTATIVES
    if cap is not None:
        limit = min(limit, cap)
    if count <= SHOW_ALL_LIMIT:
        shown = entry["matches"][:limit]
    else:
        clusters = {}
        for line, text in entry["matches"]:
            clusters.setdefault(normalize(text), []).append((line, text))
        ordered = sorted(clusters.values(), key=lambda c: (-len(c), c[0][0]))
        shown = sorted(c[0] for c in ordered[:limit])
    return shown, count - len(shown)


def rank(files, weights, extra):
    """Paths by score = match count x path-class weight; ties by path."""
    def score(path):
        return files[path]["count"] * weights[classify(path, extra)]
    return sorted(files, key=lambda p: (-score(p), p))


# --------------------------------------------------------------- rendering

def _context_lines(entry, shown, radius):
    ctx = {}
    for line, _ in shown:
        for offset in range(-radius, radius + 1):
            if offset and (line + offset) in entry["contexts"]:
                ctx[line + offset] = entry["contexts"][line + offset]
    return ctx


def render(ranked, files, ctx_radius, cap, nfiles, counts_only, files_only):
    kept = ranked[:nfiles]
    if files_only:
        return list(kept)
    if counts_only:
        rows = [(files[p]["count"], p) for p in kept]
        width = max((len(str(c)) for c, _ in rows), default=1)
        lines = ["%*d  %s" % (width, c, p) for c, p in rows]
        total = sum(files[p]["count"] for p in ranked)
        lines.append("total: %d matches in %d files" % (total, len(ranked)))
        return lines

    out = []
    for path in kept:
        entry = files[path]
        if out:
            out.append("")
        n = entry["count"]
        out.append("== %s (%d match%s) ==" % (path, n, "es"[: 2 * (n != 1)]))
        shown, hidden = select_matches(entry, cap)
        ctx = _context_lines(entry, shown, ctx_radius) if ctx_radius else {}
        match_lines = {line for line, _ in shown}
        for line in sorted(match_lines | set(ctx)):
            if line in match_lines:
                text = dict(shown)[line]
                out.append("%s:%d: %s" % (path, line, text))
            else:
                out.append("%s:%d- %s" % (path, line, ctx[line]))
        if hidden:
            out.append("(+%d more similar)" % hidden)
    if len(ranked) > len(kept):
        dropped = ranked[len(kept):]
        out.append("")
        out.append("(+%d more files with %d matches)"
                   % (len(dropped), sum(files[p]["count"] for p in dropped)))
    return out


def apply_budget(ranked, files, args):
    """ADR-003: reduce context, then matches per file, then files shown."""
    ctx = args.context
    cap = None
    nfiles = len(ranked)
    counts_only = args.counts_only
    while True:
        lines = render(ranked, files, ctx, cap, nfiles, counts_only,
                       args.files_only)
        if not args.max_tokens or _tokens_of(lines) <= args.max_tokens:
            return lines
        if ctx > 0:
            ctx -= 1
        elif cap is None:
            cap = REPRESENTATIVES
        elif cap > 1:
            cap -= 1
        elif nfiles > 1:
            nfiles -= 1
        elif not counts_only and not args.files_only:
            counts_only = True
            lines = render(ranked, files, 0, 1, len(ranked), True, False)
            noted = ["(reduced to counts for --max-tokens %d)"
                     % args.max_tokens] + lines
            if _tokens_of(noted) <= args.max_tokens:
                return noted
            break  # truncate the bare counts rows below
        else:
            break
    # even the cheapest full rendering is over budget: truncate rows,
    # keeping the elision marker itself inside the budget
    def marker(n):
        return "(… %d more lines elided for --max-tokens %d)" % (
            n, args.max_tokens)

    best = [lines[0], marker(len(lines) - 1)]
    for k in range(2, len(lines)):
        cand = lines[:k] + [marker(len(lines) - k)]
        if _tokens_of(cand) <= args.max_tokens:
            best = cand
        else:
            break
    return best


# --------------------------------------------------------------------- CLI

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="sgrep",
        description="ripgrep wrapper that condenses results into a ranked, "
                    "deduplicated digest")
    parser.add_argument("pattern")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    parser.add_argument("-i", "--ignore-case", action="store_true")
    parser.add_argument("-F", "--fixed-strings", action="store_true")
    parser.add_argument("-w", "--word-regexp", action="store_true")
    parser.add_argument("-t", "--type", action="append", default=[],
                        metavar="TYPE", help="rg file type filter")
    parser.add_argument("-g", "--glob", action="append", default=[],
                        metavar="GLOB", help="rg glob filter")
    parser.add_argument("-C", "--context", type=int, metavar="N", default=0,
                        help="context lines around each shown match")
    parser.add_argument("--files-only", action="store_true",
                        help="ranked matching-file list only")
    parser.add_argument("--counts-only", action="store_true",
                        help="ranked file list with match counts")
    parser.add_argument("--max-tokens", type=int, metavar="N", default=0,
                        help="cap output; reduces context, then matches per "
                             "file, then files")
    parser.add_argument("--config", metavar="PATH",
                        help="path-class config (default: ./.sgrep.toml)")
    parser.add_argument("--rg", default=os.environ.get("SGREP_RG", "rg"),
                        metavar="BIN", help="ripgrep binary to use")
    parser.add_argument("--version", action="version",
                        version="sgrep %s" % __version__)
    args = parser.parse_args(argv)

    tail = []
    if args.ignore_case:
        tail.append("-i")
    if args.fixed_strings:
        tail.append("-F")
    if args.word_regexp:
        tail.append("-w")
    for t in args.type:
        tail += ["-t", t]
    for g in args.glob:
        tail += ["-g", g]
    if args.context:
        tail += ["-C", str(args.context)]
    tail += ["--", args.pattern] + args.paths

    try:
        weights, extra = load_config(args.config)
        files = run_rg(args.rg, tail)
    except SgrepError as exc:
        print("sgrep: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        return 1

    ranked = rank(files, weights, extra)
    lines = apply_budget(ranked, files, args)
    try:  # matched lines may carry symbols the console encoding lacks
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
