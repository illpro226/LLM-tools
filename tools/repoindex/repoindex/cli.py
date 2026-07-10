"""repoindex CLI: build / update / status / sql over .repoindex/index.db."""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import sys

from . import db as dbmod
from . import extract as extractmod
from . import resolve as resolvemod
from . import walk as walkmod

DB_RELPATH = os.path.join(".repoindex", "index.db")


def _db_path(root):
    return os.path.join(root, DB_RELPATH)


def _read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
        return f.read()


def _hash(content):
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _mtime(root, rel):
    return os.path.getmtime(os.path.join(root, rel))


def _run_repo_wide(conn, all_files, root):
    resolved = resolvemod.resolve_refs(all_files, root)
    dbmod.write_resolved_refs(conn, resolved)
    dbmod.write_go_implements(conn, resolvemod.go_structural_implements(all_files))
    dbmod.write_test_links(conn, resolvemod.seed_tests(all_files, root))


def build(root="."):
    root = os.path.abspath(root)
    os.makedirs(os.path.join(root, ".repoindex"), exist_ok=True)
    db_path = _db_path(root)
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = dbmod.connect(db_path)
    dbmod.init_schema(conn)

    paths = walkmod.scan_repo(root)
    all_files = []
    for rel in paths:
        content = _read(root, rel)
        lang = extractmod.detect_language(rel, content)
        ef = extractmod.extract(rel, content, lang=lang)
        all_files.append(ef)
        dbmod.write_file_record(conn, rel, lang, _mtime(root, rel), _hash(content))
        dbmod.write_extracted(conn, ef)

    _run_repo_wide(conn, all_files, root)
    conn.commit()
    conn.close()
    added = walkmod.ensure_gitignore_entry(root)

    n_symbols = sum(len(f.symbols) for f in all_files)
    print(f"repoindex: built {len(paths)} files, {n_symbols} symbols -> "
          f"{os.path.relpath(db_path, root)}")
    if added:
        print("repoindex: added .repoindex/ to .gitignore")
    return 0


def update(root="."):
    root = os.path.abspath(root)
    db_path = _db_path(root)
    if not os.path.exists(db_path):
        return build(root)

    conn = dbmod.connect(db_path)
    dbmod.init_schema(conn)

    known = {row[0]: (row[1], row[2], row[3]) for row in
              conn.execute("SELECT path, language, mtime, hash FROM files")}
    paths = set(walkmod.scan_repo(root))

    removed = set(known) - paths
    for rel in removed:
        dbmod.delete_file_rows(conn, rel)

    changed, unchanged = [], []
    for rel in sorted(paths):
        mtime = _mtime(root, rel)
        prior = known.get(rel)
        if prior is None:
            changed.append(rel)
            continue
        _prior_lang, prior_mtime, prior_hash = prior
        if mtime == prior_mtime:
            unchanged.append(rel)
            continue
        content = _read(root, rel)
        if _hash(content) == prior_hash:
            conn.execute("UPDATE files SET mtime = ? WHERE path = ?", (mtime, rel))
            unchanged.append(rel)
            continue
        changed.append(rel)

    all_files = [dbmod.load_extracted_from_db(conn, rel, known[rel][0])
                 for rel in unchanged]

    for rel in changed:
        content = _read(root, rel)
        lang = extractmod.detect_language(rel, content)
        ef = extractmod.extract(rel, content, lang=lang)
        dbmod.delete_file_rows(conn, rel)
        dbmod.write_file_record(conn, rel, lang, _mtime(root, rel), _hash(content))
        dbmod.write_extracted(conn, ef)
        all_files.append(ef)

    dbmod.clear_refs_and_derived(conn)
    _run_repo_wide(conn, all_files, root)
    conn.commit()
    conn.close()

    print(f"repoindex: updated {len(changed)} changed, "
          f"{len(unchanged)} unchanged, {len(removed)} removed")
    return 0


def status(root="."):
    root = os.path.abspath(root)
    db_path = _db_path(root)
    if not os.path.exists(db_path):
        print("repoindex: no index -- run `repoindex build`")
        return 1

    conn = dbmod.connect(db_path)
    known = {row[0]: (row[1], row[2]) for row in
              conn.execute("SELECT path, language, mtime FROM files")}
    paths = set(walkmod.scan_repo(root))

    stale = [rel for rel in paths & set(known)
             if _mtime(root, rel) != known[rel][1]]
    new_on_disk = paths - set(known)
    missing = set(known) - paths
    fresh = not stale and not new_on_disk and not missing

    lang_files, lang_symbols = {}, {}
    for lang, count in conn.execute(
            "SELECT language, COUNT(*) FROM files GROUP BY language"):
        lang_files[lang or "unknown"] = count
    for lang, count in conn.execute(
            "SELECT f.language, COUNT(*) FROM symbols s "
            "JOIN files f ON f.path = s.file GROUP BY f.language"):
        lang_symbols[lang or "unknown"] = count
    conn.close()

    print(f"repoindex status: {'fresh' if fresh else 'stale'}")
    if stale:
        print(f"  {len(stale)} file(s) changed since last index")
    if new_on_disk:
        print(f"  {len(new_on_disk)} new file(s) not yet indexed")
    if missing:
        print(f"  {len(missing)} indexed file(s) no longer on disk")
    for lang in sorted(lang_files):
        print(f"  {lang}: {lang_files[lang]} files, "
              f"{lang_symbols.get(lang, 0)} symbols")
    return 0


_WRITE_RE = re.compile(
    r"^\s*(insert|update|delete|drop|alter|create|replace|attach|pragma|vacuum)\b",
    re.IGNORECASE)


def sql(root, query):
    root = os.path.abspath(root)
    db_path = _db_path(root)
    if not os.path.exists(db_path):
        print("repoindex: no index -- run `repoindex build`", file=sys.stderr)
        return 1
    if _WRITE_RE.match(query):
        print("repoindex sql: read-only -- write statements are rejected",
              file=sys.stderr)
        return 2

    uri = f"file:{db_path.replace(os.sep, '/')}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.execute(query)
        rows = cur.fetchall()
    except sqlite3.Error as e:
        print(f"repoindex sql: {e}", file=sys.stderr)
        return 2
    cols = [d[0] for d in cur.description] if cur.description else []
    _print_table(cols, rows)
    conn.close()
    return 0


def _print_table(cols, rows):
    if not cols:
        return
    str_rows = [["" if v is None else str(v) for v in row] for row in rows]
    widths = [len(c) for c in cols]
    for row in str_rows:
        for i, v in enumerate(row):
            widths[i] = max(widths[i], len(v))

    def fmt(vals):
        return "  ".join(v.ljust(widths[i]) for i, v in enumerate(vals))

    print(fmt(cols))
    print(fmt(["-" * w for w in widths]))
    for row in str_rows:
        print(fmt(row))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="repoindex")
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build")
    sub.add_parser("update")
    sub.add_parser("status")
    sql_parser = sub.add_parser("sql")
    sql_parser.add_argument("query")

    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.root)
    if args.command == "update":
        return update(args.root)
    if args.command == "status":
        return status(args.root)
    if args.command == "sql":
        return sql(args.root, args.query)
    return 1


if __name__ == "__main__":
    sys.exit(main())
