#!/usr/bin/env python3
"""gitbrief — layered, token-cheap views of git state.

    gitbrief                    branch + drift, status+diffstat table
                                (staged/unstaged/untracked), last 5 commits
    gitbrief hunks [FILE...]    diff hunks at 1 context line, vs HEAD
    gitbrief show FILE          the full diff for exactly one file
    gitbrief log [--grep X] [--author X] [-n N]   condensed history
    gitbrief pr BASE            branch summary vs BASE: diffstat, commits,
                                changed top-level symbols (heuristic;
                                Python and JS/TS)

All modes accept `--max-tokens N` (bytes/4) and degrade by whole levels
(table -> counts, context -> headers -> counts, shorter lists) — never by
truncating mid-thought. Layered disclosure is the product shape: the full
diff exists only behind `show FILE`.

Read-only by construction: subprocess `git` plumbing with
`--no-optional-locks`, porcelain output formats only, no libgit binding.
Rename detection is disabled (`--no-renames`) so a rename reads as
delete + add with exact counts.
"""

import argparse
import os
import re
import subprocess
import sys

__version__ = "0.1.1"

DEFAULT_COMMITS = 5
LOG_DEFAULT_N = 10
PY_EXTS = {".py", ".pyi"}
TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}


class GitbriefError(Exception):
    pass


def _est(lines):
    return sum(len(l.encode("utf-8", "replace")) + 1 for l in lines) // 4


def _git(*args, ok_codes=(0,)):
    """Run one read-only git command; every call is a reproducible argv."""
    argv = ["git", "--no-optional-locks", "--no-pager",
            "-c", "color.ui=false", "-c", "core.quotepath=false", *args]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise GitbriefError("git binary not found on PATH")
    if proc.returncode not in ok_codes:
        msg = (proc.stderr or proc.stdout).strip().splitlines()
        raise GitbriefError("git %s: %s" % (args[0], msg[0] if msg else
                                            "exit %d" % proc.returncode))
    return proc.stdout


def fit(levels, budget):
    """Return the first (most detailed) level within budget, else the last.

    Levels are callables returning line lists, ordered most -> least
    detailed. Degradation is by whole levels, never mid-thought.
    """
    lines = levels[0]()
    if not budget or _est(lines) <= budget:
        return lines
    for level in levels[1:]:
        lines = level()
        if _est(lines) <= budget:
            return lines
    return lines


# ---------------------------------------------------------- status gathering

def gather_status():
    out = _git("status", "--porcelain=v2", "--branch",
               "--untracked-files=all", "--no-renames")
    st = {"branch": "(detached)", "upstream": None, "ahead": None,
          "behind": None, "staged": [], "unstaged": [], "untracked": [],
          "unmerged": []}
    for line in out.splitlines():
        if line.startswith("# branch.head "):
            st["branch"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.upstream "):
            st["upstream"] = line.split(" ", 2)[2]
        elif line.startswith("# branch.ab "):
            m = re.match(r"# branch\.ab \+(\d+) -(\d+)", line)
            if m:
                st["ahead"], st["behind"] = int(m.group(1)), int(m.group(2))
        elif line.startswith("1 "):
            parts = line.split(" ", 8)
            xy, path = parts[1], parts[8]
            if xy[0] != ".":
                st["staged"].append({"code": xy[0], "path": path})
            if xy[1] != ".":
                st["unstaged"].append({"code": xy[1], "path": path})
        elif line.startswith("u "):
            parts = line.split(" ", 10)
            st["unmerged"].append({"code": parts[1], "path": parts[10]})
        elif line.startswith("? "):
            st["untracked"].append({"code": "?", "path": line[2:]})
    return st


def _numstat(*extra):
    """path -> (plus, minus, is_binary) from `git diff --numstat`."""
    out = _git("diff", "--numstat", "--no-renames", *extra)
    stats = {}
    for line in out.splitlines():
        plus, minus, path = line.split("\t", 2)
        if plus == "-":
            stats[path] = (0, 0, True)
        else:
            stats[path] = (int(plus), int(minus), False)
    return stats


def _count_lines(path):
    """(line_count, is_binary) for an untracked file, streamed."""
    try:
        n = 0
        last = b"\n"
        with open(path, "rb") as fh:
            head = fh.read(8192)
            if b"\0" in head:
                return 0, True
            while head:
                n += head.count(b"\n")
                last = head[-1:]
                head = fh.read(65536)
        if last != b"\n":
            n += 1
        return n, False
    except OSError:
        return 0, False


def gather_commits(n, grep=None, author=None, rev_range=None):
    args = ["log", "--format=%h %s (%an)", "-n", str(n)]
    if grep:
        args += ["--grep", grep]
    if author:
        args += ["--author", author]
    if rev_range:
        args.append(rev_range)
    out = _git(*args, ok_codes=(0, 128))  # 128: no commits yet
    return out.splitlines()


# ------------------------------------------------------------- default view

def _section(name, entries, stats, show_files):
    plus = sum(stats.get(e["path"], (0, 0, False))[0] for e in entries)
    minus = sum(stats.get(e["path"], (0, 0, False))[1] for e in entries)
    head = "%s (%d file%s, +%d -%d):" % (name, len(entries),
                                         "" if len(entries) == 1 else "s",
                                         plus, minus)
    lines = [head]
    if show_files:
        width = max(len(e["path"]) for e in entries)
        for e in entries:
            p, m, binary = stats.get(e["path"], (0, 0, False))
            counts = "bin" if binary else "+%d -%d" % (p, m)
            lines.append("  %s %-*s  %s" % (e["code"], width, e["path"],
                                            counts))
    return lines


def view_default(budget):
    st = gather_status()
    staged_stats = _numstat("--cached")
    unstaged_stats = _numstat()
    untracked_stats = {}
    for e in st["untracked"]:
        n, binary = _count_lines(e["path"].replace("/", os.sep))
        untracked_stats[e["path"]] = (n, 0, binary)
    commits = gather_commits(DEFAULT_COMMITS)

    def head_lines():
        if st["upstream"] is None:
            drift = "(no upstream)"
        else:
            drift = "→ %s (ahead %d, behind %d)" % (
                st["upstream"], st["ahead"] or 0, st["behind"] or 0)
        return ["branch %s %s" % (st["branch"], drift)]

    def render(show_files, n_commits):
        lines = head_lines()
        sections = (("staged", st["staged"], staged_stats),
                    ("unstaged", st["unstaged"], unstaged_stats),
                    ("unmerged", st["unmerged"], unstaged_stats),
                    ("untracked", st["untracked"], untracked_stats))
        any_files = False
        for name, entries, stats in sections:
            if entries:
                any_files = True
                lines.append("")
                lines += _section(name, entries, stats, show_files)
        if not any_files:
            lines += ["", "working tree clean"]
        if commits and n_commits:
            lines += ["", "last commits:"]
            lines += ["  " + c for c in commits[:n_commits]]
            if n_commits < len(commits):
                lines.append("  (… %d more)" % (len(commits) - n_commits))
        elif not commits:
            lines += ["", "no commits yet"]
        return lines

    return fit([lambda: render(True, DEFAULT_COMMITS),
                lambda: render(False, DEFAULT_COMMITS),
                lambda: render(False, 1),
                lambda: render(False, 0)], budget)


# -------------------------------------------------------------- hunks / show

def _head_exists():
    return _git("rev-parse", "--verify", "-q", "HEAD",
                ok_codes=(0, 1)).strip() != ""


def parse_diff(text):
    """Unified diff -> [{path, hunks: [{header, lines}]}]."""
    files = []
    cur = None
    hunk = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            cur = {"path": None, "hunks": []}
            hunk = None
            files.append(cur)
        elif line.startswith("--- ") and cur is not None:
            if cur["path"] is None and line != "--- /dev/null":
                cur["path"] = line[4:].split("\t")[0][2:]  # strip a/
        elif line.startswith("+++ ") and cur is not None:
            if line != "+++ /dev/null":
                cur["path"] = line[4:].split("\t")[0][2:]  # strip b/
        elif line.startswith("@@") and cur is not None:
            hunk = {"header": line, "lines": []}
            cur["hunks"].append(hunk)
        elif hunk is not None and line[:1] in ("+", "-", " ", "\\"):
            hunk["lines"].append(line)
    return [f for f in files if f["path"]]


def _hunk_counts(f):
    plus = sum(1 for h in f["hunks"] for l in h["lines"]
               if l.startswith("+"))
    minus = sum(1 for h in f["hunks"] for l in h["lines"]
                if l.startswith("-"))
    return plus, minus


def view_hunks(paths, budget):
    if not _head_exists():
        raise GitbriefError("no commits yet; nothing to diff against")
    args = ["diff", "HEAD", "-U1", "--no-renames"]
    if paths:
        args += ["--", *paths]
    files = parse_diff(_git(*args))
    if not files:
        return ["no changes" + (" in %s" % ", ".join(paths)
                                if paths else "")]

    def render(level):
        # level 0: full 1-context hunks; 1: changed lines only;
        # 2: hunk headers only; 3: per-file hunk counts only
        lines = []
        for f in files:
            plus, minus = _hunk_counts(f)
            lines.append("%s (%d hunk%s, +%d -%d)"
                         % (f["path"], len(f["hunks"]),
                            "" if len(f["hunks"]) == 1 else "s",
                            plus, minus))
            if level >= 3:
                continue
            for h in f["hunks"]:
                lines.append("  " + h["header"])
                if level >= 2:
                    continue
                for l in h["lines"]:
                    if level >= 1 and l[:1] == " ":
                        continue
                    lines.append("  " + l)
        if level > 0:
            lines.append("(reduced for --max-tokens: %s)"
                         % {1: "context lines dropped",
                            2: "hunk headers only",
                            3: "per-file counts only"}[level])
        return lines

    return fit([lambda: render(0), lambda: render(1),
                lambda: render(2), lambda: render(3)], budget)


def view_show(path, budget):
    if not _head_exists():
        raise GitbriefError("no commits yet; nothing to diff against")
    out = _git("diff", "HEAD", "--no-renames", "--", path)
    if not out:
        st = gather_status()
        if any(e["path"] == path for e in st["untracked"]):
            raise GitbriefError("%s is untracked; gitbrief show diffs "
                                "tracked files (read it with xread)" % path)
        return ["no changes in %s" % path]
    full = out.splitlines()
    if not budget or _est(full) <= budget:
        return full
    return view_hunks([path], budget)  # too big: degrade to hunks view


# --------------------------------------------------------------------- log

def view_log(n, grep, author, budget):
    commits = gather_commits(n, grep=grep, author=author)
    if not commits:
        return ["no matching commits"]

    def render(k):
        lines = commits[:k]
        if k < len(commits):
            lines.append("(… %d more commits elided for --max-tokens)"
                         % (len(commits) - k))
        return lines

    levels = [lambda k=k: render(k)
              for k in (len(commits), max(len(commits) // 2, 1), 1)]
    return fit(levels, budget)


# ---------------------------------------------------------------------- pr
# Changed-symbol lists come from stdlib extraction of the before/after
# blobs (`git show REV:path`) for Python and JS/TS — see DECISIONS.md
# ADR-005 (supersedes the optional-tree-sitter plan). Heuristic by design.

def _py_symbols(source):
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    return [{"name": n.name, "start": n.lineno, "end": n.end_lineno}
            for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))]


_TS_DECL = re.compile(
    r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?"
    r"(?:async\s+)?(?:class|interface|enum|function\s*\*?)\s+"
    r"([A-Za-z_$][\w$]*)"
    r"|^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
    r"[^=;]*=")


def _strip_ts_noise(line, state):
    out = []
    i, n = 0, len(line)
    while i < n:
        if state["comment"]:
            end = line.find("*/", i)
            if end == -1:
                return "".join(out)
            state["comment"] = False
            i = end + 2
            continue
        ch = line[i]
        if ch == "/" and i + 1 < n and line[i + 1] == "/":
            break
        if ch == "/" and i + 1 < n and line[i + 1] == "*":
            state["comment"] = True
            i += 2
            continue
        if ch in "'\"`":
            quote, j = ch, i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == quote:
                    break
                j += 1
            if j >= n and quote == "`":
                state["template"] = not state["template"]
            i = j + 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _ts_symbols(source):
    syms = []
    stack = []  # open top-level declarations: (symbol, open_depth)
    depth = 0
    state = {"comment": False, "template": False}
    lines = source.splitlines()
    for i, raw in enumerate(lines, 1):
        if state["template"]:
            if "`" in raw:
                state["template"] = False
            continue
        code = _strip_ts_noise(raw, state).strip()
        if depth == 0 and code:
            m = _TS_DECL.match(code)
            if m:
                sym = {"name": m.group(1) or m.group(2),
                       "start": i, "end": i}
                syms.append(sym)
                stack.append((sym, depth))
        depth = max(0, depth + code.count("{") - code.count("}"))
        while stack and depth <= stack[-1][1]:
            stack.pop()[0]["end"] = i
    for sym, _ in stack:  # unterminated: close at EOF
        sym["end"] = len(lines)
    return syms


def _symbols_for(path, source):
    ext = os.path.splitext(path)[1].lower()
    if ext in PY_EXTS:
        return _py_symbols(source)
    if ext in TS_EXTS:
        return _ts_symbols(source)
    return None


def _blob(rev, path):
    out = _git("show", "%s:%s" % (rev, path), ok_codes=(0, 128))
    return out  # empty string when the path does not exist at rev


def _changed_ranges(base, path):
    """(before_ranges, after_ranges) from a -U0 diff, inclusive spans."""
    out = _git("diff", "-U0", "--no-renames", base, "HEAD", "--", path)
    before, after = [], []
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@",
                         out, re.M):
        a, b = int(m.group(1)), int(m.group(2) or "1")
        c, d = int(m.group(3)), int(m.group(4) or "1")
        if b:                # a pure addition touches no before lines
            before.append((a, a + b - 1))
        if d:                # a pure deletion touches no after lines
            after.append((c, c + d - 1))
    return before, after


def _hits(spans, ranges):
    return {s["name"] for s in spans
            if any(r[0] <= s["end"] and r[1] >= s["start"] for r in ranges)}


def changed_symbols(base, paths):
    """[(path, added, modified, removed)], [unanalyzed paths]."""
    results, skipped = [], []
    for path in paths:
        probe = _symbols_for(path, "")
        if probe is None:
            skipped.append(path)
            continue
        before_src = _blob(base, path)
        after_src = _blob("HEAD", path)
        before = _symbols_for(path, before_src) or []
        after = _symbols_for(path, after_src) or []
        before_names = {s["name"] for s in before}
        after_names = {s["name"] for s in after}
        added = sorted(after_names - before_names)
        removed = sorted(before_names - after_names)
        b_ranges, a_ranges = _changed_ranges(base, path)
        touched = _hits(after, a_ranges) | _hits(before, b_ranges)
        modified = sorted(touched & before_names & after_names)
        if added or removed or modified:
            results.append((path, added, modified, removed))
    return results, skipped


def view_pr(base, budget):
    if not _git("rev-parse", "--verify", "-q", base,
                ok_codes=(0, 1)).strip():
        raise GitbriefError("unknown base revision: %s" % base)
    merge_base = _git("merge-base", base, "HEAD").strip()
    stats = _numstat(merge_base, "HEAD")
    commits = gather_commits(1000, rev_range="%s..HEAD" % merge_base)
    paths = sorted(stats)
    symbols, skipped = changed_symbols(merge_base, paths)

    def render(n_commits, per_file, with_symbols):
        lines = ["pr vs %s (merge-base %s)" % (base, merge_base[:7])]
        lines += ["", "commits (%d):" % len(commits)]
        lines += ["  " + c for c in commits[:n_commits]]
        if n_commits < len(commits):
            lines.append("  (… %d more)" % (len(commits) - n_commits))
        plus = sum(v[0] for v in stats.values())
        minus = sum(v[1] for v in stats.values())
        lines += ["", "diffstat (%d file%s, +%d -%d):"
                  % (len(stats), "" if len(stats) == 1 else "s",
                     plus, minus)]
        if per_file and stats:
            width = max(len(p) for p in stats)
            for p in paths:
                pl, mi, binary = stats[p]
                counts = "bin" if binary else "+%d -%d" % (pl, mi)
                lines.append("  %-*s  %s" % (width, p, counts))
        if with_symbols and symbols:
            lines += ["", "changed symbols (heuristic; python/js-ts "
                          "top-level):"]
            for path, added, modified, removed in symbols:
                marks = (["+" + n for n in added]
                         + ["~" + n for n in modified]
                         + ["-" + n for n in removed])
                lines.append("  %s  %s" % (path, " ".join(marks)))
            if skipped:
                lines.append("  (%d file%s not analyzed: %s)"
                             % (len(skipped),
                                "" if len(skipped) == 1 else "s",
                                ", ".join(skipped)))
        elif with_symbols and stats:
            lines += ["", "changed symbols: none detected "
                          "(python/js-ts top-level only)"]
        return lines

    n = len(commits)
    return fit([lambda: render(n, True, True),
                lambda: render(n, True, False),
                lambda: render(n, False, False),
                lambda: render(min(3, n), False, False),
                lambda: render(0, False, False)], budget)


# --------------------------------------------------------------------- CLI

def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--max-tokens", type=int, metavar="N", default=0,
                        help="cap output at roughly N tokens (bytes/4)")
    parser = argparse.ArgumentParser(
        prog="gitbrief", parents=[common],
        description="layered, token-cheap views of git state "
                    "(default: branch, status+diffstat, last commits)")
    parser.add_argument("--version", action="version",
                        version="gitbrief %s" % __version__)
    sub = parser.add_subparsers(dest="cmd")
    p_hunks = sub.add_parser("hunks", parents=[common],
                             help="diff hunks at 1 context line")
    p_hunks.add_argument("paths", nargs="*", metavar="FILE")
    p_show = sub.add_parser("show", parents=[common],
                            help="full diff for one file")
    p_show.add_argument("path", metavar="FILE")
    p_log = sub.add_parser("log", parents=[common],
                           help="condensed history")
    p_log.add_argument("-n", type=int, default=LOG_DEFAULT_N, metavar="N")
    p_log.add_argument("--grep", metavar="PATTERN")
    p_log.add_argument("--author", metavar="PATTERN")
    p_pr = sub.add_parser("pr", parents=[common],
                          help="branch summary vs a base")
    p_pr.add_argument("base", metavar="BASE")
    args = parser.parse_args(argv)

    budget = max(0, args.max_tokens)
    try:
        _git("rev-parse", "--git-dir")  # inside a repo?
        if args.cmd == "hunks":
            lines = view_hunks(args.paths, budget)
        elif args.cmd == "show":
            lines = view_show(args.path, budget)
        elif args.cmd == "log":
            lines = view_log(args.n, args.grep, args.author, budget)
        elif args.cmd == "pr":
            lines = view_pr(args.base, budget)
        else:
            lines = view_default(budget)
    except GitbriefError as exc:
        print("gitbrief: %s" % exc, file=sys.stderr)
        return 2

    try:  # echo file content byte-faithfully, not via a cp1252 console default
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
