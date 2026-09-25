#!/usr/bin/env python3
"""sgrep — token-budgeted search condenser.

A ripgrep wrapper that post-processes `rg --json` results for LLM
consumption: groups matches by file, deduplicates near-identical hits,
ranks files by match count x path-class weight (src > tests > generated),
and hard-caps total output.

    sgrep PATTERN [PATH...]         condensed, ranked digest
    sgrep PATTERN --files-only      matching file list only
    sgrep PATTERN --counts-only     file list with match counts
    sgrep PATTERN --no-collapse     every match line, not one per cluster
    sgrep PATTERN --max-tokens N    reduce: context, then matches per
                                    file, then files shown, in that order

Matching is never reimplemented: ripgrep must be installed (`rg` on PATH,
or point at a binary with --rg / SGREP_RG). Exit codes follow grep: 0
matches found, 1 none, 2 error — including rg failing on some paths after
finding matches in others, in which case the matches are still printed
and the error goes to stderr.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading

__version__ = "0.6.0"

SHOW_ALL_LIMIT = 5    # files with <= this many matching lines show them all
REPRESENTATIVES = 3   # distinct lines shown when a file exceeds the limit
MAX_STORED = 200      # matches kept per file; the count keeps rising past it
STDERR_KEPT = 5       # rg error lines quoted (a regex error is ~4); the
                      # rest are counted, not echoed
# ADR-005: the budget ladder is on by default. An opt-in cap protects only
# the callers who already suspected the output would be large, which is
# exactly the case where they didn't need protecting; the calls that blow
# up a context window are the ones nobody expected to. `--max-tokens 0`
# restores unbounded output.
DEFAULT_MAX_TOKENS = 1500

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
        # rg echoes the separator of the path it was given, so a directory
        # search yields `dir\file.py` while naming the file yields
        # `dir/file.py`. Normalize at ingest: paths are display-and-reference
        # values here (sgrep never reopens them), and stable `path:line`
        # references are a suite invariant.
        path = path.replace("\\", "/")
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
    """Returns (files, errors): `errors` is rg's complaint when it failed on
    some paths but still found matches in others, else "".

    rg exits 2 for *any* error — one unreadable file, one mistyped path
    argument — even when every other path searched fine. Raising there threw
    away every match it had found, so one bad path read as "no output"."""
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
    # Drain stderr while stdout streams. Read only after stdout hit EOF, a
    # stderr pipe holding more than one buffer's worth (rg writes a line per
    # unreadable path) blocks rg mid-write, and both processes wait forever:
    # observed as a hang, not an error.
    err = {"lines": [], "extra": 0}

    def drain():
        for line in proc.stderr:
            if len(err["lines"]) < STDERR_KEPT:
                err["lines"].append(line.rstrip("\r\n"))
            else:
                err["extra"] += 1

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    files = parse_stream(proc.stdout)
    code = proc.wait()
    reader.join()
    stderr = "\n".join(err["lines"]).strip()
    if err["extra"]:
        stderr += "\n(+%d more error lines)" % err["extra"]
    if code not in (0, 1):
        if not files:
            raise SgrepError("rg failed: %s" % (stderr or "exit %d" % code))
        return files, stderr or "rg exited %d" % code
    return files, ""


# ------------------------------------------------------- dedupe and ranking

def normalize(text):
    """Collapse whitespace and digit runs so near-identical hits cluster."""
    return re.sub(r"\d+", "0", " ".join(text.split()))


def select_matches(entry, cap, no_collapse=False):
    """Pick the shown matches for one file.

    Files at or under SHOW_ALL_LIMIT show every match; above it, one
    representative per normalized-content cluster (largest clusters first).
    Every cluster gets one: clustering drops near-duplicates, and size is
    --max-tokens' job, whose ladder sets `cap` (REPRESENTATIVES, then fewer)
    when the full set doesn't fit. A fixed cap of 3 here hid distinct lines
    - different JSON keys, different `def`s - from outputs far under budget
    (docs/known-issues/archive/sgrep-collapse-hides-distinct-json-keys.md).
    `cap` tightens either path under --max-tokens.
    `no_collapse` skips the clustering step: every match is a candidate, in
    line order, for the times the task is "edit each one of these" and a
    representative is the wrong answer.
    Returns (shown [(line, text)] in line order, hidden count).
    """
    count = entry["count"]
    limit = count if cap is None else min(count, cap)
    if no_collapse or count <= SHOW_ALL_LIMIT:
        shown = entry["matches"][:limit]
    else:
        ordered = sorted(_clusters(entry).values(),
                         key=lambda c: (-len(c), c[0][0]))
        shown = sorted(c[0] for c in ordered[:limit])
    return shown, count - len(shown)


def _clusters(entry):
    clusters = {}
    for line, text in entry["matches"]:
        clusters.setdefault(normalize(text), []).append((line, text))
    return clusters


def unshown_clusters(entry, shown):
    """Distinct clusters with no representative shown. Non-zero only when
    --max-tokens capped the file, and then the hidden lines are not all
    "similar" to what's on screen, so the footer must not say they are."""
    seen = {normalize(text) for _, text in shown}
    return sum(1 for key in _clusters(entry) if key not in seen)


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


def render(ranked, files, ctx_radius, cap, nfiles, counts_only, files_only,
           no_collapse=False):
    kept = ranked[:nfiles]
    if files_only:
        # Same marker as the digest: a file list the budget cut short must
        # not read as the complete list of matching files.
        return list(kept) + _dropped_files_note(ranked, kept, files)
    if counts_only:
        rows = [(files[p]["count"], p) for p in kept]
        width = max((len(str(c)) for c, _ in rows), default=1)
        lines = ["%*d  %s" % (width, c, p) for c, p in rows]
        total = sum(files[p]["count"] for p in ranked)
        lines.append("total: %d matches in %d files" % (total, len(ranked)))
        return lines

    out = []
    any_distinct = False
    for path in kept:
        entry = files[path]
        if out:
            out.append("")
        n = entry["count"]
        out.append("== %s (%d match%s) ==" % (path, n, "es"[: 2 * (n != 1)]))
        shown, hidden = select_matches(entry, cap, no_collapse)
        ctx = _context_lines(entry, shown, ctx_radius) if ctx_radius else {}
        match_lines = {line for line, _ in shown}
        # Right-align context line numbers under the widest one in the
        # block so the gutter stays a readable column, not a ragged edge.
        lineno_width = max((len(str(l)) for l in ctx), default=1)
        for line in sorted(match_lines | set(ctx)):
            if line in match_lines:
                text = dict(shown)[line]
                out.append("%s:%d: %s" % (path, line, text))
            else:
                # Context lines make no claim of their own - they exist to
                # situate the match above them, inside a block whose header
                # already names the file. Repeating the path on each one
                # cost more than it bought: measured against raw `rg`, the
                # prefix was most of sgrep's per-line overhead and the
                # reason narrow -C searches printed *more* than the dump
                # they replaced. Match lines keep the full path:line, so
                # every claim line is still followable with xread.
                out.append("%*d- %s" % (lineno_width, line, ctx[line]))
        if hidden:
            distinct = 0 if no_collapse else unshown_clusters(entry, shown)
            if no_collapse:
                out.append("(+%d more)" % hidden)
            elif distinct:
                out.append("(+%d more, %d distinct)" % (hidden, distinct))
                any_distinct = True
            else:
                out.append("(+%d more similar)" % hidden)
    if len(ranked) > len(kept):
        out.append("")
        out += _dropped_files_note(ranked, kept, files)
    if any_distinct:
        out.append("(distinct lines hidden to fit the budget: raise "
                   "--max-tokens or use --no-collapse)")
    return out


def _dropped_files_note(ranked, kept, files):
    if len(ranked) <= len(kept):
        return []
    dropped = ranked[len(kept):]
    return ["(+%d more files with %d matches)"
            % (len(dropped), sum(files[p]["count"] for p in dropped))]


def apply_budget(ranked, files, args):
    """ADR-003: reduce context, then matches per file, then files shown."""
    ctx = args.context
    cap = None
    nfiles = len(ranked)
    counts_only = args.counts_only
    def note(lines):
        """Say so when the budget silently removed something the caller
        asked for. Without this, dropped context reads as absent context:
        the caller concludes the surrounding lines don't exist rather than
        that they were trimmed, and never thinks to raise the cap."""
        if args.no_collapse and cap is not None:
            lines = ["(--no-collapse capped at %d matches/file for "
                     "--max-tokens %d — raise it or 0 for the full list)"
                     % (cap, args.max_tokens)] + lines
        if ctx < args.context:
            return ["(context reduced %d -> %d for --max-tokens %d)"
                    % (args.context, ctx, args.max_tokens)] + lines
        return lines

    while True:
        lines = render(ranked, files, ctx, cap, nfiles, counts_only,
                       args.files_only, args.no_collapse)
        if not args.max_tokens:
            return lines
        if _tokens_of(note(lines)) <= args.max_tokens:
            return note(lines)
        if ctx > 0:
            ctx -= 1
        elif cap is None:
            cap = REPRESENTATIVES
        elif cap > 1:
            cap -= 1
        elif nfiles > 1:
            # The most files that fit. Stepping down one file per render was
            # O(files²): 30 s for a 3,000-file search, nearly 8 minutes for
            # 20,000. Every kept file adds at least a header line — more than
            # the "(+N more files)" marker's digits can shrink — so size grows
            # with the count and a binary search lands on the same answer.
            lo, hi, best = 1, nfiles - 1, None
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = note(render(ranked, files, ctx, cap, mid, counts_only,
                                   args.files_only, args.no_collapse))
                if _tokens_of(cand) <= args.max_tokens:
                    best, lo = cand, mid + 1
                else:
                    hi = mid - 1
            if best is not None:
                return best
            nfiles = 1
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

    # Running byte count, not a re-measure per candidate: the rows being
    # truncated here are one per matching file, so this loop is as long as
    # the search is wide.
    best_k, used = 1, len(lines[0]) + 1
    for k in range(2, len(lines)):
        used += len(lines[k - 1]) + 1
        if (used + len(marker(len(lines) - k)) + 1) // 4 > args.max_tokens:
            break
        best_k = k
    return lines[:best_k] + [marker(len(lines) - best_k)]


# --------------------------------------------------------------------- CLI

def main(argv=None):
    try:  # error text carries the same non-ASCII punctuation as output;
        # a cp1252 console default turns it into invalid UTF-8 bytes
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
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
    # grep muscle memory: match lines always carry path:line, so -n asks for
    # what is already there. Rejecting it cost a round-trip to learn that.
    parser.add_argument("-n", "--line-number", action="store_true",
                        help="accepted and ignored: line numbers are always "
                             "shown")
    parser.add_argument("--files-only", action="store_true",
                        help="ranked matching-file list only")
    parser.add_argument("--counts-only", action="store_true",
                        help="ranked file list with match counts")
    parser.add_argument("--no-collapse", action="store_true",
                        help="show every match line instead of one "
                             "representative per near-identical cluster; "
                             "for \"edit each of these\" work. Still bounded "
                             "by --max-tokens")
    parser.add_argument("--max-tokens", type=int, metavar="N",
                        default=DEFAULT_MAX_TOKENS,
                        help="cap output; reduces context, then matches per "
                             "file, then files (default: %d, 0 = unbounded)"
                             % DEFAULT_MAX_TOKENS)
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
        files, rg_errors = run_rg(args.rg, tail)
    except SgrepError as exc:
        print("sgrep: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        return 1

    ranked = rank(files, weights, extra)
    lines = apply_budget(ranked, files, args)
    try:  # echo matched lines byte-faithfully, not via a cp1252 console default
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("\n".join(lines))
    if rg_errors:
        # grep's convention: an error is exit 2 even when lines matched. The
        # matches above are real; what is missing is whatever rg could not
        # read, so say what that was rather than let the list pass as whole.
        print("sgrep: rg reported errors; matches above cover only the paths "
              "it could search:\n%s" % rg_errors, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
