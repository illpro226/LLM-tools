#!/usr/bin/env python3
"""tokq — token cost meter and context linter.

Measures the token cost of files, stdin, and directories, and flags
context-wasteful content (lockfiles, minified bundles, high-entropy blobs,
oversized files) with a cheaper-tool suggestion from the LLM-tools suite.

Modes:
    tokq FILE...            per-file token estimates and a total
    some-cmd | tokq -       meter stdin
    tokq dir PATH           token-weighted tree, heaviest paths first
    tokq lint PATH...       flag wasteful content; --budget N gates scripts

Startup in the fallback (no tiktoken) path must stay under 100 ms, so all
non-stdlib imports are lazy and the heuristic path never reads more than a
small probe of each file.
"""

import argparse
import os
import sys

__version__ = "0.1.1"

BYTES_PER_TOKEN = 3.7  # fallback heuristic divisor

# Directories never worth descending into (shared suite convention).
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", "__pycache__",
    ".venv", "venv", ".tox", ".repoindex", "target", ".next", ".nuxt",
    ".cache", "coverage", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "vendor", ".idea", ".factbook",
}

LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "Cargo.lock", "poetry.lock", "Pipfile.lock", "uv.lock", "composer.lock",
    "Gemfile.lock", "go.sum", "flake.lock", "packages.lock.json",
}

DATA_EXTS = {
    ".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".csv", ".tsv", ".xml",
    ".log", ".toml",
}

MINIFIED_SUFFIXES = (".min.js", ".min.css", ".min.mjs", ".bundle.js")

PROBE_BYTES = 8192        # binary sniff
SAMPLE_BYTES = 65536      # entropy / long-line sniff
LONG_LINE_MAX = 500       # a line longer than this suggests minified
LONG_LINE_AVG = 200       # ... when the average is also this long
ENTROPY_BITS = 5.5        # Shannon bits/byte above which content looks packed
ENTROPY_MIN_SIZE = 1024   # ignore tiny files for the entropy rule
DEFAULT_THRESHOLD = 4000  # lint: tokens above which a file is "big"


# ---------------------------------------------------------------- estimator

class Estimator:
    """Token estimator: tiktoken when available/requested, else bytes/3.7.

    `label` is printed once per run so estimates are never silently mixed.
    """

    def __init__(self, mode="auto"):
        self._enc = None
        if mode in ("auto", "tiktoken"):
            try:
                import tiktoken  # lazy: keeps fallback startup fast
                self._enc = tiktoken.get_encoding("o200k_base")
            except Exception:
                if mode == "tiktoken":
                    raise SystemExit(
                        "tokq: --tokenizer tiktoken requested but tiktoken "
                        "is not importable"
                    )

    @property
    def exact(self):
        return self._enc is not None

    @property
    def label(self):
        if self._enc is not None:
            return "tiktoken (o200k_base)"
        return "heuristic (bytes/%s)" % BYTES_PER_TOKEN

    def from_bytes(self, data):
        if self._enc is not None:
            text = data.decode("utf-8", errors="replace")
            return len(self._enc.encode(text, disallowed_special=()))
        return round(len(data) / BYTES_PER_TOKEN)

    def from_size(self, nbytes):
        """Size-only estimate, used for binary content and the fast path."""
        return round(nbytes / BYTES_PER_TOKEN)

    def file_tokens(self, path):
        """Return (tokens, is_binary). Reads as little as the mode allows."""
        size = os.path.getsize(path)
        with open(path, "rb") as fh:
            probe = fh.read(PROBE_BYTES)
            binary = _looks_binary(probe)
            if binary or not self.exact:
                return self.from_size(size), binary
            data = probe + fh.read()
        return self.from_bytes(data), False


def _looks_binary(probe):
    if not probe:
        return False
    if b"\0" in probe:
        return True
    # High ratio of non-text bytes (outside printable ASCII / common UTF-8).
    text = sum(1 for b in probe if 32 <= b < 127 or b in (9, 10, 13) or b >= 128)
    return (len(probe) - text) / len(probe) > 0.30


def _shannon_entropy(data):
    if not data:
        return 0.0
    from math import log2  # lazy; only lint needs it
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    n = len(data)
    return -sum(c / n * log2(c / n) for c in counts if c)


# ------------------------------------------------------------------ shared

def _fmt_rows(rows):
    """rows: (tokens, text) -> right-aligned token column."""
    width = max((len(str(t)) for t, _ in rows), default=1)
    return ["%*d  %s" % (width, t, text) for t, text in rows]


def _walk(root):
    """Yield (relpath, size) for files under root, pruned and sorted.

    relpath always uses "/" so output is identical across platforms.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            yield rel, os.path.getsize(full)


def _emit(lines, max_tokens):
    """Print lines, truncating to a rough token budget when asked."""
    if max_tokens:
        budget = max_tokens * 4  # bytes, using the same 1 token ~ 4 bytes idea
        used = 0
        for i, line in enumerate(lines):
            used += len(line) + 1
            if used > budget and i < len(lines) - 1:
                print("\n".join(lines[:i]))
                print("(… %d more lines elided for --max-tokens %d)"
                      % (len(lines) - i, max_tokens))
                return
    print("\n".join(lines))


# ------------------------------------------------------------- meter front

def cmd_meter(args):
    est = Estimator(args.tokenizer)
    print("# estimator: %s" % est.label)
    rows = []
    total = 0
    status = 0
    for path in args.paths:
        if path == "-":
            data = sys.stdin.buffer.read()
            binary = _looks_binary(data[:PROBE_BYTES])
            tokens = est.from_size(len(data)) if binary else est.from_bytes(data)
            name = "(stdin)"
        elif os.path.isdir(path):
            print("tokq: %s is a directory (use `tokq dir %s`)" % (path, path),
                  file=sys.stderr)
            status = 2
            continue
        else:
            try:
                tokens, binary = est.file_tokens(path)
            except OSError as exc:
                print("tokq: %s: %s" % (path, exc.strerror or exc),
                      file=sys.stderr)
                status = 2
                continue
            name = path
        if binary:
            name += "  [binary: size-based estimate]"
        rows.append((tokens, name))
        total += tokens
    n = len(rows)
    rows.append((total, "total (%d %s)" % (n, "file" if n == 1 else "files")))
    _emit(_fmt_rows(rows), args.max_tokens)
    return status


# --------------------------------------------------------------- dir front

def cmd_dir(args):
    root = args.path
    if not os.path.isdir(root):
        print("tokq: %s: not a directory" % root, file=sys.stderr)
        return 2
    est = Estimator(args.tokenizer)

    file_tokens = {}
    dir_tokens = {}
    for rel, size in _walk(root):
        full = os.path.join(root, rel)
        try:
            tokens, binary = est.file_tokens(full)
        except OSError:
            continue
        file_tokens[rel] = (tokens, binary)
        d = os.path.dirname(rel)
        while d:
            dir_tokens[d] = dir_tokens.get(d, 0) + tokens
            d = os.path.dirname(d)

    total = sum(t for t, _ in file_tokens.values())
    print("# estimator: %s" % est.label)
    print("# %s: %d tokens across %d files"
          % (root.replace(os.sep, "/"), total, len(file_tokens)))

    entries = [(t, d + "/") for d, t in dir_tokens.items()]
    entries += [(t, rel + ("  [binary]" if b else ""))
                for rel, (t, b) in file_tokens.items()]
    entries.sort(key=lambda e: (-e[0], e[1]))
    shown = entries[: args.top]

    rows = []
    for tokens, name in shown:
        pct = 100.0 * tokens / total if total else 0.0
        rows.append((tokens, "%5.1f%%  %s" % (pct, name)))
    lines = _fmt_rows(rows) if rows else ["(empty)"]
    if len(entries) > len(shown):
        lines.append("(+%d more paths; use --top N)" % (len(entries) - len(shown)))
    _emit(lines, args.max_tokens)
    return 0


# -------------------------------------------------------------- lint front

# Rules are data: (rule id, predicate on a probe dict, message, suggestion).
# First matching rule wins for a file. Predicates see:
#   name, ext, size, tokens, threshold, sample (bytes), max_line, avg_line

def _rule_lockfile(p):
    if p["name"] in LOCKFILE_NAMES:
        return "generated lockfile"

def _rule_minified_name(p):
    if p["name"].endswith(MINIFIED_SUFFIXES):
        return "minified/bundled (by name)"

def _rule_minified_content(p):
    if p["max_line"] > LONG_LINE_MAX and p["avg_line"] > LONG_LINE_AVG:
        return "minified/bundled (max line %d chars)" % p["max_line"]

def _rule_entropy(p):
    if p["size"] >= ENTROPY_MIN_SIZE:
        ent = _shannon_entropy(p["sample"])
        if ent > ENTROPY_BITS:
            return "high-entropy content (%.1f bits/byte; packed or encoded)" % ent

def _rule_big(p):
    if p["tokens"] > p["threshold"]:
        kind = "data file" if p["ext"] in DATA_EXTS else "source file"
        return "large %s (%d tokens > threshold %d)" % (
            kind, p["tokens"], p["threshold"])

RULES = (
    ("LOCKFILE", _rule_lockfile,
     "skip it, or `structo` if you need its shape"),
    ("MINIFIED", _rule_minified_name,
     "skip it: generated, near-zero signal per token"),
    ("MINIFIED", _rule_minified_content,
     "skip it: generated, near-zero signal per token"),
    ("HIGH-ENTROPY", _rule_entropy,
     "skip it, or `structo` if it is structured data"),
    ("BIG-DATA", lambda p: _rule_big(p) if p["ext"] in DATA_EXTS else None,
     "use `structo` for its schema/shape instead of reading it"),
    ("BIG-FILE", _rule_big,
     "use `xread` for targeted excerpts instead of reading it"),
)


def _lint_file(path, est, threshold):
    """Return (tokens, finding|None); finding = (rule_id, message, suggestion)."""
    tokens, binary = est.file_tokens(path)
    with open(path, "rb") as fh:
        sample = fh.read(SAMPLE_BYTES)
    if binary:
        return tokens, ("BINARY", "binary content",
                        "do not read into context")
    lines = sample.splitlines() or [b""]
    probe = {
        "name": os.path.basename(path),
        "ext": os.path.splitext(path)[1].lower(),
        "size": os.path.getsize(path),
        "tokens": tokens,
        "threshold": threshold,
        "sample": sample,
        "max_line": max(len(l) for l in lines),
        "avg_line": len(sample) / len(lines),
    }
    for rule_id, pred, suggestion in RULES:
        msg = pred(probe)
        if msg:
            return tokens, (rule_id, msg, suggestion)
    return tokens, None


def cmd_lint(args):
    est = Estimator(args.tokenizer)
    print("# estimator: %s" % est.label)
    findings = []      # (rule_id, path, tokens, message, suggestion)
    over_budget = []   # (path, tokens)
    grand_total = 0

    for path in args.paths:
        if os.path.isdir(path):
            dir_total = 0
            for rel, _size in _walk(path):
                full = path.rstrip("/\\").replace(os.sep, "/") + "/" + rel
                try:
                    tokens, finding = _lint_file(full, est, args.threshold)
                except OSError:
                    continue
                dir_total += tokens
                if finding:
                    findings.append((finding[0], full, tokens) + finding[1:])
            if dir_total > args.threshold:
                findings.append((
                    "BIG-DIR",
                    path.rstrip("/\\").replace(os.sep, "/") + "/", dir_total,
                    "directory totals %d tokens > threshold %d"
                    % (dir_total, args.threshold),
                    "use `repomap` for an outline instead of reading through it",
                ))
            path_tokens = dir_total
        else:
            try:
                path_tokens, finding = _lint_file(path, est, args.threshold)
            except OSError as exc:
                print("tokq: %s: %s" % (path, exc.strerror or exc),
                      file=sys.stderr)
                return 2
            if finding:
                findings.append((finding[0], path, path_tokens) + finding[1:])
        grand_total += path_tokens
        if args.budget and path_tokens > args.budget:
            over_budget.append((path, path_tokens))

    lines = []
    for rule_id, path, tokens, message, suggestion in findings:
        lines.append("%-12s %s  (%d tokens) — %s; %s"
                     % (rule_id, path, tokens, message, suggestion))
    n = len(findings)
    lines.append("%d finding%s; total %d tokens"
                 % (n, "" if n == 1 else "s", grand_total))
    for path, tokens in over_budget:
        lines.append("BUDGET EXCEEDED: %s is %d tokens > budget %d"
                     % (path, tokens, args.budget))
    _emit(lines, args.max_tokens)
    return 1 if over_budget else 0


# --------------------------------------------------------------------- CLI

def _add_common(parser):
    parser.add_argument("--tokenizer", choices=("auto", "tiktoken", "heuristic"),
                        default=os.environ.get("TOKQ_TOKENIZER", "auto"),
                        help="token counting method (default: auto)")
    parser.add_argument("--max-tokens", type=int, metavar="N", default=0,
                        help="cap tokq's own output at roughly N tokens")
    parser.add_argument("--version", action="version",
                        version="tokq %s" % __version__)


def _pin_utf8():
    """Paths and lint excerpts are echoed verbatim; a cp1252 console default
    would replace anything non-ASCII with `?`."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _pin_utf8()
    argv = sys.argv[1:] if argv is None else list(argv)

    if argv and argv[0] == "dir":
        parser = argparse.ArgumentParser(
            prog="tokq dir", description="token-weighted tree, heaviest first")
        parser.add_argument("path")
        parser.add_argument("--top", type=int, metavar="N", default=40,
                            help="show at most N paths (default 40)")
        _add_common(parser)
        return cmd_dir(parser.parse_args(argv[1:]))

    if argv and argv[0] == "lint":
        parser = argparse.ArgumentParser(
            prog="tokq lint", description="flag context-wasteful content")
        parser.add_argument("paths", nargs="+", metavar="PATH")
        parser.add_argument("--threshold", type=int, metavar="N",
                            default=DEFAULT_THRESHOLD,
                            help="tokens above which a file is 'big' "
                                 "(default %d)" % DEFAULT_THRESHOLD)
        parser.add_argument("--budget", type=int, metavar="N", default=0,
                            help="exit nonzero if any PATH exceeds N tokens")
        _add_common(parser)
        return cmd_lint(parser.parse_args(argv[1:]))

    parser = argparse.ArgumentParser(
        prog="tokq",
        description="token cost meter; also see `tokq dir` and `tokq lint`")
    parser.add_argument("paths", nargs="+", metavar="FILE",
                        help="files to meter, or - for stdin")
    _add_common(parser)
    return cmd_meter(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
