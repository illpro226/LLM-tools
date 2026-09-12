#!/usr/bin/env python3
"""xread — targeted code excerpt reader.

Prints just the relevant parts of a file instead of the whole thing:

    xread FILE --symbol NAME        full body of a function/class/method
                                    (nested names like ClassName.method),
                                    or a module-level constant with its
                                    full right-hand side; on markdown
                                    files, a heading's section
    xread FILE --lines A-B          a line range; --scope expands it to the
                                    enclosing function/class
    xread FILE --query "text"       the top keyword-scoring blocks
    xread FILE --headings           outline of one file: markdown headings,
                                    or the symbols of a code file with their
                                    spans (the names --symbol takes)
    xread FILE                      no mode given: defaults to --headings,
                                    the cheap first look at a file whose
                                    symbol names you don't know yet

Every excerpt starts with a citable `== path:start-end ==` header; elision
markers appear between non-adjacent excerpts. All modes accept multiple
files and `--max-tokens N`, degrading by dropping whole blocks (lowest
score first) and trimming at blank-line boundaries — never mid-statement.

Parsing is stateless per invocation, stdlib only: Python via `ast` (exact
spans), JS/TS via a brace-tracking line scanner (heuristic: declarations
must open their brace on the same line), markdown via heading scan, Prisma
schemas via a flat block scanner (model/enum/type/view/generator/
datasource).
"""

import argparse
import os
import re
import sys

__version__ = "0.4.2"

PY_EXTS = {".py", ".pyi"}
TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts"}
MD_EXTS = {".md", ".markdown"}
PRISMA_EXTS = {".prisma"}

WINDOW = 20        # query-mode block size for lines outside any symbol
DEFAULT_TOP = 3    # query-mode blocks returned
# ADR-005: the token cap is on by default. An excerpt tool that can still
# emit a whole large symbol unasked is only excerpting by luck; 0 restores
# unbounded output for the rare case that wants it.
DEFAULT_MAX_TOKENS = 2000
ADJACENT_MAX = 20  # query-mode: max lines of a preceding sibling section
                   # pulled in when a match starts at a markdown heading


class XreadError(Exception):
    pass


def _tokens_of(lines):
    return sum(len(line) + 1 for line in lines) // 4


# ----------------------------------------------------------- python parser
# A symbol is {"name", "qual", "kind", "start", "end", "top"} with
# 1-indexed inclusive line spans.

def _extend_comments(lines, start, prefixes):
    while start > 1:
        above = lines[start - 2].strip()
        if any(above.startswith(p) for p in prefixes) and above:
            start -= 1
        else:
            break
    return start


def _assigned_names(target):
    """Names bound by an assignment target, unpacking tuples and lists.

    `A, B = 1, 2` binds both, so both should be findable; attribute and
    subscript targets (`obj.x = 1`, `d["k"] = 1`) bind no new module-level
    name and are skipped.
    """
    import ast
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names = []
        for elt in target.elts:
            names.extend(_assigned_names(elt))
        return names
    return []


def parse_python(source, lines):
    import ast
    symbols = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                start = child.lineno
                if child.decorator_list:
                    start = min(start, child.decorator_list[0].lineno)
                start = _extend_comments(lines, start, ("#",))
                kind = ("class" if isinstance(child, ast.ClassDef)
                        else "function")
                qual = prefix + child.name
                symbols.append({"name": child.name, "qual": qual,
                                "kind": kind, "start": start,
                                "end": child.end_lineno,
                                "top": prefix == ""})
                visit(child, qual + ".")
            elif prefix == "" and isinstance(child, (ast.Assign,
                                                     ast.AnnAssign)):
                # Module-level bindings are the configuration surface of a
                # file — rule regexes, tunables, extension sets — and the
                # names an agent arrives with from a traceback or a grep
                # hit. Without them `--symbol NAME` fails on exactly the
                # lookup it should be cheapest at. Top-level only: names
                # bound inside a function are locals, not API, and would
                # bury the outline. See docs/known-issues/
                # xread-symbol-misses-module-level-constants.md.
                targets = ([child.target] if isinstance(child, ast.AnnAssign)
                           else child.targets)
                for tgt in targets:
                    for name in _assigned_names(tgt):
                        start = _extend_comments(lines, child.lineno, ("#",))
                        symbols.append({"name": name, "qual": name,
                                        "kind": "constant", "start": start,
                                        "end": child.end_lineno,
                                        "top": True})

    try:
        visit(ast.parse(source), "")
    except SyntaxError as exc:
        raise XreadError("python parse error: %s" % exc)
    return symbols


# ------------------------------------------------------------ js/ts parser
# Heuristic line scanner: strings and comments are stripped, braces are
# counted, and a declaration's span ends when depth returns to the depth it
# opened at. Declarations must open their brace on the same line (K&R
# style); one-liners close on their own line naturally.

_TS_DECLS = (
    ("class", re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?"
        r"class\s+([A-Za-z_$][\w$]*)")),
    ("interface", re.compile(
        r"^(?:export\s+)?(?:declare\s+)?interface\s+([A-Za-z_$][\w$]*)")),
    ("enum", re.compile(
        r"^(?:export\s+)?(?:declare\s+)?(?:const\s+)?"
        r"enum\s+([A-Za-z_$][\w$]*)")),
    ("function", re.compile(
        r"^(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?"
        r"function\s*\*?\s*([A-Za-z_$][\w$]*)")),
    ("function", re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
        r"[^=;]*=\s*(?:async\b[^=;]*)?(?:\([^)]*\)?|[A-Za-z_$][\w$]*)"
        r"\s*(?::[^=]*)?=>")),
    ("function", re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)"
        r"\s*=\s*(?:async\s+)?function\b")),
    ("type", re.compile(
        r"^(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=")),
)

_TS_METHOD = re.compile(
    r"^(?:(?:public|private|protected|static|readonly|async|override|get|set)"
    r"\s+|\*\s*)*([A-Za-z_$][\w$]*)\s*(?:<[^>]*>)?\s*\(")
_TS_FIELD_FN = re.compile(
    r"^(?:(?:public|private|protected|static|readonly)\s+)*"
    r"([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\([^)]*\)?[^;]*=>")
_TS_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "new",
                "function", "typeof", "delete", "void", "do", "else",
                "throw", "await", "yield", "super", "this"}


def _strip_ts_noise(line, state):
    """Remove strings and comments so brace counting sees only code."""
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


def parse_ts(source, lines):
    symbols = []
    stack = []  # open symbols: [(symbol, close_depth)]
    depth = 0
    state = {"comment": False, "template": False}

    for i, raw in enumerate(lines, 1):
        if state["template"]:  # inside a multi-line template literal
            if "`" in raw:
                state["template"] = False
            continue
        code = _strip_ts_noise(raw, state).strip()

        decl = None
        in_class = (stack and stack[-1][0]["kind"] in ("class", "interface")
                    and depth == stack[-1][1] + 1)
        if in_class and "{" in code:
            m = _TS_METHOD.match(code) or _TS_FIELD_FN.match(code)
            if m and m.group(1) not in _TS_KEYWORDS:
                decl = ("method", m.group(1))
        if decl is None:
            for kind, rx in _TS_DECLS:
                m = rx.match(code)
                if m:
                    decl = (kind, m.group(1))
                    break

        if decl:
            kind, name = decl
            start = _extend_comments(lines, i, ("//", "*", "/*"))
            qual = ".".join(s["name"] for s, _ in stack) or ""
            qual = (qual + "." if qual else "") + name
            sym = {"name": name, "qual": qual, "kind": kind, "start": start,
                   "end": i, "top": not stack}
            symbols.append(sym)
            stack.append((sym, depth))

        depth += code.count("{") - code.count("}")
        while stack and depth <= stack[-1][1]:
            sym, _ = stack.pop()
            sym["end"] = i
    for sym, _ in stack:  # unterminated (parse imperfection): close at EOF
        sym["end"] = len(lines)
    return symbols


# ---------------------------------------------------------- markdown parser

_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_MD_FENCE = re.compile(r"^\s*(```|~~~)")


def parse_markdown(source, lines):
    headings = []
    in_fence = False
    for i, line in enumerate(lines, 1):
        if _MD_FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _MD_HEADING.match(line)
        if m:
            headings.append({"name": m.group(2), "qual": m.group(2),
                             "kind": "h%d" % len(m.group(1)),
                             "level": len(m.group(1)),
                             "start": i, "end": len(lines), "top": True})
    for idx, h in enumerate(headings):  # section ends before the next
        for nxt in headings[idx + 1:]:  # heading at the same level or higher
            if nxt["level"] <= h["level"]:
                h["end"] = nxt["start"] - 1
                break
    return headings


# ------------------------------------------------------------ prisma parser
# Prisma schemas are flat block declarations: `model X { ... }` with no
# nesting, `//` comments, `"` strings (which may themselves contain `//`,
# e.g. datasource URLs — strip strings before comments).

_PRISMA_BLOCK = re.compile(
    r"^\s*(model|enum|type|view|generator|datasource)\s+(\w+)\s*\{")
_PRISMA_STRING = re.compile(r'"[^"]*"')


def parse_prisma(source, lines):
    symbols = []
    open_sym = None
    depth = 0
    for i, raw in enumerate(lines, 1):
        code = _PRISMA_STRING.sub('""', raw).split("//", 1)[0]
        if open_sym is None:
            m = _PRISMA_BLOCK.match(code)
            if m:
                start = _extend_comments(lines, i, ("//",))
                open_sym = {"name": m.group(2), "qual": m.group(2),
                            "kind": m.group(1), "start": start,
                            "end": i, "top": True}
                symbols.append(open_sym)
        if open_sym is not None:
            depth += code.count("{") - code.count("}")
            if depth <= 0:
                open_sym["end"] = i
                open_sym = None
                depth = 0
    if open_sym is not None:  # unterminated block: close at EOF
        open_sym["end"] = len(lines)
    return symbols


# ------------------------------------------------------------------ files

def parser_for(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in PY_EXTS:
        return parse_python
    if ext in TS_EXTS:
        return parse_ts
    if ext in MD_EXTS:
        return parse_markdown
    if ext in PRISMA_EXTS:
        return parse_prisma
    return None


def load(paths):
    """Return [(path, lines, symbols|None)] in argument order."""
    files = []
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError as exc:
            raise XreadError("%s: %s" % (path, exc.strerror or exc))
        lines = source.splitlines()
        parse = parser_for(path)
        symbols = parse(source, lines) if parse else None
        files.append((path, lines, symbols))
    return files


# ------------------------------------------------------------------ modes
# Every mode resolves to regions {file_index, path, start, end, score}.

def _region(idx, path, start, end, score):
    return {"file_index": idx, "path": path, "start": start, "end": end,
            "score": score}


def resolve_symbols(files, names):
    regions = []
    for name in names:
        exact, loose = [], []
        for idx, (path, lines, symbols) in enumerate(files):
            for s in symbols or ():
                if s["qual"] == name:
                    exact.append((idx, path, s))
                elif s["qual"].endswith("." + name) or s["name"] == name:
                    loose.append((idx, path, s))
        matches = exact or loose
        if not matches:
            raise XreadError("symbol not found: %s" % name)
        if not exact and len(loose) > 1:
            cands = "\n".join("  %s  %s:%d" % (s["qual"], path, s["start"])
                              for idx, path, s in loose)
            raise XreadError(
                "ambiguous symbol %s; candidates:\n%s" % (name, cands))
        for idx, path, s in matches:
            regions.append(_region(idx, path, s["start"], s["end"], 1e9))
    return regions


def resolve_lines(files, spec, scope):
    m = re.match(r"^(\d+)(?:-(\d+))?$", spec)
    if not m:
        raise XreadError("bad --lines %r (expected A-B)" % spec)
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    if b < a:
        a, b = b, a
    regions = []
    for idx, (path, lines, symbols) in enumerate(files):
        if a > len(lines):
            raise XreadError("%s: --lines %s starts past end of file (%d "
                             "lines)" % (path, spec, len(lines)))
        start, end = a, min(b, len(lines))
        if scope and symbols:
            enclosing = [s for s in symbols
                         if s["start"] <= start and s["end"] >= end]
            if enclosing:
                best = min(enclosing, key=lambda s: s["end"] - s["start"])
                start, end = best["start"], best["end"]
        regions.append(_region(idx, path, start, end, 1e9))
    return regions


def _query_blocks(idx, path, lines, symbols):
    """Top-level symbol spans, plus fixed windows over the gaps."""
    blocks = []
    covered_to = 0
    tops = sorted((s for s in (symbols or ()) if s["top"]),
                  key=lambda s: s["start"])
    for j, s in enumerate(tops):
        if s["start"] > covered_to + 1:
            for w in range(covered_to + 1, s["start"], WINDOW):
                blocks.append((w, min(w + WINDOW - 1, s["start"] - 1)))
        end = s["end"]
        if j + 1 < len(tops):
            # Markdown sections nest: an H1's span runs to the next H1 or
            # EOF, containing every subsection. Clamp each block at the
            # next heading so blocks tile the file and a parent section's
            # body can't outscore (and swallow) the specific subsection a
            # query is aimed at (known-issue
            # xread-query-returns-whole-markdown-file). Code symbols are
            # non-overlapping, so this is a no-op for them.
            end = min(end, tops[j + 1]["start"] - 1)
        blocks.append((s["start"], end))
        covered_to = max(covered_to, end)
    for w in range(covered_to + 1, len(lines) + 1, WINDOW):
        blocks.append((w, min(w + WINDOW - 1, len(lines))))
    return [(idx, path, a, b) for a, b in blocks]


def resolve_query(files, query, top):
    keywords = [k for k in query.lower().split() if k]
    if not keywords:
        raise XreadError("empty --query")
    word_res = [re.compile(r"\b%s\b" % re.escape(k)) for k in keywords]
    scored = []
    for idx, (path, lines, symbols) in enumerate(files):
        for bidx, bpath, a, b in _query_blocks(idx, path, lines, symbols):
            text = "\n".join(lines[a - 1:b]).lower()
            hits = sum(text.count(k) for k in keywords)
            if hits:
                # Weight by whole-word keyword coverage so a block
                # containing every query word outranks one where a single
                # common word repeats, or only appears inside longer words
                # ("building" is not a hit for "build"). Substring hits
                # still count toward volume, and max(matched, 1) keeps
                # partial-word queries ("instal") working when no block
                # has a whole-word match.
                matched = sum(1 for rx in word_res if rx.search(text))
                score = (hits * max(matched, 1) / len(keywords)
                         / max(1, b - a + 1) ** 0.5)
                scored.append(_region(bidx, bpath, a, b, score))
    scored.sort(key=lambda r: (-r["score"], r["file_index"], r["start"]))
    return _pull_in_preceding_sibling(files, scored[:top])


def _pull_in_preceding_sibling(files, regions):
    """A markdown section's payload often sits in a short sibling directly
    above the section the keywords land in (e.g. a fenced error-envelope
    under "### Error" scoring below its neighbour "### Error Codes").
    Fenced code is nearly opaque to keyword scoring, so when a returned
    region starts at a heading, extend it back over the immediately
    preceding same-level sibling if that sibling is short and carries a
    fenced block (known-issue xread-query-misses-adjacent-code-block).
    Siblings without fences stay out — prose scores on its own merits, and
    pulling it in unconditionally would pad every markdown match."""
    for r in regions:
        _, lines, symbols = files[r["file_index"]]
        heads = [s for s in symbols or () if "level" in s]
        match = next((h for h in heads if h["start"] == r["start"]), None)
        if match is None:
            continue
        prev = None  # nearest earlier heading at the same or higher level
        for h in heads:
            if h["start"] >= match["start"]:
                break
            if h["level"] <= match["level"]:
                prev = h
        if (prev is not None and prev["level"] == match["level"]
                and prev["end"] == match["start"] - 1
                and prev["end"] - prev["start"] + 1 <= ADJACENT_MAX
                and any(_MD_FENCE.match(l)
                        for l in lines[prev["start"] - 1:prev["end"]])):
            r["start"] = prev["start"]
    return regions


# -------------------------------------------------------- merge and render

def _merge(regions):
    """Per file: sort by start, merge overlapping/adjacent regions."""
    groups = {}
    for r in regions:
        groups.setdefault((r["file_index"], r["path"]), []).append(r)
    merged = []
    for (idx, path), regs in sorted(groups.items()):
        regs.sort(key=lambda r: r["start"])
        out = [dict(regs[0])]
        for r in regs[1:]:
            if r["start"] <= out[-1]["end"] + 1:
                out[-1]["end"] = max(out[-1]["end"], r["end"])
                out[-1]["score"] = max(out[-1]["score"], r["score"])
            else:
                out.append(dict(r))
        merged.append((path, out))
    return merged


def render(regions, sources):
    out = []
    for path, regs in _merge(regions):
        if out:
            out.append("")
        prev_end = None
        for r in regs:
            if prev_end is not None:
                out.append("… %d lines elided …" % (r["start"] - prev_end - 1))
            out.append("== %s:%d-%d ==" % (path, r["start"], r["end"]))
            out.extend(sources[path][r["start"] - 1:r["end"]])
            if r.get("trimmed_from"):
                out.append("… %d more lines elided (--max-tokens) …"
                           % (r["trimmed_from"] - r["end"]))
            prev_end = r["end"]
    return out


def apply_budget(regions, sources, max_tokens):
    """Drop lowest-score regions, then trim the survivor at blank lines."""
    dropped = []
    while regions:
        lines = render(regions, sources)
        if not max_tokens or _tokens_of(lines) <= max_tokens:
            break
        if len(regions) > 1:
            victim = min(regions, key=lambda r: (r["score"],
                                                 -r["file_index"],
                                                 -r["start"]))
            regions.remove(victim)
            dropped.append(victim)
            continue
        r = regions[0]
        body = sources[r["path"]][r["start"] - 1:r["end"]]
        blank = None
        for j in range(len(body) - 1, 0, -1):  # last blank line in the body
            if not body[j].strip():
                blank = j
                break
        if blank is None or r["start"] + blank - 1 <= r["start"]:
            # No blank line to cut at. Trimming at a plain line boundary is
            # worse than a paragraph boundary but far better than the
            # alternative: dropping the sole region returns nothing but a
            # note, which is the one degradation that answers no part of
            # the question. Halve toward the head until it fits.
            span = r["end"] - r["start"]
            if span > 1:
                r.setdefault("trimmed_from", r["end"])
                r["end"] = r["start"] + span // 2
                continue
            dropped.append(regions.pop())
            break
        r.setdefault("trimmed_from", r["end"])
        r["end"] = r["start"] + blank - 1
        while (r["end"] > r["start"]
               and not sources[r["path"]][r["end"] - 1].strip()):
            r["end"] -= 1
    lines = render(regions, sources)
    if dropped:
        dropped.sort(key=lambda r: (r["file_index"], r["start"]))
        if lines:
            lines.append("")
        lines.append("(dropped for --max-tokens: %s)" % ", ".join(
            "%s:%d-%d" % (r["path"], r["start"], r["end"]) for r in dropped))
    return lines


# --------------------------------------------------------------------- CLI

def _code_outline(path, symbols):
    """One line per symbol: `path:start  kind name [start-end]`.

    Nesting is carried by indentation rather than by repeating the qualified
    name, so a method costs its own name once. The span is what makes the
    listing actionable — it tells you what a follow-up `--symbol` will cost
    before you spend it.
    """
    out = []
    for s in symbols:
        depth = s["qual"].count(".") if s.get("qual") else 0
        out.append("%s:%d  %s%s %s [%d-%d]"
                   % (path, s["start"], "  " * depth, s["kind"], s["name"],
                      s["start"], s["end"]))
    return out


def cmd_headings(files, max_tokens):
    out = []
    for path, lines, symbols in files:
        parse = parser_for(path)
        if parse is None:
            raise XreadError(
                "%s: --headings needs a file xread can parse "
                "(python, js/ts, markdown, prisma)" % path)
        if parse is parse_markdown:
            for h in symbols:
                out.append("%s:%d  %s %s"
                           % (path, h["start"], "#" * h["level"], h["name"]))
        else:
            # "What's in this file?" is the precondition for --symbol: you
            # cannot ask for a symbol whose name you don't know yet. xread
            # already builds this map to serve --symbol, and repomap only
            # takes directories, so this used to be a gap between the two
            # tools that each deflected to the other.
            out.extend(_code_outline(path, symbols))
    if max_tokens:
        budget = max_tokens * 4
        used = 0
        for i, line in enumerate(out):
            used += len(line) + 1
            if used > budget and i < len(out) - 1:
                return out[:i] + ["(… %d more outline entries elided for "
                                  "--max-tokens %d)" % (len(out) - i,
                                                        max_tokens)]
    return out


def main(argv=None):
    try:  # error text carries the same non-ASCII punctuation as output;
        # a cp1252 console default turns it into invalid UTF-8 bytes
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(
        prog="xread",
        description="print targeted excerpts of files instead of whole files")
    parser.add_argument("paths", nargs="+", metavar="FILE")
    parser.add_argument("--symbol", action="append", metavar="NAME",
                        help="print the named function/class/method "
                             "(or markdown section); repeatable")
    parser.add_argument("--lines", metavar="A-B",
                        help="print a line range")
    parser.add_argument("--scope", action="store_true",
                        help="expand --lines to the enclosing function/class")
    parser.add_argument("--query", metavar="TEXT",
                        help="print the top keyword-scoring blocks")
    parser.add_argument("--top", type=int, metavar="N", default=DEFAULT_TOP,
                        help="query mode: blocks to return (default %d)"
                             % DEFAULT_TOP)
    parser.add_argument("--headings", action="store_true",
                        help="outline the file: markdown headings, or code "
                             "symbols with their spans")
    parser.add_argument("--max-tokens", type=int, metavar="N",
                        default=DEFAULT_MAX_TOKENS,
                        help="cap output at roughly N tokens "
                             "(default: %d, 0 = unbounded)"
                             % DEFAULT_MAX_TOKENS)
    parser.add_argument("--version", action="version",
                        version="xread %s" % __version__)
    args = parser.parse_args(argv)

    modes = [bool(args.symbol), bool(args.lines), bool(args.query),
             args.headings]
    if sum(modes) > 1:
        parser.error("at most one of --symbol, --lines, --query, "
                     "--headings may be given")
    if sum(modes) == 0:
        # Naming a file and asking to see it is the most natural first call,
        # and it is the one a reader makes before they have a symbol name to
        # ask for. Erroring there spends a round-trip to teach what the
        # outline would have shown; --headings is the bounded answer to that
        # request, so make it the default and say so rather than refusing.
        # See docs/known-issues/xread-bare-file-call-errors-instead-of-
        # defaulting.md.
        args.headings = True
        sys.stderr.write("xread: no mode given, showing --headings\n")

    try:
        files = load(args.paths)
        if args.headings:
            lines = cmd_headings(files, args.max_tokens)
        else:
            if args.symbol:
                unsupported = [p for p, _, s in files if s is None]
                if unsupported:
                    raise XreadError(
                        "unsupported file type for --symbol: %s"
                        % ", ".join(unsupported))
                regions = resolve_symbols(files, args.symbol)
            elif args.lines:
                regions = resolve_lines(files, args.lines, args.scope)
            else:
                regions = resolve_query(files, args.query, args.top)
            sources = {path: lines for path, lines, _ in files}
            lines = apply_budget(regions, sources, args.max_tokens)
    except XreadError as exc:
        print("xread: %s" % exc, file=sys.stderr)
        return 2

    try:  # echo file content byte-faithfully, not via a cp1252 console default
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
