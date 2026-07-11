#!/usr/bin/env python3
"""rq: repo query -- a query pack over .repoindex/index.db.

Each subcommand answers one relationship question (who uses this, what
implements that, what breaks if I change this) with one or two SQL queries
plus shared formatting. rq never parses source: data gaps are repoindex's
to fix (DECISIONS.md ADR-002).

Output contract (INVARIANTS.md): plain text, deterministic ordering, every
line that makes a claim about code carries a path:line reference,
--max-tokens collapses leaf lists to (+N more) counts before anything else,
--json mirrors the text content. Confidence is two-valued:
resolved | heuristic.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys

DB_RELPATH = os.path.join(".repoindex", "index.db")

# Extensions stripped when matching an import's module string to a file
# stem in findcycles (mirrors repoindex's resolver candidates).
_JS_EXTS = (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")

# javascript and typescript files import each other freely; treat them as
# one family when scoping raw-name matches to a language.
_FAMILY = {"javascript": "js", "typescript": "js"}


def _family(language):
    return _FAMILY.get(language, language)


def _local(qualname):
    """'py/shapes.py::Rectangle.area' -> 'Rectangle.area'."""
    return qualname.split("::", 1)[1] if "::" in qualname else qualname


def _last(name):
    """Last dotted segment: 'Rectangle.area' -> 'area'."""
    return name.rsplit(".", 1)[-1]


# --------------------------------------------------------- freshness ---

def ensure_fresh(root, repoindex_cmd=None):
    """Run `repoindex update` so answers never come from a stale index.

    Resolution order for the repoindex binary: --repoindex flag,
    RQ_REPOINDEX env var, `repoindex` on PATH, then the sibling checkout
    (tools/repoindex/repoindex.py) so an uninstalled working copy still
    works. Returns True if an update ran, False if it could not.
    """
    cmd = repoindex_cmd or os.environ.get("RQ_REPOINDEX") or "repoindex"
    resolved = shutil.which(cmd)
    if resolved is not None:
        # Pass the resolved path, not the bare name: on Windows the PATH
        # entry is a .cmd shim, and CreateProcess only resolves bare names
        # to .exe -- subprocess would raise FileNotFoundError.
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
        sys.stderr.write("rq: `repoindex update` failed:\n" + proc.stderr)
        return False
    return True


def open_db(root):
    db_path = os.path.join(root, DB_RELPATH)
    if not os.path.exists(db_path):
        return None
    uri = f"file:{db_path.replace(os.sep, '/')}?mode=ro"
    return sqlite3.connect(uri, uri=True)


# ---------------------------------------------------------- matching ---

def match_symbols(conn, name):
    """Symbols whose qualname, local name, or last dotted segment == name.

    substr() comparisons instead of LIKE: SQLite LIKE is case-insensitive
    for ASCII, which would conflate `Run` and `run`.
    """
    suffix_local = f"::{name}"
    suffix_member = f".{name}"
    rows = conn.execute(
        "SELECT qualname, kind, file, line_start, line_end, exported "
        "FROM symbols WHERE qualname = ? "
        f"OR substr(qualname, -{len(suffix_local)}) = ? "
        f"OR substr(qualname, -{len(suffix_member)}) = ? "
        "ORDER BY file, line_start, qualname",
        (name, suffix_local, suffix_member)).fetchall()
    return rows


def _refs_to(conn, qualname):
    """Inbound refs: resolved rows targeting the qualname, plus heuristic
    rows (to_symbol IS NULL) whose raw name matches the symbol's local
    name or last segment -- shown, labeled, never dropped."""
    local = _local(qualname)
    suffix = f".{_last(local)}"
    rows = conn.execute(
        "SELECT from_file, from_line, kind, confidence FROM refs "
        "WHERE to_symbol = ? "
        "OR (to_symbol IS NULL AND (to_name = ? "
        f"    OR substr(to_name, -{len(suffix)}) = ?)) "
        "ORDER BY kind, from_file, from_line",
        (qualname, local, suffix)).fetchall()
    return rows


def _load_languages(conn):
    return dict(conn.execute("SELECT path, language FROM files"))


def _load_inherits(conn):
    return conn.execute(
        "SELECT child, parent, file, line FROM inherits "
        "ORDER BY file, line, child").fetchall()


def _load_implements(conn):
    return conn.execute(
        "SELECT symbol, interface, file, line, confidence FROM implements "
        "ORDER BY file, line, symbol").fetchall()


def _interface_matches(interface, qualname, languages, row_file):
    """Does an implements row's raw-or-qualified interface name denote
    this interface symbol? Qualified names match exactly; raw names match
    the local name, scoped to the same language family."""
    if interface == qualname:
        return True
    local = _local(qualname)
    if interface == local or _last(interface) == local:
        ifile = qualname.split("::", 1)[0]
        return _family(languages.get(row_file)) == _family(languages.get(ifile))
    return False


def _parent_matches(parent, qualname, languages, row_file):
    """Does an inherits row's raw parent name denote this class symbol?"""
    local = _local(qualname)
    if parent == local or _last(parent) == local:
        pfile = qualname.split("::", 1)[0]
        return _family(languages.get(row_file)) == _family(languages.get(pfile))
    return False


# ---------------------------------------------------------- renderer ---

def _estimate_tokens(text):
    """tokq's fallback heuristic: bytes / 3.7."""
    return len(text.encode("utf-8", errors="replace")) / 3.7


def _render_text(groups, notes, cap=None):
    lines = []
    for g in groups:
        if g["title"] is not None:
            lines.append(g["title"])
        items = g["items"]
        shown = items if cap is None else items[:cap]
        for it in shown:
            lines.append("  " * it["depth"] + it["text"])
        if cap is not None and len(items) > cap:
            lines.append(f"  (+{len(items) - cap} more)")
    lines.extend(notes)
    return "\n".join(lines) + ("\n" if lines else "")


def _render_json(command, groups, notes, cap=None):
    out_groups = []
    for g in groups:
        items = g["items"]
        shown = items if cap is None else items[:cap]
        out_groups.append({
            "title": g["title"],
            "items": [it["data"] for it in shown],
            "omitted": 0 if cap is None else max(0, len(items) - cap),
        })
    return json.dumps({"command": command, "groups": out_groups,
                       "notes": notes}) + "\n"


def render(command, groups, notes, as_json=False, max_tokens=None):
    """Render under the token budget: collapse leaf lists to (+N more)
    counts first (largest cap that fits), floor at count-only groups."""
    def _render(cap):
        if as_json:
            return _render_json(command, groups, notes, cap)
        return _render_text(groups, notes, cap)

    out = _render(None)
    if max_tokens is None or _estimate_tokens(out) <= max_tokens:
        return out
    biggest = max((len(g["items"]) for g in groups), default=0)
    for cap in range(biggest - 1, -1, -1):
        out = _render(cap)
        if _estimate_tokens(out) <= max_tokens:
            return out
    return out  # count-only floor: cannot summarize harder


def _item(depth, text, **data):
    return {"depth": depth, "text": text, "data": data}


# -------------------------------------------------------- subcommands ---

def cmd_whouses(conn, args):
    syms = match_symbols(conn, args.symbol)
    if not syms:
        sys.stderr.write(f"rq: no symbol matching '{args.symbol}' in index\n")
        return [], [], 1
    groups = []
    for qualname, kind, file, line_start, _end, _exp in syms:
        items = []
        seen = set()
        for from_file, from_line, ref_kind, conf in _refs_to(conn, qualname):
            key = (ref_kind, from_file, from_line, conf)
            if key in seen:
                continue
            seen.add(key)
            items.append(_item(
                1, f"{ref_kind}  {from_file}:{from_line}  {conf}",
                kind=ref_kind, file=from_file, line=from_line,
                confidence=conf))
        groups.append({
            "title": f"{qualname}  {kind}  {file}:{line_start}",
            "items": items,
        })
    return groups, [], 0


def _inherits_children(qualname, inherits_rows, languages):
    return [(child, file, line)
            for child, parent, file, line in inherits_rows
            if _parent_matches(parent, qualname, languages, file)]


def _tree_items(root_qualname, conn, inherits_rows, implements_rows,
                languages, include_implements):
    """Indented, cycle-safe tree under one root symbol."""
    items = []
    visited = {root_qualname}

    def walk(qualname, depth):
        edges = []
        if include_implements:
            for symbol, interface, file, line, conf in implements_rows:
                if _interface_matches(interface, qualname, languages, file):
                    edges.append((symbol, file, line, "implements", conf))
        for child, file, line in _inherits_children(
                qualname, inherits_rows, languages):
            edges.append((child, file, line, "inherits", "resolved"))
        for symbol, file, line, via, conf in sorted(edges):
            if symbol in visited:
                continue
            visited.add(symbol)
            items.append(_item(
                depth, f"{symbol}  {via}  {file}:{line}  {conf}",
                qualname=symbol, via=via, file=file, line=line,
                confidence=conf))
            walk(symbol, depth + 1)

    walk(root_qualname, 1)
    return items


def _hierarchy(conn, name, include_implements):
    syms = match_symbols(conn, name)
    languages = _load_languages(conn)
    inherits_rows = _load_inherits(conn)
    implements_rows = _load_implements(conn) if include_implements else []
    groups = []
    for qualname, kind, file, line_start, _end, _exp in syms:
        groups.append({
            "title": f"{qualname}  {kind}  {file}:{line_start}",
            "items": _tree_items(qualname, conn, inherits_rows,
                                 implements_rows, languages,
                                 include_implements),
        })
    if not syms:
        # The name may only exist as a raw parent/interface string
        # (e.g. a base class from outside the repo).
        items = []
        visited = set()
        edges = []
        if include_implements:
            edges += [(s, f, l, "implements", c)
                      for s, i, f, l, c in implements_rows
                      if i == name or _last(i) == name]
        edges += [(c, f, l, "inherits", "resolved")
                  for c, p, f, l in inherits_rows
                  if p == name or _last(p) == name]
        for symbol, file, line, via, conf in sorted(edges):
            if symbol in visited:
                continue
            visited.add(symbol)
            items.append(_item(1, f"{symbol}  {via}  {file}:{line}  {conf}",
                               qualname=symbol, via=via, file=file,
                               line=line, confidence=conf))
            for sub in _tree_items(symbol, conn, inherits_rows,
                                   implements_rows, languages,
                                   include_implements):
                items.append(dict(sub, depth=sub["depth"] + 1))
        if not items:
            sys.stderr.write(f"rq: no symbol matching '{name}' in index\n")
            return [], [], 1
        groups.append({"title": f"{name}  (not defined in index)",
                       "items": items})
    return groups, [], 0


def cmd_implements(conn, args):
    return _hierarchy(conn, args.interface, include_implements=True)


def cmd_inherits(conn, args):
    return _hierarchy(conn, args.base, include_implements=False)


def _enclosing_symbol(conn, file, line):
    """Innermost symbol spanning file:line, or None (module level)."""
    row = conn.execute(
        "SELECT qualname, kind FROM symbols "
        "WHERE file = ? AND line_start <= ? AND line_end >= ? "
        "ORDER BY line_start DESC, (line_end - line_start) ASC LIMIT 1",
        (file, line, line)).fetchone()
    return row


def cmd_impact(conn, args):
    """Blast radius: BFS over inbound refs + inherits/implements, one SQL
    query set per level (ADR-003: a recursive CTE cannot express the
    innermost-enclosing-symbol join), ending with covering tests."""
    syms = match_symbols(conn, args.symbol)
    if not syms:
        sys.stderr.write(f"rq: no symbol matching '{args.symbol}' in index\n")
        return [], [], 1
    languages = _load_languages(conn)
    inherits_rows = _load_inherits(conn)
    implements_rows = _load_implements(conn)
    groups = []
    affected_files = set()
    for qualname, kind, file, line_start, _end, _exp in syms:
        affected_files.add(file)
        seen = {qualname}
        frontier = [qualname]
        items = []
        for depth in range(1, args.depth + 1):
            found = []  # (dep_qualname|None, via, file, line, confidence)
            for q in frontier:
                for from_file, from_line, ref_kind, conf in _refs_to(conn, q):
                    enc = _enclosing_symbol(conn, from_file, from_line)
                    dep = enc[0] if enc else None
                    found.append((dep, ref_kind, from_file, from_line, conf))
                for symbol, iface, ifile, iline, iconf in implements_rows:
                    if _interface_matches(iface, q, languages, ifile):
                        found.append((symbol, "implements", ifile, iline,
                                      iconf))
                for child, cfile, cline in _inherits_children(
                        q, inherits_rows, languages):
                    found.append((child, "inherits", cfile, cline,
                                  "resolved"))
            frontier = []
            for dep, via, dfile, dline, conf in sorted(
                    found, key=lambda t: (t[2], t[3], t[0] or "", t[1])):
                key = dep if dep is not None else f"{dfile} (module level)"
                if key in seen:
                    continue
                seen.add(key)
                affected_files.add(dfile)
                label = dep if dep is not None else f"{dfile} (module level)"
                items.append(_item(
                    1, f"{depth}  {label}  {via}  {dfile}:{dline}  {conf}",
                    depth_level=depth, qualname=dep, via=via, file=dfile,
                    line=dline, confidence=conf))
                if dep is not None:
                    frontier.append(dep)
            if not frontier:
                break
        groups.append({
            "title": (f"impact of {qualname}  {kind}  {file}:{line_start}"
                      f"  (max depth {args.depth})"),
            "items": items,
        })

    placeholders = ",".join("?" for _ in affected_files)
    test_rows = conn.execute(
        "SELECT test_file, target_file, source FROM tests "
        f"WHERE target_file IN ({placeholders}) "
        "ORDER BY test_file, target_file",
        sorted(affected_files)).fetchall()
    test_items = [
        _item(1, f"{test_file}:1  covers {target_file}  ({source})",
              test_file=test_file, target_file=target_file, source=source)
        for test_file, target_file, source in test_rows]
    groups.append({"title": "covering tests:", "items": test_items})
    notes = []
    if not test_items:
        notes.append("note: no covering tests found for the affected files")
    return groups, notes, 0


def _path_prefix_match(file, prefix):
    norm = prefix.replace("\\", "/").rstrip("/")
    return file == norm or file.startswith(norm + "/")


def cmd_publicapi(conn, args):
    rows = conn.execute(
        "SELECT qualname, kind, file, line_start FROM symbols "
        "WHERE exported = 1 ORDER BY file, line_start, qualname").fetchall()
    if args.path:
        rows = [r for r in rows if _path_prefix_match(r[2], args.path)]
    items = [_item(0, f"{file}:{line}  {qualname}  {kind}",
                   qualname=qualname, kind=kind, file=file, line=line)
             for qualname, kind, file, line in rows]
    notes = [] if items else ["note: no exported symbols found"]
    return [{"title": None, "items": items}], notes, 0


def _heuristic_caveat(conn):
    n = conn.execute("SELECT COUNT(*) FROM refs "
                     "WHERE confidence = 'heuristic'").fetchone()[0]
    if n:
        return [f"note: index contains {n} heuristic ref(s) -- dynamic or "
                "unresolved uses may hide callers; this list is "
                "conservative, not sound"]
    return []


def cmd_deadcode(conn, args):
    resolved_targets = {r[0] for r in conn.execute(
        "SELECT DISTINCT to_symbol FROM refs WHERE to_symbol IS NOT NULL")}
    heur_names, heur_lasts = set(), set()
    for (to_name,) in conn.execute(
            "SELECT DISTINCT to_name FROM refs WHERE to_symbol IS NULL"):
        heur_names.add(to_name)
        heur_lasts.add(_last(to_name))
    parent_lasts = {_last(p) for _c, p, _f, _l in _load_inherits(conn)}
    iface_names = set()
    for _s, interface, _f, _l, _c in _load_implements(conn):
        iface_names.add(interface)
        iface_names.add(_last(_local(interface)))
    test_files = {r[0] for r in conn.execute(
        "SELECT DISTINCT test_file FROM tests")}

    items = []
    for qualname, kind, file, line, exported in conn.execute(
            "SELECT qualname, kind, file, line_start, exported FROM symbols "
            "ORDER BY file, line_start, qualname"):
        if exported and not args.include_exported:
            continue
        if file in test_files:
            continue  # test symbols are invoked by the runner, not by refs
        local = _local(qualname)
        leaf = _last(local)
        if leaf.startswith("__") and leaf.endswith("__"):
            continue  # dunders are called implicitly by the runtime
        if qualname in resolved_targets:
            continue
        if local in heur_names or leaf in heur_lasts:
            continue
        if leaf in parent_lasts or qualname in iface_names \
                or local in iface_names or leaf in iface_names:
            continue
        items.append(_item(
            0, f"{file}:{line}  {qualname}  {kind}  no inbound refs",
            qualname=qualname, kind=kind, file=file, line=line))
    notes = _heuristic_caveat(conn)
    if not items:
        notes.insert(0, "note: no dead symbols found")
    return [{"title": None, "items": items}], notes, 0


def _module_stem(module, language):
    """Last component of an import's module string, per language."""
    if language == "python":
        return module.lstrip(".").rsplit(".", 1)[-1] or None
    base = module.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    if _family(language) == "js":
        for ext in _JS_EXTS:
            if base.endswith(ext):
                return base[: -len(ext)]
    return base or None


def cmd_findcycles(conn, args):
    languages = _load_languages(conn)
    stems = {}  # (family, stem) -> [path]
    dirs = {}   # (family, dirname-last) -> [path]
    for path, lang in sorted(languages.items()):
        if lang is None:
            continue
        fam = _family(lang)
        base = path.rsplit("/", 1)[-1]
        stem = base.rsplit(".", 1)[0] if "." in base else base
        stems.setdefault((fam, stem), []).append(path)
        d = path.rsplit("/", 1)[0] if "/" in path else ""
        if d:
            dirs.setdefault((fam, d.rsplit("/", 1)[-1]), []).append(path)

    edges = {}  # (from_path, to_path) -> first import line
    for file, line, module in conn.execute(
            "SELECT file, line, module FROM imports ORDER BY file, line"):
        lang = languages.get(file)
        if lang is None:
            continue
        fam = _family(lang)
        stem = _module_stem(module, lang)
        if not stem:
            continue
        cands = stems.get((fam, stem), [])
        if lang == "go":
            cands = cands + [p for p in dirs.get((fam, stem), [])
                             if p not in cands]
        same_dir = [p for p in cands
                    if p.rsplit("/", 1)[0] == file.rsplit("/", 1)[0]]
        if same_dir:
            cands = same_dir
        for target in cands:
            if target != file:
                edges.setdefault((file, target), line)

    adj = {}
    for (a, b) in edges:
        adj.setdefault(a, []).append(b)
    for a in adj:
        adj[a].sort()

    sccs = _tarjan(sorted(set(languages) | set(adj)), adj)
    cycles = sorted((sorted(scc) for scc in sccs if len(scc) > 1),
                    key=lambda c: (len(c), c))
    groups = []
    for i, cycle in enumerate(cycles, 1):
        members = set(cycle)
        items = [_item(1, f"{a}:{line}  imports {b}",
                       file=a, line=line, imports=b)
                 for (a, b), line in sorted(edges.items(),
                                            key=lambda kv: (kv[0][0], kv[1]))
                 if a in members and b in members]
        groups.append({"title": f"cycle {i} ({len(cycle)} files):",
                       "items": items})
    notes = [] if cycles else ["note: no import cycles found"]
    return groups, notes, 0


def _tarjan(nodes, adj):
    """Iterative Tarjan SCC (deterministic given sorted nodes/adjacency)."""
    index = {}
    low = {}
    on_stack = set()
    stack = []
    sccs = []
    counter = [0]

    for root in nodes:
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, ei = work[-1]
            if ei == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack.add(node)
            neighbors = adj.get(node, [])
            advanced = False
            while ei < len(neighbors):
                nxt = neighbors[ei]
                ei += 1
                if nxt not in index:
                    work[-1] = (node, ei)
                    work.append((nxt, 0))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if low[node] == index[node]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(scc)
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
    return sccs


def cmd_untested(conn, args):
    covered = {r[0] for r in conn.execute(
        "SELECT DISTINCT target_file FROM tests")}
    test_files = {r[0] for r in conn.execute(
        "SELECT DISTINCT test_file FROM tests")}
    items = []
    for qualname, kind, file, line in conn.execute(
            "SELECT qualname, kind, file, line_start FROM symbols "
            "WHERE exported = 1 ORDER BY file, line_start, qualname"):
        if file in covered or file in test_files:
            continue
        items.append(_item(
            0, f"{file}:{line}  {qualname}  {kind}  no covering tests",
            qualname=qualname, kind=kind, file=file, line=line))
    notes = [] if items else \
        ["note: every file with exported symbols has a covering test"]
    return [{"title": None, "items": items}], notes, 0


# --------------------------------------------------------------- main ---

_COMMANDS = {
    "whouses": cmd_whouses,
    "implements": cmd_implements,
    "inherits": cmd_inherits,
    "impact": cmd_impact,
    "publicapi": cmd_publicapi,
    "deadcode": cmd_deadcode,
    "findcycles": cmd_findcycles,
    "untested": cmd_untested,
}


def _add_shared_flags(parser, top_level):
    # The same flags live on the top-level parser (with real defaults) and on
    # every subparser (defaults SUPPRESSed).  A subparser default would
    # otherwise clobber a value parsed before the subcommand; with SUPPRESS,
    # `rq --json whouses X` and `rq whouses X --json` both work and the
    # post-subcommand position wins when both are given.
    d = (lambda v: v) if top_level else (lambda v: argparse.SUPPRESS)
    parser.add_argument("--root", default=d("."),
                        help="repo root (default: cwd)")
    parser.add_argument("--json", action="store_true", default=d(False),
                        help="emit JSON instead of text")
    parser.add_argument("--max-tokens", type=int, default=d(None),
                        help="token budget; leaf lists collapse to counts")
    parser.add_argument("--repoindex", default=d(None),
                        help="repoindex command for the freshness guard "
                             "(default: repoindex on PATH or the sibling "
                             "checkout; env RQ_REPOINDEX)")
    parser.add_argument("--no-update", action="store_true", default=d(False),
                        help="skip the automatic `repoindex update`")


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    _add_shared_flags(common, top_level=False)

    parser = argparse.ArgumentParser(
        prog="rq", description="query pack over .repoindex/index.db")
    _add_shared_flags(parser, top_level=True)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("whouses", parents=[common],
                       help="inbound refs, grouped by kind")
    p.add_argument("symbol")
    p = sub.add_parser("implements", parents=[common],
                       help="implementations of an interface, as a tree")
    p.add_argument("interface")
    p = sub.add_parser("inherits", parents=[common], help="subclass tree")
    p.add_argument("base")
    p = sub.add_parser("impact", parents=[common],
                       help="blast radius + covering tests")
    p.add_argument("symbol")
    p.add_argument("--depth", type=int, default=3,
                   help="max transitive depth (default 3)")
    p = sub.add_parser("publicapi", parents=[common],
                       help="exported symbols, optionally under PATH")
    p.add_argument("path", nargs="?", default=None)
    p = sub.add_parser("deadcode", parents=[common],
                       help="symbols with zero inbound refs")
    p.add_argument("--include-exported", action="store_true",
                   help="also list exported symbols (default: excluded)")
    sub.add_parser("findcycles", parents=[common],
                   help="import cycles between files, smallest first")
    sub.add_parser("untested", parents=[common],
                   help="exported symbols with no covering test")

    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)

    if not args.no_update:
        ensure_fresh(root, args.repoindex)
    conn = open_db(root)
    if conn is None:
        sys.stderr.write("rq: no index at .repoindex/index.db and "
                         "`repoindex` is unavailable -- run "
                         "`repoindex build` first\n")
        return 2

    groups, notes, status = _COMMANDS[args.command](conn, args)
    conn.close()
    if status != 0:
        return status
    sys.stdout.write(render(args.command, groups, notes,
                            as_json=args.json, max_tokens=args.max_tokens))
    return 0


if __name__ == "__main__":
    sys.exit(main())
