#!/usr/bin/env python3
"""repomap — compact repository map generator.

Prints an orientation view of a codebase in one screen:

    repomap [DIR]            pruned directory tree + per-file symbol
                             outlines, most-referenced files first
    repomap --focus PATH     outline one file or subtree; every other
                             file collapses to `path [refs N] (K symbols)`
                             and the tree elsewhere goes shallower
    repomap --max-tokens N   stay under a token budget (bytes/4),
                             degrading in order: drop low-rank file
                             outlines -> drop signatures -> tree only

Every symbol line carries `path:line` so an entry can be followed up with
`xread PATH --symbol NAME`. Output is plain text, deterministic, and
stable across runs. Ranking is heuristic (identifier reference counts
across the repo's own source files) and is labeled as such.

Stdlib only (see DECISIONS.md ADR-004): Python via `ast`; JS/TS and
C/C++ via depth-tracking line scanners; Go and Rust via column-0
declaration patterns; other languages via a generic declaration regex.
All non-Python extraction is top-level-only and best-effort by design.
"""

import argparse
import collections
import fnmatch
import os
import re
import sys

__version__ = "0.4.0"

# ADR-007: the token cap is on by default. An orientation map is read at
# the start of a task, when context is most valuable; 3000 covers a
# typical repo's tree plus outlines, and 0 restores unbounded output.
DEFAULT_MAX_TOKENS = 3000

PY_EXTS = {".py", ".pyi"}
TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
GO_EXTS = {".go"}
RS_EXTS = {".rs"}
C_EXTS = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx", ".cu"}
GENERIC_EXTS = {
    ".rb", ".php", ".lua", ".sh", ".bash", ".zsh", ".pl", ".pm", ".kt",
    ".kts", ".java", ".cs", ".swift", ".scala", ".ex", ".exs", ".erl",
    ".hs", ".ml", ".r", ".jl", ".zig", ".nim", ".d", ".dart", ".groovy",
    ".ps1", ".psm1", ".vb", ".tcl", ".m", ".mm",
}

SKIP_DIRS = {
    "node_modules", "__pycache__", "dist", "build", "target", "vendor",
    "venv", "site-packages", "bower_components", "coverage", "htmlcov",
}
KEEP_DOT_DIRS = {".github"}

SIG_CAP = 100        # max chars of a rendered signature
DOC_CAP = 80         # max chars of a docstring/comment first line
SIZE_CAP = 1_000_000  # bytes; larger files are listed in the tree only
FULL_FLOOR = 5       # min outlines kept at full detail before dropping sigs
MIN_NAME = 3         # identifiers shorter than this don't count for ranking

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


class RepomapError(Exception):
    pass


def _est(lines):
    """Token estimate: bytes/4 including newlines (PRD convention)."""
    return sum(len(l.encode("utf-8", "replace")) + 1 for l in lines) // 4


def _clean_sig(text, cap=SIG_CAP):
    sig = " ".join(text.split()).rstrip("{; ").strip()
    if sig.endswith("=>"):
        sig = sig[:-2].rstrip()
    if len(sig) > cap:
        sig = sig[:cap - 1] + "…"
    return sig


def _doc_above(lines, lineno, prefixes):
    """First line of the contiguous comment block directly above lineno."""
    block = []
    j = lineno - 2
    allow_block = "/*" in prefixes
    while j >= 0:
        s = lines[j].strip()
        if s and (any(s.startswith(p) for p in prefixes)
                  or (allow_block and s.endswith("*/"))):
            block.append(s)
            j -= 1
        else:
            break
    for s in reversed(block):
        text = s
        for tok in ("/**", "/*", "///", "//!", "//", "--", "#", ";"):
            if text.startswith(tok):
                text = text[len(tok):]
                break
        if text.startswith("*"):
            text = text[1:]
        if text.endswith("*/"):
            text = text[:-2]
        text = text.strip()
        if text and not set(text) <= set("-=*~ "):
            return text[:DOC_CAP]
    return ""


def _sym(line, kind, name, sig, doc):
    return {"line": line, "kind": kind, "name": name, "sig": sig, "doc": doc}


# ----------------------------------------------------------- python (ast)

def _py_sig(lines, lineno):
    """Signature text from the def/class line up to the block colon."""
    out = []
    depth = 0
    for line in lines[lineno - 1:lineno + 24]:
        for ch in line:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == ":" and depth <= 0:
                return _clean_sig("".join(out))
            out.append(ch)
        out.append(" ")
    return _clean_sig("".join(out))


def _py_top_level(ast, node):
    """Module-level defs, including those under `if`/`try`/`with` — a
    platform- or import-conditional def is still the module's name."""
    blocks = tuple(getattr(ast, n) for n in ("If", "Try", "TryStar",
                                              "ExceptHandler", "With",
                                              "AsyncWith")
                   if hasattr(ast, n))
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef)):
            yield child
        elif isinstance(child, blocks):
            yield from _py_top_level(ast, child)


def extract_python(source, lines):
    import ast
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    syms = []
    for node in _py_top_level(ast, tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "func"
            doc = (ast.get_docstring(node) or "").strip().splitlines()
            syms.append(_sym(node.lineno, kind, node.name,
                             _py_sig(lines, node.lineno),
                             doc[0][:DOC_CAP] if doc else ""))
    return syms


# ------------------------------------------- js/ts and c/c++ line scanners
# Strings and comments are stripped so brace counting sees only code;
# declarations are recognized only at brace depth 0 (top level).

def _strip_c_noise(line, state):
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


_TS_DECLS = (
    ("class", re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?"
        r"class\s+([A-Za-z_$][\w$]*)")),
    ("interface", re.compile(
        r"^(?:export\s+)?(?:declare\s+)?interface\s+([A-Za-z_$][\w$]*)")),
    ("enum", re.compile(
        r"^(?:export\s+)?(?:declare\s+)?(?:const\s+)?"
        r"enum\s+([A-Za-z_$][\w$]*)")),
    ("func", re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?"
        r"function\s*\*?\s*([A-Za-z_$][\w$]*)")),
    ("func", re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
        r"[^=;]*=\s*(?:async\b[^=;]*)?(?:\([^)]*\)?|[A-Za-z_$][\w$]*)"
        r"\s*(?::[^=]*)?=>")),
    ("func", re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
        r"\s*=\s*(?:async\s+)?function\b")),
    ("type", re.compile(
        r"^(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
)


def _template_close(line):
    """Index of the backtick closing a template literal, or -1."""
    i = 0
    while i < len(line):
        if line[i] == "\\":
            i += 2
            continue
        if line[i] == "`":
            return i
        i += 1
    return -1


def extract_ts(source, lines):
    syms = []
    depth = 0
    state = {"comment": False, "template": False}
    for i, raw in enumerate(lines, 1):
        if state["template"]:
            close = _template_close(raw)
            if close == -1:
                continue
            state["template"] = False
            raw = raw[close + 1:]   # braces after the backtick still count
        code = _strip_c_noise(raw, state).strip()
        if depth == 0 and code:
            for kind, rx in _TS_DECLS:
                m = rx.match(code)
                if m:
                    syms.append(_sym(i, kind, m.group(1), _clean_sig(code),
                                     _doc_above(lines, i, ("//", "/*", "*"))))
                    break
        depth = max(0, depth + code.count("{") - code.count("}"))
    return syms


_C_TYPE = re.compile(r"^(?:typedef\s+)?(struct|union|enum|class)\s+"
                     r"([A-Za-z_]\w*)")
_C_DEFINE = re.compile(r"^#\s*define\s+([A-Za-z_]\w*)")
_C_QUAL_FN = re.compile(r"^[A-Za-z_][\w:<>~]*::([A-Za-z_~]\w*)\s*\(")
_C_FN = re.compile(r"^[A-Za-z_][\w\s\*&:,<>]*?[\s\*&]([A-Za-z_]\w*)\s*\(")
_C_KEYWORDS = {"if", "else", "for", "while", "switch", "return", "do",
               "case", "goto", "sizeof", "using", "namespace", "template"}


def extract_c(source, lines):
    syms = []
    depth = 0
    state = {"comment": False, "template": False}
    for i, raw in enumerate(lines, 1):
        code = _strip_c_noise(raw, state)
        stripped = code.strip()
        if depth == 0 and raw[:1] not in (" ", "\t", "") and stripped:
            first = re.split(r"\W", stripped, maxsplit=1)[0]
            doc = _doc_above(lines, i, ("//", "/*", "*"))
            m = _C_DEFINE.match(stripped)
            if m:
                syms.append(_sym(i, "macro", m.group(1),
                                 _clean_sig(stripped), doc))
            elif _C_TYPE.match(stripped):
                m = _C_TYPE.match(stripped)
                syms.append(_sym(i, m.group(1), m.group(2),
                                 _clean_sig(stripped), doc))
            elif first not in _C_KEYWORDS:
                m = _C_QUAL_FN.match(stripped) or _C_FN.match(stripped)
                if m:
                    syms.append(_sym(i, "func", m.group(1),
                                     _clean_sig(stripped), doc))
        depth = max(0, depth + code.count("{") - code.count("}"))
    return syms


# --------------------------------------------- go and rust (column 0 only)

_GO_FUNC = re.compile(r"^func\s+(?:\(([^)]*)\)\s*)?([A-Za-z_]\w*)\s*\(")
_GO_TYPE = re.compile(r"^type\s+([A-Za-z_]\w*)(?:\s+(struct|interface))?")
_GO_VAR = re.compile(r"^(var|const)\s+([A-Za-z_]\w*)")


def extract_go(source, lines):
    syms = []
    for i, raw in enumerate(lines, 1):
        if raw[:1] in (" ", "\t", ""):
            continue
        doc = _doc_above(lines, i, ("//",))
        m = _GO_FUNC.match(raw)
        if m:
            kind = "method" if m.group(1) else "func"
            syms.append(_sym(i, kind, m.group(2), _clean_sig(raw), doc))
            continue
        m = _GO_TYPE.match(raw)
        if m:
            syms.append(_sym(i, m.group(2) or "type", m.group(1),
                             _clean_sig(raw), doc))
            continue
        m = _GO_VAR.match(raw)
        if m:
            syms.append(_sym(i, m.group(1), m.group(2),
                             _clean_sig(raw), doc))
    return syms


_RS_VIS = r"(?:pub(?:\([^)]*\))?\s+)?"
_RS_FN = re.compile(r"^" + _RS_VIS + r"(?:default\s+|const\s+|async\s+|"
                    r"unsafe\s+|extern\s+\"[^\"]*\"\s+)*fn\s+([A-Za-z_]\w*)")
_RS_TYPE = re.compile(r"^" + _RS_VIS + r"(struct|enum|trait|union|mod)\s+"
                      r"([A-Za-z_]\w*)")
_RS_ALIAS = re.compile(r"^" + _RS_VIS + r"type\s+([A-Za-z_]\w*)")
_RS_CONST = re.compile(r"^" + _RS_VIS + r"(?:const|static)\s+([A-Za-z_]\w*)")
_RS_IMPL = re.compile(r"^impl(?:<[^>]*>)?\s+(?:.+\s+for\s+)?"
                      r"([A-Za-z_][\w:]*)")


def extract_rust(source, lines):
    syms = []
    for i, raw in enumerate(lines, 1):
        if raw[:1] in (" ", "\t", ""):
            continue
        doc = _doc_above(lines, i, ("///", "//!", "//"))
        m = _RS_FN.match(raw)
        if m:
            syms.append(_sym(i, "func", m.group(1), _clean_sig(raw), doc))
            continue
        m = _RS_TYPE.match(raw)
        if m:
            syms.append(_sym(i, m.group(1), m.group(2),
                             _clean_sig(raw), doc))
            continue
        m = _RS_ALIAS.match(raw)
        if m:
            syms.append(_sym(i, "type", m.group(1), _clean_sig(raw), doc))
            continue
        m = _RS_CONST.match(raw)
        if m:
            syms.append(_sym(i, "const", m.group(1), _clean_sig(raw), doc))
            continue
        m = _RS_IMPL.match(raw)
        if m:
            name = m.group(1).rsplit("::", 1)[-1]
            syms.append(_sym(i, "impl", name, _clean_sig(raw), doc))
    return syms


# --------------------------------------------------------- generic fallback

_GEN = re.compile(
    r"^(?:(?:public|private|protected|static|export|async|final|abstract|"
    r"pub|open|inline|local|override|sealed|partial|internal)\s+)*"
    r"(def|function|fn|func|sub|proc|class|module|interface|struct|trait|"
    r"object|enum)\s+([A-Za-z_][\w:.$!?]*)")
_GEN_SH = re.compile(r"^([A-Za-z_]\w*)\s*\(\)\s*\{")
_GEN_FUNC_KINDS = {"def", "function", "fn", "func", "sub", "proc"}


def extract_generic(source, lines):
    syms = []
    for i, raw in enumerate(lines, 1):
        if raw[:1] in (" ", "\t", ""):
            continue
        m = _GEN.match(raw)
        if m:
            kind = "func" if m.group(1) in _GEN_FUNC_KINDS else m.group(1)
            syms.append(_sym(i, kind, m.group(2), _clean_sig(raw),
                             _doc_above(lines, i, ("#", "//", "--", ";"))))
            continue
        m = _GEN_SH.match(raw)
        if m:
            syms.append(_sym(i, "func", m.group(1), _clean_sig(raw),
                             _doc_above(lines, i, ("#",))))
    return syms


def extractor_for(ext):
    if ext in PY_EXTS:
        return extract_python
    if ext in TS_EXTS:
        return extract_ts
    if ext in GO_EXTS:
        return extract_go
    if ext in RS_EXTS:
        return extract_rust
    if ext in C_EXTS:
        return extract_c
    if ext in GENERIC_EXTS:
        return extract_generic
    return None


# ------------------------------------------------------------------ walker

def _load_gitignore(root):
    """Root .gitignore, simple subset: names, globs, dir/ patterns.

    Negations and nested .gitignore files are not supported (heuristic).
    """
    pats = []
    try:
        with open(os.path.join(root, ".gitignore"), encoding="utf-8") as fh:
            for line in fh:
                s = line.strip()
                if not s or s.startswith("#") or s.startswith("!"):
                    continue
                pats.append(s.rstrip("/").lstrip("/"))
    except OSError:
        pass
    return pats


def _ignored(rel, name, pats):
    for p in pats:
        if (fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p)
                or fnmatch.fnmatch(rel, p + "/*")):
            return True
    return False


def _skip_dir(name):
    if name in SKIP_DIRS or name.endswith(".egg-info"):
        return True
    return name.startswith(".") and name not in KEEP_DOT_DIRS


def scan(root, pats):
    """Walk root -> (tree, source_files, total_file_count)."""
    tree = {"dirs": {}, "files": []}
    files = []
    total = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        rel = "" if rel == "." else rel
        keep = []
        for d in sorted(dirnames):
            drel = (rel + "/" + d).lstrip("/")
            if not _skip_dir(d) and not _ignored(drel, d, pats):
                keep.append(d)
        dirnames[:] = keep
        node = tree
        for part in rel.split("/") if rel else ():
            node = node["dirs"].setdefault(part, {"dirs": {}, "files": []})
        for d in keep:
            node["dirs"].setdefault(d, {"dirs": {}, "files": []})
        for fn in sorted(filenames):
            frel = (rel + "/" + fn).lstrip("/")
            if _ignored(frel, fn, pats):
                continue
            node["files"].append(fn)
            total += 1
            ext = os.path.splitext(fn)[1].lower()
            extract = extractor_for(ext)
            if extract is None:
                continue
            path = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(path) > SIZE_CAP:
                    continue
                with open(path, "rb") as fh:
                    head = fh.read(8192)
                if b"\0" in head:
                    continue
                # utf-8-sig: a BOM is U+FEFF to ast.parse, and a BOM'd
                # Python file used to outline as empty.
                with open(path, encoding="utf-8-sig",
                          errors="replace") as fh:
                    source = fh.read()
            except OSError:
                continue
            lines = source.splitlines()
            symbols = extract(source, lines)
            stem = os.path.splitext(fn)[0]
            files.append({
                "rel": frel,
                "stem": stem if len(stem) >= MIN_NAME else "",
                "symbols": symbols,
                "names": {s["name"] for s in symbols
                          if len(s["name"]) >= MIN_NAME},
                "tokens": set(IDENT.findall(source)),
                "score": 0,
            })
    return tree, files, total


# ------------------------------------------------------------------ ranker
# Built-in heuristic: how often a file's stem and top-level symbol names
# occur as identifiers in the repo's other source files. A shared
# .repoindex/index.db would be a better source, but its schema is not
# pinned yet — see DECISIONS.md ADR-005. This function is the seam where
# index-backed ranking will slot in.

def rank(files):
    # Score = over every *other* file: +2 if it mentions this file's stem,
    # +1 per top-level name of this file it mentions. Counted through each
    # identifier's document frequency (minus this file's own use), which
    # is the same number the pairwise loop produced in O(files²) — 3.3 s
    # of a 12 s run over Python's 1,853-file stdlib.
    df = collections.Counter()
    for g in files:
        df.update(g["tokens"])
    for f in files:
        toks = f["tokens"]
        score = 0
        if f["stem"]:
            score += 2 * (df[f["stem"]] - (f["stem"] in toks))
        score += sum(df[n] - (n in toks) for n in f["names"])
        f["score"] = score
    files.sort(key=lambda f: (-f["score"], f["rel"]))


# ---------------------------------------------------------------- renderer

def _count_files(node):
    n = len(node["files"])
    for child in node["dirs"].values():
        n += _count_files(child)
    return n


def _related(drel, focus):
    return (focus == drel or focus.startswith(drel + "/")
            or drel.startswith(focus + "/"))


def _tree_lines(tree, focus, depth_limit, cap=None):
    """`cap` limits the entries listed per directory (dirs and files each),
    the rest counted: collapsing depth alone never shrinks a directory's
    own listing, so a root holding 3,000 files ignored every budget."""
    out = []

    def more(indent, n, kind):
        return "%s… (+%d more %s%s)" % (indent, n, kind, "" if n == 1 else "s")

    def walk(node, rel, depth):
        indent = "  " * depth
        dirs = sorted(node["dirs"])
        for d in dirs[:cap]:
            drel = (rel + "/" + d).lstrip("/")
            child = node["dirs"][d]
            collapse = False
            if depth_limit and depth >= depth_limit:
                collapse = True
            elif focus and depth >= 2 and not _related(drel, focus):
                collapse = True
            if collapse and (child["dirs"] or child["files"]):
                n = _count_files(child)
                out.append("%s%s/ … (%d file%s)"
                           % (indent, d, n, "" if n == 1 else "s"))
            else:
                out.append("%s%s/" % (indent, d))
                walk(child, drel, depth + 1)
        if cap is not None and len(dirs) > cap:
            out.append(more(indent, len(dirs) - cap, "dir"))
        files = sorted(node["files"])
        for fn in files[:cap]:
            out.append("%s%s" % (indent, fn))
        if cap is not None and len(files) > cap:
            out.append(more(indent, len(files) - cap, "file"))

    walk(tree, "", 1)
    return out


def _in_focus(f, focus):
    return f["rel"] == focus or f["rel"].startswith(focus + "/")


TEST_RUN_MIN = 3


def _is_test_symbol(s):
    return s["kind"] == "func" and s["name"].startswith("test_")


def _collapse_tests(symbols):
    """Fold runs of test_* functions into one entry each. A suite's test names
    are the bulkiest thing in an outline and the least informative — a better
    tested file should not cost more to map."""
    out, i = [], 0
    while i < len(symbols):
        j = i
        while j < len(symbols) and _is_test_symbol(symbols[j]):
            j += 1
        if j - i >= TEST_RUN_MIN:
            out.append((symbols[i], j - i))
            i = j
        else:
            out.append((symbols[i], 0))
            i += 1
    return out


def _file_block(f, prefix, detail):
    dpath = prefix + f["rel"]
    lines = ["%s  [refs %d]" % (dpath, f["score"])]
    if detail == "summary":
        n = len(f["symbols"])
        lines[0] += "  (%d symbol%s)" % (n, "" if n == 1 else "s")
        return lines
    for s, run in _collapse_tests(f["symbols"]):
        if run:
            line = "  %s:%d %d test functions (%s …)" % (
                dpath, s["line"], run, s["name"])
        elif detail == "full":
            line = "  %s:%d %s" % (dpath, s["line"], s["sig"])
            if s["doc"]:
                line += " — " + s["doc"]
        else:
            line = "  %s:%d %s %s" % (dpath, s["line"], s["kind"], s["name"])
        lines.append(line)
    return lines


def _render(ctx, stage, k, depth_limit, cap=None):
    lines = ["repomap %s — %d source files / %d files  "
             "(ranking: heuristic, identifier references)"
             % (ctx["label"], ctx["n_source"], ctx["n_total"]), ""]
    root_label = ctx["label"].replace("\\", "/").rstrip("/") or "."
    lines.append(root_label + "/")
    lines += _tree_lines(ctx["tree"], ctx["focus"], depth_limit, cap)
    order = ctx["order"]
    collapsed = 0
    if stage != "tree":
        for f in order[:k]:
            if ctx["focus"] and not _in_focus(f, ctx["focus"]):
                detail = "summary"   # --focus narrows, not merely ranks
                collapsed += 1
            else:
                detail = "full" if stage == "full" else "names"
            lines.append("")
            lines += _file_block(f, ctx["prefix"], detail)
    notes = []
    if collapsed:
        notes.append("(%d file%s outside --focus %s collapsed to one line; "
                     "drop --focus for their outlines)"
                     % (collapsed, "" if collapsed == 1 else "s",
                        ctx["focus"]))
    if stage == "full" and k < len(order):
        notes.append("(… %d lower-ranked file outlines dropped for "
                     "--max-tokens %d)" % (len(order) - k, ctx["budget"]))
    elif stage == "names":
        note = "(signatures dropped for --max-tokens %d" % ctx["budget"]
        if k < len(order):
            note += "; %d of %d outlines shown" % (k, len(order))
        notes.append(note + ")")
    elif stage == "tree" and ctx["budget"]:
        notes.append("(tree only for --max-tokens %d)" % ctx["budget"])
    if cap is not None:
        notes.append("(directory listings capped at %d entr%s each for "
                     "--max-tokens %d)" % (cap, "y" if cap == 1 else "ies",
                                           ctx["budget"]))
    if notes:
        lines.append("")
        lines += notes
    return lines


def build_output(ctx):
    """Render within budget, degrading whole levels — never mid-entry."""
    budget = ctx["budget"]
    n = len(ctx["order"])
    lines = _render(ctx, "full", n, None)
    if not budget or _est(lines) <= budget:
        return lines

    if n:
        # Reserve at least half the budget for outlines by collapsing deep
        # tree levels before sacrificing any outline content. (With no
        # outlines to make room for, the tree gets all of it, below.)
        tree_depth, tree_cap = _fit_tree(ctx, budget // 2)

        def search(stage, floor):
            best = None
            lo, hi = floor, n
            while lo <= hi:
                mid = (lo + hi) // 2
                cand = _render(ctx, stage, mid, tree_depth, tree_cap)
                if _est(cand) <= budget:
                    best = cand
                    lo = mid + 1
                else:
                    hi = mid - 1
            return best

        best = search("full", min(FULL_FLOOR, n))
        if best:
            return best
        best = search("names", 1)
        if best:
            return best
    depth, cap = _fit_tree(ctx, budget)
    return _render(ctx, "tree", 0, depth, cap)


def _fit_tree(ctx, limit):
    """(depth_limit, cap) of the most detailed tree-only render within
    `limit`: shallower first, then fewer entries listed per directory —
    the rung that makes the ladder terminate on a wide directory. Floors
    at depth 1 with one entry of each kind, which is O(1)."""
    for depth in (None, 3, 2, 1):
        if _est(_render(ctx, "tree", 0, depth)) <= limit:
            return depth, None
    root = ctx["tree"]
    lo, hi, best = 1, max(len(root["dirs"]), len(root["files"]), 1), 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if _est(_render(ctx, "tree", 0, 1, mid)) <= limit:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return 1, best


# --------------------------------------------------------------------- CLI

def main(argv=None):
    try:  # error text carries the same non-ASCII punctuation as output;
        # a cp1252 console default turns it into invalid UTF-8 bytes
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        prog="repomap",
        description="print a compact repository map: pruned tree plus "
                    "per-file symbol outlines, most-referenced files first")
    parser.add_argument("dir", nargs="?", default=".", metavar="DIR")
    parser.add_argument("--focus", metavar="PATH",
                        help="outline only this file or subtree; every other "
                             "file collapses to a one-line count")
    parser.add_argument("--max-tokens", type=int, metavar="N",
                        default=DEFAULT_MAX_TOKENS,
                        help="cap output at roughly N tokens (bytes/4) "
                             "(default: %d, 0 = unbounded)"
                             % DEFAULT_MAX_TOKENS)
    parser.add_argument("--version", action="version",
                        version="repomap %s" % __version__)
    args = parser.parse_args(argv)

    try:
        if not os.path.isdir(args.dir):
            raise RepomapError("not a directory: %s" % args.dir)
        focus = None
        if args.focus:
            focus = args.focus.replace("\\", "/").strip("/")
            if not os.path.exists(os.path.join(args.dir, focus)):
                raise RepomapError("--focus path not found under %s: %s"
                                   % (args.dir, args.focus))
        pats = _load_gitignore(args.dir)
        tree, files, total = scan(args.dir, pats)
        rank(files)
        order = [f for f in files if f["symbols"]]
        if focus:
            order.sort(key=lambda f: 0 if _in_focus(f, focus) else 1)
        label = args.dir.replace("\\", "/")
        prefix = "" if label in (".", "./") else label.rstrip("/") + "/"
        ctx = {"label": args.dir, "prefix": prefix, "tree": tree,
               "order": order, "focus": focus, "n_source": len(files),
               "n_total": total, "budget": max(0, args.max_tokens)}
        lines = build_output(ctx)
    except RepomapError as exc:
        print("repomap: %s" % exc, file=sys.stderr)
        return 2

    try:  # echo file content byte-faithfully, not via a cp1252 console default
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
