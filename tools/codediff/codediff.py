#!/usr/bin/env python3
"""codediff — semantic summary of a git diff.

    codediff                    working tree vs HEAD
    codediff --staged           index vs HEAD
    codediff REF                working tree vs REF
    codediff A..B               B vs A          (A...B: B vs merge-base)

Sections: API changes (added/renamed public symbols, signature changes as
old → new), Behavior changes (modified bodies with cheap high-signal
patterns: changed literals/defaults `3 → 5`, added/removed conditionals and
calls), Doc changes (markdown heading deltas — sections added, removed, or
whose body or fenced code moved; structure, not semantics), Removed (deleted
symbols, noting deprecation markers), Tests (one counted line per test file —
nothing depends on a test name, so enumerating them would bury the real
surface change), Mechanical (formatting/comment-only, import reshuffles — one
line per file). Risk is a flat list of deterministic, individually
explainable flags — never an ordinal grade (see DECISIONS.md ADR-002 and
docs/decisions/0002).

Whatever is still left unanalyzed is reported as a share of the whole
change ("4 of 6 files, 61% of changed lines"), so the summary states its
own incompleteness rather than burying it in a trailing parenthetical.

Both sides of every file are parsed with repoindex's pure extraction
library (`extract(path, source)`, repoindex ADR-006), so before-versions
that exist only as git blobs use the exact machinery that built the index.
Read-only git plumbing throughout; deterministic and offline — the compact
delta an LLM narrator would need is exactly the `--json` output.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys

try:
    import tomllib
except ImportError:  # pragma: no cover - Python < 3.11
    tomllib = None

__version__ = "0.5.0"

# ADR-007: the token cap is on by default. A pre-commit summary is read
# while the context already holds the work that produced the diff, so it
# is the worst moment to spend thousands of tokens unasked. `--json` stays
# full (a truncated payload is not parseable); 0 restores unbounded text.
DEFAULT_MAX_TOKENS = 3000

DEFAULT_KEYWORDS = ("auth", "crypto", "payment", "migration",
                    "secret", "password", "credential")
DEFAULT_LARGE_DELTA = 5
DB_RELPATH = os.path.join(".repoindex", "index.db")
CONFIG_NAME = ".codediff.toml"

SECTION_ORDER = ("api", "behavior", "docs", "removed", "tests", "mechanical")
SECTION_TITLES = {"api": "API changes", "behavior": "Behavior changes",
                  "docs": "Doc changes", "removed": "Removed",
                  "tests": "Tests", "mechanical": "Mechanical"}

# Markdown has no symbols to extract, so it used to fall out as "not
# analyzed" — which understates any commit where the doc IS the artifact
# (spec repos, ADRs, a README contract changed alongside the code). The
# pass below reads structure, not semantics: which sections appeared,
# vanished, or had their body move.
_MD_EXTS = (".md", ".markdown", ".mdx")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_MD_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
# Content above the first heading still belongs to somebody.
_MD_PREAMBLE = "(preamble)"

_LIT_RE = re.compile(r"\d+\.\d+|\d+|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"")
_TOKEN_RE = re.compile(
    r"\d+\.\d+|\d+|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|\w+|\S")
_COND_RE = re.compile(r"^\s*(?:if|elif|else if|else\b|switch|case|match|"
                      r"when|\?\.)")
_IMPORT_LINE = {
    "python": re.compile(r"^\s*(?:import\s|from\s)"),
    "javascript": re.compile(r"^\s*(?:import[\s{(\"']|(?:const|let|var)\s.*"
                             r"=\s*require\(|export\s.*\sfrom\s)"),
    "typescript": re.compile(r"^\s*(?:import[\s{(\"']|(?:const|let|var)\s.*"
                             r"=\s*require\(|export\s.*\sfrom\s)"),
    "go": re.compile(r"^\s*(?:import\s|\"[\w./-]+\"$|_?\s*\"[\w./-]+\"$)"),
}
_DEPRECATED_RE = re.compile(r"deprecat", re.IGNORECASE)


class CodediffError(Exception):
    pass


# ------------------------------------------------------------- plumbing ---

def _git_env():
    """Environment for git discovery, with a ceiling on the upward walk.

    Without a ceiling, running this tool anywhere outside a project lets
    git climb all the way to $HOME. On a machine whose home directory is
    itself a repo (a dotfiles checkout - common, and true of this one),
    every such run silently adopts that repo and scans the entire home
    tree: observed as a multi-minute hang, not an error, which is the
    worst failure shape because it looks like the tool is working.

    Stopping at $HOME still finds every repo *below* it normally - the
    walk only stops once it reaches the ceiling. A repo located exactly
    at $HOME is the one case this excludes, so set CODEDIFF_NO_CEILING=1
    (or your own GIT_CEILING_DIRECTORIES, which is respected as-is) when
    that repo is the one you mean.
    """
    env = dict(os.environ)
    if env.get("CODEDIFF_NO_CEILING") or "GIT_CEILING_DIRECTORIES" in env:
        return env
    home = os.path.expanduser("~")
    if home and os.path.isdir(home):
        env["GIT_CEILING_DIRECTORIES"] = home
    return env


def _git(*args, ok_codes=(0,)):
    """Run one read-only git command; every call is a reproducible argv."""
    # diff.relative would re-root and restrict every diff to the cwd, and
    # paths here are joined to the toplevel (gitbrief pins the same).
    argv = ["git", "--no-optional-locks", "--no-pager",
            "-c", "color.ui=false", "-c", "core.quotepath=false",
            "-c", "diff.relative=false", *args]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              env=_git_env())
    except FileNotFoundError:
        raise CodediffError("git binary not found on PATH")
    if proc.returncode not in ok_codes:
        msg = (proc.stderr or proc.stdout).strip().splitlines()
        raise CodediffError("git %s: %s" % (args[0], msg[0] if msg else
                                            "exit %d" % proc.returncode))
    return proc.stdout


def _est(lines):
    return sum(len(l.encode("utf-8", "replace")) + 1 for l in lines) // 4


def fit(levels, budget):
    """First (most detailed) level within budget, else the last.

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


def _load_extract(lib_dir=None):
    """Import repoindex.extract: installed package, CODEDIFF_REPOINDEX (a
    directory containing the `repoindex` package), then the sibling
    checkout, so an uninstalled working copy still works."""
    candidates = []
    if lib_dir:
        candidates.append(lib_dir)
    env = os.environ.get("CODEDIFF_REPOINDEX")
    if env:
        candidates.append(env)
    candidates.append(os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "repoindex")))
    try:
        from repoindex.extract import extract, detect_language
        return extract, detect_language
    except ImportError:
        pass
    for cand in candidates:
        if os.path.isdir(os.path.join(cand, "repoindex")):
            sys.path.insert(0, cand)
            try:
                from repoindex.extract import extract, detect_language
                return extract, detect_language
            except ImportError:
                sys.path.remove(cand)
    raise CodediffError(
        "cannot import repoindex.extract (install repoindex, set "
        "CODEDIFF_REPOINDEX to its checkout dir, or keep the sibling "
        "tools/repoindex checkout)")


# ------------------------------------------------------- target resolve ---

def resolve_target(target, staged):
    """(before_rev, after_rev, label). after_rev None = working tree,
    ':0' = the index."""
    if staged and target:
        raise CodediffError("--staged takes no revision argument")
    if staged:
        return "HEAD", ":0", "staged vs HEAD"
    if not target:
        return "HEAD", None, "working tree vs HEAD"
    if "..." in target:
        a, b = target.split("...", 1)
        a, b = a or "HEAD", b or "HEAD"
        base = _git("merge-base", a, b).strip()
        return base, b, "%s vs merge-base(%s, %s)" % (b, a, b)
    if ".." in target:
        a, b = target.split("..", 1)
        a, b = a or "HEAD", b or "HEAD"
        return a, b, "%s vs %s" % (b, a)
    if not _git("rev-parse", "--verify", "-q", target,
                ok_codes=(0, 1)).strip():
        raise CodediffError("unknown revision: %s" % target)
    return target, None, "working tree vs %s" % target


def changed_files(before_rev, after_rev):
    """[{status, path, old}] from name-status with rename detection on
    (unlike gitbrief: a rename IS the semantic fact here)."""
    if after_rev == ":0":
        out = _git("diff", "--name-status", "-M", "--cached", before_rev)
    elif after_rev:
        out = _git("diff", "--name-status", "-M", before_rev, after_rev)
    else:
        out = _git("diff", "--name-status", "-M", before_rev)
    entries = []
    for line in out.splitlines():
        parts = line.split("\t")
        code = parts[0][:1]
        if code == "R":
            entries.append({"status": "R", "path": parts[2],
                            "old": parts[1]})
        elif code in ("A", "M", "D", "T", "C"):
            entries.append({"status": "M" if code in ("T", "C") else code,
                            "path": parts[1], "old": None})
    if after_rev is None:  # working tree: untracked files are additions
        out = _git("status", "--porcelain=v1", "-uall", "--no-renames")
        for line in out.splitlines():
            # the index db mutates on every implicit update; listing it
            # would make back-to-back runs disagree
            if line.startswith("?? ") and not line[3:].startswith(
                    ".repoindex/"):
                entries.append({"status": "A", "path": line[3:],
                                "old": None})
    entries.sort(key=lambda e: e["path"])
    return entries


def _content(rev, path, root):
    """File content at rev; None = working tree, ':0' = index. Empty
    string when the path does not exist on that side. Git paths are
    root-relative, so worktree reads must resolve against root, not cwd."""
    if rev is None:
        try:
            with open(os.path.join(root, path.replace("/", os.sep)),
                      "r", encoding="utf-8-sig", errors="replace") as fh:
                return fh.read()
        except OSError:
            return ""
    spec = ":%s" % path if rev == ":0" else "%s:%s" % (rev, path)
    out = _git("show", spec, ok_codes=(0, 128))
    # A byte-order mark is U+FEFF to ast.parse: both sides failed to parse,
    # every symbol vanished, and a real change summarized as nothing.
    return out[1:] if out.startswith("﻿") else out


# ------------------------------------------------------ symbol analysis ---

def _local(qualname):
    return qualname.split("::", 1)[1] if "::" in qualname else qualname


def _body_lines(lines, sym):
    return lines[sym.line_start - 1:sym.line_end]


def _norm(body_lines):
    return [l.strip() for l in body_lines if l.strip()]


def _py_code(line):
    """(text, skeleton) of one Python line: the line minus its comment, and
    that with string-literal contents removed. Splitting on a bare `#` cut
    `def paint(color="#fff"):` at the quote, the parens never balanced, and
    the "signature" ran on into the body — so a body edit was reported as a
    changed default."""
    text, skel, quote, i = [], [], None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            text.append(ch)
            if ch == "\\" and i + 1 < len(line):
                text.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
                skel.append(ch)
        elif ch == "#":
            break
        else:
            text.append(ch)
            skel.append(ch)
            if ch in "'\"":
                quote = ch
        i += 1
    return "".join(text).rstrip(), "".join(skel).rstrip()


def _signature(lines, sym, lang):
    """Header text of a symbol, from source the tool already holds (the
    index stores no signatures -- rq ADR-006). Heuristic by design."""
    i = sym.line_start - 1
    if i >= len(lines):
        return ""
    if lang == "python":
        parts, depth = [], 0
        for j in range(i, min(i + 10, len(lines))):
            line, skel = _py_code(lines[j])
            parts.append(line.strip())
            depth += skel.count("(") - skel.count(")")
            if depth <= 0 and skel.endswith(":"):
                break
        return " ".join(p for p in parts if p)
    return lines[i].split("{")[0].strip()


def _mask_literals(text):
    return _LIT_RE.sub("\x00", text)


def _literal_pairs(old_line, new_line):
    """(old, new) literal pairs when the two lines differ only in
    literal-shaped tokens; [] otherwise."""
    old_t = _TOKEN_RE.findall(old_line)
    new_t = _TOKEN_RE.findall(new_line)
    if len(old_t) != len(new_t):
        return []
    pairs = []
    for a, b in zip(old_t, new_t):
        if a == b:
            continue
        if _LIT_RE.fullmatch(a) and _LIT_RE.fullmatch(b):
            pairs.append((a, b))
        else:
            return []
    return pairs


def _calls_in(ef, sym):
    names = {}
    for ref in ef.refs:
        if (ref.kind == "call" and ref.to_name != "<dynamic>"
                and sym.line_start <= ref.line <= sym.line_end):
            names[ref.to_name] = names.get(ref.to_name, 0) + 1
    return names


def _body_details(b_lines, a_lines, ef_b, ef_a, sym_b, sym_a):
    """Cheap high-signal patterns in a modified body: literal changes,
    conditional count delta, call-set delta. Returns (details, line).
    The line anchors at the symbol header: normalized-diff indexes don't
    map exactly back to file lines, and pretending otherwise would break
    the follow-up-with-xread contract."""
    nb = _norm(_body_lines(b_lines, sym_b))
    na = _norm(_body_lines(a_lines, sym_a))
    details = []
    sm = difflib.SequenceMatcher(a=nb, b=na, autojunk=False)
    added, dropped = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace" and (i2 - i1) == (j2 - j1):
            any_pairs = False
            for off in range(i2 - i1):
                pairs = _literal_pairs(nb[i1 + off], na[j1 + off])
                for old, new in pairs[:3]:
                    details.append("%s → %s" % (old, new))
                any_pairs = any_pairs or bool(pairs)
            if not any_pairs:
                dropped += nb[i1:i2]
                added += na[j1:j2]
        elif tag == "delete":
            dropped += nb[i1:i2]
        elif tag == "insert":
            added += na[j1:j2]
    plus_cond = sum(1 for l in added if _COND_RE.match(l))
    minus_cond = sum(1 for l in dropped if _COND_RE.match(l))
    if plus_cond:
        details.append("+%d conditional%s" % (plus_cond,
                                              "" if plus_cond == 1 else "s"))
    if minus_cond:
        details.append("-%d conditional%s" % (minus_cond,
                                              "" if minus_cond == 1 else "s"))
    calls_b = _calls_in(ef_b, sym_b)
    calls_a = _calls_in(ef_a, sym_a)
    new_calls = sorted(n for n in calls_a if n not in calls_b)
    gone_calls = sorted(n for n in calls_b if n not in calls_a)
    if new_calls:
        details.append("+call: " + ", ".join(new_calls[:3]))
    if gone_calls:
        details.append("-call: " + ", ".join(gone_calls[:3]))
    return details, sym_a.line_start


def _is_deprecated(lines, sym):
    lo = max(0, sym.line_start - 3)  # decorators/comments just above
    text = "\n".join(lines[lo:sym.line_end])
    return bool(_DEPRECATED_RE.search(text))


def _display(name, sym):
    return name + "()" if sym.kind in ("func", "method") else name


def _mechanical_kind(before_src, after_src, ef_b, ef_a, lang):
    """'formatting/comment-only', 'imports reshuffled', or None."""
    b_lines = [l.strip() for l in before_src.splitlines()]
    a_lines = [l.strip() for l in after_src.splitlines()]
    changed = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=b_lines, b=a_lines, autojunk=False).get_opcodes():
        if tag != "equal":
            changed += [l for l in b_lines[i1:i2] if l]
            changed += [l for l in a_lines[j1:j2] if l]
    imp_re = _IMPORT_LINE.get(lang)
    if changed and imp_re and all(imp_re.match(l) for l in changed):
        key = lambda ef: sorted((i.module, i.symbol or "", i.alias or "")
                                for i in ef.imports)
        if key(ef_b) == key(ef_a):
            return "imports reshuffled"
    if lang == "python":
        import ast
        try:
            if ast.dump(ast.parse(before_src)) == ast.dump(
                    ast.parse(after_src)):
                return "formatting/comment-only"
        except SyntaxError:
            return None
        return None
    strip = lambda src: re.sub(r"\s+", "", re.sub(
        r"//[^\n]*|/\*.*?\*/", "", src, flags=re.S))
    if strip(before_src) == strip(after_src):
        return "formatting/comment-only"
    return None


def _is_test_symbol(name, sym):
    leaf = name.split(".")[-1]
    return sym.kind == "func" and leaf.lower().startswith("test")


def _test_summary(before, after, b_lines, a_lines):
    """One line's worth of counts for a test file. Nothing depends on a test
    name, so enumerating them would bury the change's real surface under
    noise that grows with how well the change is tested."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = [n for n in sorted(set(before) & set(after))
               if _norm(_body_lines(b_lines, before[n]))
               != _norm(_body_lines(a_lines, after[n]))]

    def split(names, table):
        tests = [n for n in names if _is_test_symbol(n, table[n])]
        return len(tests), len(names) - len(tests)

    parts = []
    for label, names, table in (("+", added, after), ("-", removed, before),
                                ("~", changed, after)):
        n_test, n_helper = split(names, table)
        if n_test:
            parts.append("%s%d test%s" % (label, n_test,
                                          "" if n_test == 1 else "s"))
        if n_helper:
            parts.append("%s%d helper%s" % (label, n_helper,
                                            "" if n_helper == 1 else "s"))
    return ", ".join(parts)


def analyze_file(entry, before_src, after_src, extract, lang, out):
    """Classify one changed file into the sections (dict lists in `out`).
    Every entry: {text, path, line, public}."""
    path = entry["path"]

    def add(section, text, line, public=False):
        out[section].append({"text": text, "path": path, "line": line,
                             "public": public})

    if entry["status"] == "R":
        add("mechanical", "file renamed from %s" % entry["old"], 1)
        if _norm(before_src.splitlines()) == _norm(after_src.splitlines()):
            return
    # Same path label on both sides so qualnames join (repoindex ADR-006:
    # deterministic qualnames are the before/after key). Extracted once:
    # the mechanical check used to parse both sides and then throw them away.
    ef_b = extract(path, before_src, lang)
    ef_a = extract(path, after_src, lang)
    if entry["status"] == "M":
        kind = _mechanical_kind(before_src, after_src, ef_b, ef_a, lang)
        if kind:
            add("mechanical", kind, 1)
            return
    b_lines = before_src.splitlines()
    a_lines = after_src.splitlines()
    before = {_local(s.qualname): s for s in ef_b.symbols}
    after = {_local(s.qualname): s for s in ef_a.symbols}

    if _is_test_path(path):
        summary = _test_summary(before, after, b_lines, a_lines)
        add("tests", summary or "changed outside any test symbol", 1)
        return

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    common = sorted(set(before) & set(after))

    # renames: same kind, same nontrivial body below the header
    renamed = {}  # old -> new
    for old in list(removed):
        for new in list(added):
            if new in renamed.values():
                continue
            sb, sa = before[old], after[new]
            if sb.kind != sa.kind or sb.kind == "const":
                continue
            body_b = _norm(_body_lines(b_lines, sb)[1:])
            body_a = _norm(_body_lines(a_lines, sa)[1:])
            if body_b and body_b == body_a:
                renamed[old] = new
                break
    for old, new in sorted(renamed.items()):
        sa = after[new]
        public = before[old].exported or sa.exported
        add("api", "~ %s → %s (renamed)" % (old, new), sa.line_start,
            public=public)
        removed.remove(old)
        added.remove(new)

    for name in added:
        sym = after[name]
        label = "+ %s (%s)" % (_display(name, sym), sym.kind)
        if sym.exported:
            add("api", label, sym.line_start, public=True)
        else:
            add("behavior", label + " (private)", sym.line_start)

    for name in removed:
        sym = before[name]
        notes = []
        if sym.exported:
            notes.append("public")
        if _is_deprecated(b_lines, sym):
            notes.append("was deprecated")
        suffix = " (%s)" % ", ".join([sym.kind] + notes)
        add("removed", "- %s%s" % (_display(name, sym), suffix),
            sym.line_start, public=sym.exported)

    for name in common:
        sb, sa = before[name], after[name]
        if _norm(_body_lines(b_lines, sb)) == _norm(_body_lines(a_lines, sa)):
            continue
        if sa.kind == "const":
            details, line = _body_details(b_lines, a_lines, ef_b, ef_a,
                                          sb, sa)
            add("behavior", "~ %s  %s" % (name, ", ".join(details)
                                          if details else "value changed"),
                line)
            continue
        sig_b = _signature(b_lines, sb, lang)
        sig_a = _signature(a_lines, sa, lang)
        sig_changed = False
        if sig_b != sig_a:
            if _mask_literals(sig_b) != _mask_literals(sig_a):
                section = "api" if (sa.exported or sb.exported) else "behavior"
                add(section, "~ %s → %s" % (sig_b, sig_a), sa.line_start,
                    public=sa.exported or sb.exported)
                sig_changed = True
            else:
                pairs = _literal_pairs(sig_b, sig_a)
                for old, new in pairs[:3]:
                    add("behavior", "~ %s  default %s → %s"
                        % (_display(name, sa), old, new), sa.line_start)
                sig_changed = bool(pairs)
        # python signatures can span lines; compare below the full header
        skip_b = _sig_line_count(b_lines, sb) if lang == "python" else 1
        skip_a = _sig_line_count(a_lines, sa) if lang == "python" else 1
        header_only = (_norm(_body_lines(b_lines, sb)[skip_b:])
                       == _norm(_body_lines(a_lines, sa)[skip_a:]))
        if sig_changed and header_only:
            continue
        details, line = _body_details(b_lines, a_lines, ef_b, ef_a, sb, sa)
        add("behavior", "~ %s  %s" % (_display(name, sa),
                                      ", ".join(details) if details
                                      else "body changed"), line)


def _is_markdown(path):
    return path.lower().endswith(_MD_EXTS)


def _md_sections(src):
    """[{key, title, line, body, code}] for one markdown file.

    `key` carries the heading level and an occurrence index so two `##
    Usage` sections under different parents stay distinct. `code` is the
    section's fenced-block lines, tracked separately: a changed command in
    a README or AGENTS.md block is executable content, and the
    highest-value markdown edit to surface.
    """
    sections, seen = [], {}
    cur = {"key": _MD_PREAMBLE, "title": _MD_PREAMBLE, "line": 1,
           "body": [], "code": []}
    fence = None
    for i, line in enumerate(src.splitlines(), 1):
        m = _MD_FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            cur["code"].append(line.strip())
            continue
        if fence is not None:
            cur["code"].append(line.strip())
            continue
        h = _MD_HEADING_RE.match(line)
        if not h:
            if line.strip():
                cur["body"].append(line.strip())
            continue
        if cur["body"] or cur["code"] or cur["key"] != _MD_PREAMBLE:
            sections.append(cur)
        level, title = len(h.group(1)), h.group(2).strip()
        n = seen[(level, title)] = seen.get((level, title), 0) + 1
        cur = {"key": "%d/%s/%d" % (level, title, n), "title": title,
               "line": i, "body": [], "code": []}
    if cur["body"] or cur["code"] or cur["key"] != _MD_PREAMBLE:
        sections.append(cur)
    return sections


def analyze_markdown(entry, before_src, after_src, out):
    """Heading-level deltas for one markdown file, into the docs section."""
    path = entry["path"]
    before = {s["key"]: s for s in _md_sections(before_src)}
    after = {s["key"]: s for s in _md_sections(after_src)}

    def add(text, line):
        out["docs"].append({"text": text, "path": path, "line": line})

    # A wholly new or deleted document is one fact, not one fact per
    # heading — the same reason Tests are counted rather than enumerated
    # (archive/codediff-enumerates-every-new-test.md).
    if not before and after:
        add("+ new document, %d section%s"
            % (len(after), "" if len(after) == 1 else "s"), 1)
        return
    if before and not after:
        add("- document emptied (%d section%s)"
            % (len(before), "" if len(before) == 1 else "s"), 1)
        return

    for key, sec in after.items():
        if key in before:
            continue
        n = len(sec["body"])
        add("+ %s (new section%s)"
            % (sec["title"],
               ", %d line%s" % (n, "" if n == 1 else "s") if n else ""),
            sec["line"])
    for key, sec in before.items():
        if key not in after:
            add("- %s (section removed)" % sec["title"], sec["line"])
    for key, sec in after.items():
        old = before.get(key)
        if old is None:
            continue
        body_moved = old["body"] != sec["body"]
        code_moved = old["code"] != sec["code"]
        if not (body_moved or code_moved):
            continue
        what = []
        if code_moved:
            # Named first and named plainly: a changed fenced block is a
            # changed command, which is the one markdown edit that can
            # break a reader who copies it.
            what.append("fenced code changed")
        if body_moved:
            delta = len(sec["body"]) - len(old["body"])
            what.append("body changed" if not delta
                        else "body %+d line%s" % (delta,
                                                  "" if abs(delta) == 1
                                                  else "s"))
        add("~ %s (%s)" % (sec["title"], ", ".join(what)), sec["line"])


def _changed_line_counts(before_rev, after_rev):
    """{path: added + deleted}, mirroring changed_files' rev selection.

    Git's own accounting rather than a second diff of our own, so the
    share a summary reports about itself matches what any other tool
    would say about the same commit. Binary files (`-\\t-`) are omitted.
    """
    if after_rev == ":0":
        out = _git("diff", "--numstat", "-M", "--cached", before_rev)
    elif after_rev:
        out = _git("diff", "--numstat", "-M", before_rev, after_rev)
    else:
        out = _git("diff", "--numstat", "-M", before_rev)
    counts = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or parts[0] == "-":
            continue
        try:
            counts[parts[-1]] = int(parts[0]) + int(parts[1])
        except ValueError:
            continue
    return counts


def _unanalyzed_note(unanalyzed, entries, counts, max_names=None):
    """The 'not analyzed' line, stated as a share of the whole change.

    A trailing parenthetical listing four filenames reads as a footnote;
    '4 of 6 files, 61% of changed lines' states the summary's own
    incompleteness, which is the thing the reader needs. `max_names` caps
    the list on reduced rungs: named in full, a diff of 3,000 assets or
    generated files kept the floor O(files) and the budget unreachable.
    """
    if not unanalyzed:
        return []
    total_lines = sum(counts.get(e["path"], 0) for e in entries)
    skipped_lines = sum(counts.get(p, 0) for p in unanalyzed)
    share = ""
    if total_lines and skipped_lines:
        share = ", %d%% of changed lines" % round(
            100.0 * skipped_lines / total_lines)
    names = ", ".join(unanalyzed)
    if max_names is not None and len(unanalyzed) > max_names:
        names = ", ".join(unanalyzed[:max_names]) + ", … (+%d more)" % (
            len(unanalyzed) - max_names)
    return ["", "%d of %d file%s%s not analyzed: %s"
            % (len(unanalyzed), len(entries),
               "" if len(entries) == 1 else "s", share, names)]


def _sig_line_count(lines, sym):
    """How many source lines the header spans (python multi-line defs)."""
    i = sym.line_start - 1
    depth = 0
    for j in range(i, min(i + 10, len(lines))):
        skel = _py_code(lines[j])[1]
        depth += skel.count("(") - skel.count(")")
        if depth <= 0 and skel.endswith(":"):
            return j - i + 1
    return 1


# ----------------------------------------------------------- risk flags ---

def load_config(root):
    cfg = {"keywords": list(DEFAULT_KEYWORDS),
           "large_delta": DEFAULT_LARGE_DELTA}
    path = os.path.join(root, CONFIG_NAME)
    if not os.path.isfile(path) or tomllib is None:
        return cfg
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CodediffError("%s: %s" % (CONFIG_NAME, exc))
    risk = data.get("risk", {})
    if isinstance(risk.get("keywords"), list):
        cfg["keywords"] = [str(k).lower() for k in risk["keywords"]]
    if isinstance(risk.get("large_delta"), int):
        cfg["large_delta"] = risk["large_delta"]
    return cfg


def ensure_fresh(root, repoindex_cmd=None):
    """Run `repoindex update` so the tests table is never stale. Same
    resolution order as rq/testmap: flag, env, PATH, sibling checkout."""
    cmd = repoindex_cmd or os.environ.get("CODEDIFF_REPOINDEX_BIN") \
        or "repoindex"
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
    # Pinned like every other capture (INVARIANTS.md): decoded with the
    # console default, a non-ASCII path in repoindex's output raised
    # UnicodeDecodeError here, inside a flag the caller never asked about.
    proc = subprocess.run(argv, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode == 0


_TEST_DIRS = {"tests", "test", "__tests__"}


def _is_test_path(path):
    base = os.path.basename(path)
    # `test/` (mocha, Maven's src/test) and `__tests__/` (jest's default)
    # hold tests whatever their files are called; only `tests/` counted,
    # so their suites were analyzed as source and flagged as untested.
    dirs = path.replace(os.sep, "/").split("/")[:-1]
    return (base.startswith("test_") or base.endswith("_test.py")
            or ".test." in base or ".spec." in base
            or base.endswith("_test.go")
            or any(d in _TEST_DIRS for d in dirs))


def risk_flags(out, entries, root, cfg, no_update, repoindex_cmd):
    """Deterministic, individually explainable flags. Each is one claim
    with its evidence; there is deliberately no aggregate grade."""
    flags = []
    notes = []
    changed_paths = [e["path"] for e in entries]
    all_names = changed_paths + [e["old"] for e in entries if e["old"]]

    hits = {}
    for kw in cfg["keywords"]:
        for p in sorted(set(all_names)):
            if kw in p.lower():
                hits.setdefault(kw, p)
                break
    for kw in sorted(hits):
        flags.append({"text": "sensitive path: '%s'" % kw,
                      "path": hits[kw], "line": 1})

    public = [e for sec in ("api", "removed") for e in out[sec]
              if e["public"]]
    if public:
        flags.append({"text": "public API surface touched (%d change%s)"
                      % (len(public), "" if len(public) == 1 else "s"),
                      "path": public[0]["path"], "line": public[0]["line"]})

    n_behavior = len(out["behavior"])
    if n_behavior >= cfg["large_delta"]:
        flags.append({"text": "large behavior delta (%d change%s, "
                      "threshold %d)" % (n_behavior,
                      "" if n_behavior == 1 else "s", cfg["large_delta"]),
                      "path": out["behavior"][0]["path"],
                      "line": out["behavior"][0]["line"]})

    source_changed = sorted({e["path"] for sec in ("api", "behavior",
                                                   "removed")
                             for e in out[sec]
                             if not _is_test_path(e["path"])})
    tests_changed = {p for p in changed_paths if _is_test_path(p)}
    if source_changed:
        db_path = os.path.join(root, DB_RELPATH)
        if os.path.exists(db_path):
            if not no_update:
                ensure_fresh(root, repoindex_cmd)
            uri = "file:%s?mode=ro" % db_path.replace(os.sep, "/")
            conn = sqlite3.connect(uri, uri=True)
            try:
                stale, uncovered = [], []
                for src in source_changed:
                    rows = conn.execute(
                        "SELECT DISTINCT test_file FROM tests "
                        "WHERE target_file = ? ORDER BY test_file",
                        (src,)).fetchall()
                    covering = {r[0] for r in rows}
                    if not covering:
                        uncovered.append(src)
                    elif not covering & tests_changed:
                        stale.append(src)
                if stale:
                    flags.append({"text": "matching tests not changed "
                                  "(%d file%s)" % (len(stale),
                                  "" if len(stale) == 1 else "s"),
                                  "path": stale[0], "line": 1})
                if uncovered:
                    flags.append({"text": "no known tests cover %d changed "
                                  "file%s" % (len(uncovered),
                                  "" if len(uncovered) == 1 else "s"),
                                  "path": uncovered[0], "line": 1})
            finally:
                conn.close()
        else:
            notes.append("note: no .repoindex index; test-coverage flags "
                         "unavailable (run `repoindex build`)")
    return flags, notes


# -------------------------------------------------------------- render ---

def _render_section(lines, title, items, width, collapse=None,
                    strip_detail=False):
    if not items:
        return
    lines.append("")
    if collapse == "count":
        lines.append("%s: %d (collapsed for --max-tokens)"
                     % (title, len(items)))
        return
    lines.append(title)
    for e in items:
        text = e["text"]
        if strip_detail and "  " in text:
            text = text.split("  ")[0]
        ref = "%s:%d" % (e["path"], e["line"])
        lines.append("  %-*s  %s" % (width, text, ref))


def render(label, entries, out, flags, notes, unanalyzed, counts, budget):
    def build(mech_count=False, strip_detail=False, counts_only=False,
              reduced=None):
        lines = ["codediff: %s (%d file%s)" % (label, len(entries),
                 "" if len(entries) == 1 else "s")]
        width = max((len(e["text"]) for sec in SECTION_ORDER
                     for e in out[sec]), default=0)
        if strip_detail:
            width = min(width, 40)
        for sec in SECTION_ORDER:
            collapse = None
            if counts_only or (mech_count and sec == "mechanical"):
                collapse = "count"
            _render_section(lines, SECTION_TITLES[sec], out[sec], width,
                            collapse=collapse,
                            strip_detail=strip_detail and sec == "behavior")
        lines += _unanalyzed_note(unanalyzed, entries, counts,
                                  max_names=5 if reduced else None)
        lines.append("")
        if flags:
            lines.append("Risk flags (%d)" % len(flags))
            fwidth = max(len(f["text"]) for f in flags)
            for f in flags:
                lines.append("  %-*s  %s:%d" % (fwidth, f["text"],
                                                f["path"], f["line"]))
        else:
            lines.append("Risk flags: none")
        for n in notes:
            lines.append(n)
        if reduced:
            lines.append("(reduced for --max-tokens: %s)" % reduced)
        return lines

    return fit([
        lambda: build(),
        lambda: build(mech_count=True,
                      reduced="mechanical collapsed to a count"),
        lambda: build(mech_count=True, strip_detail=True,
                      reduced="behavior details dropped"),
        lambda: build(counts_only=True,
                      reduced="per-section counts only"),
    ], budget)


def to_json(label, entries, out, flags, notes, unanalyzed, counts):
    doc = {"target": label, "files": len(entries)}
    for sec in SECTION_ORDER:
        doc[sec] = [{"text": e["text"], "path": e["path"],
                     "line": e["line"]} for e in out[sec]]
    doc["risk_flags"] = [{"text": f["text"], "path": f["path"],
                          "line": f["line"]} for f in flags]
    doc["unanalyzed"] = unanalyzed
    # The narrator needs the summary's incompleteness as a number, not as
    # a list it would have to weigh for itself.
    total = sum(counts.get(e["path"], 0) for e in entries)
    skipped = sum(counts.get(p, 0) for p in unanalyzed)
    doc["unanalyzed_share"] = {
        "files": len(unanalyzed), "total_files": len(entries),
        "changed_lines": skipped, "total_changed_lines": total,
        "percent_of_changed_lines": (round(100.0 * skipped / total)
                                     if total else 0)}
    doc["notes"] = notes
    return json.dumps(doc, indent=1, sort_keys=True)


# ------------------------------------------------------------------ CLI ---

def main(argv=None):
    try:  # error text carries the same non-ASCII punctuation as output;
        # a cp1252 console default turns it into invalid UTF-8 bytes
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        prog="codediff",
        description="semantic summary of a git diff: API / behavior / "
                    "removed / mechanical, plus explainable risk flags")
    parser.add_argument("target", nargs="?", metavar="REF|A..B",
                        help="revision or range (default: worktree vs HEAD)")
    parser.add_argument("--staged", action="store_true",
                        help="diff the index against HEAD")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="structured output for tooling (always full; "
                             "--max-tokens applies to text output)")
    parser.add_argument("--max-tokens", type=int, metavar="N",
                        default=DEFAULT_MAX_TOKENS,
                        help="cap output at roughly N tokens (bytes/4) "
                             "(default: %d, 0 = unbounded; --json is "
                             "always full)" % DEFAULT_MAX_TOKENS)
    parser.add_argument("--no-update", action="store_true",
                        help="skip the implicit `repoindex update` before "
                             "the test-coverage flag")
    parser.add_argument("--repoindex", metavar="CMD", default=None,
                        help="repoindex binary for the implicit update "
                             "(default: PATH or the sibling checkout; env "
                             "CODEDIFF_REPOINDEX_BIN)")
    parser.add_argument("--repoindex-lib", metavar="DIR", default=None,
                        help="directory containing the repoindex package "
                             "(default: installed, env CODEDIFF_REPOINDEX, "
                             "or the sibling checkout)")
    parser.add_argument("--version", action="version",
                        version="codediff %s" % __version__)
    args = parser.parse_args(argv)

    try:
        root = _git("rev-parse", "--show-toplevel").strip()
        extract, detect_language = _load_extract(args.repoindex_lib)
        before_rev, after_rev, label = resolve_target(args.target,
                                                      args.staged)
        entries = changed_files(before_rev, after_rev)
        if not entries:
            print("no changes (%s)" % label)
            return 0

        out = {sec: [] for sec in SECTION_ORDER}
        unanalyzed = []
        # Untracked files never appear in numstat, so their lines would be
        # missing from both halves of the share and quietly flatter it.
        sizes = {}
        for entry in entries:
            before_path = entry["old"] or entry["path"]
            before_src = ("" if entry["status"] == "A"
                          else _content(before_rev, before_path, root))
            after_src = ("" if entry["status"] == "D"
                         else _content(after_rev, entry["path"], root))
            sizes[entry["path"]] = (len(after_src.splitlines())
                                    or len(before_src.splitlines()))
            lang = detect_language(entry["path"]) or \
                detect_language(before_path)
            if "\0" in before_src or "\0" in after_src:
                unanalyzed.append(entry["path"])
                continue
            if lang is None:
                # Markdown gets a structural pass instead of a symbol one.
                if _is_markdown(entry["path"]):
                    analyze_markdown(entry, before_src, after_src, out)
                else:
                    unanalyzed.append(entry["path"])
                continue
            analyze_file(entry, before_src, after_src, extract, lang, out)
        for sec in SECTION_ORDER:
            out[sec].sort(key=lambda e: (e["path"], e["line"], e["text"]))

        counts = _changed_line_counts(before_rev, after_rev)
        for path, n in sizes.items():
            counts.setdefault(path, n)
        cfg = load_config(root)
        flags, notes = risk_flags(out, entries, root, cfg,
                                  args.no_update, args.repoindex)

        if args.as_json:
            text = to_json(label, entries, out, flags, notes,
                           unanalyzed, counts)
        else:
            text = "\n".join(render(label, entries, out, flags, notes,
                                    unanalyzed, counts,
                                    max(0, args.max_tokens)))
    except CodediffError as exc:
        print("codediff: %s" % exc, file=sys.stderr)
        return 2

    try:  # echo file content byte-faithfully, not via a cp1252 console default
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
