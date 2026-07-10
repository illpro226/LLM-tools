"""SQLite schema and writer for .repoindex/index.db (ADR-001)."""
from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    language TEXT,
    mtime REAL NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbols (
    id INTEGER PRIMARY KEY,
    qualname TEXT NOT NULL,
    kind TEXT NOT NULL,
    file TEXT NOT NULL,
    line_start INTEGER NOT NULL,
    line_end INTEGER NOT NULL,
    exported INTEGER NOT NULL,
    FOREIGN KEY (file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_symbols_qualname ON symbols(qualname);
CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file);

CREATE TABLE IF NOT EXISTS refs (
    id INTEGER PRIMARY KEY,
    from_file TEXT NOT NULL,
    from_line INTEGER NOT NULL,
    to_name TEXT NOT NULL,
    to_symbol TEXT,
    kind TEXT NOT NULL,
    confidence TEXT NOT NULL,
    FOREIGN KEY (from_file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_refs_to_symbol ON refs(to_symbol);
CREATE INDEX IF NOT EXISTS idx_refs_from_file ON refs(from_file);

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    module TEXT NOT NULL,
    symbol TEXT,
    alias TEXT,
    FOREIGN KEY (file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_imports_file ON imports(file);

CREATE TABLE IF NOT EXISTS inherits (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    child TEXT NOT NULL,
    parent TEXT NOT NULL,
    FOREIGN KEY (file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_inherits_child ON inherits(child);

CREATE TABLE IF NOT EXISTS implements (
    id INTEGER PRIMARY KEY,
    file TEXT NOT NULL,
    line INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    interface TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'resolved',
    FOREIGN KEY (file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_implements_symbol ON implements(symbol);

CREATE TABLE IF NOT EXISTS tests (
    id INTEGER PRIMARY KEY,
    test_file TEXT NOT NULL,
    target_file TEXT NOT NULL,
    source TEXT NOT NULL,
    FOREIGN KEY (test_file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_tests_target ON tests(target_file);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Go has no `implements` keyword; go_structural_implements() needs each
-- interface's method-name set to do a real (if name-only) satisfaction
-- check. Persisted separately so an `update` that skips re-parsing an
-- unchanged Go file can still reconstruct its interfaces.
CREATE TABLE IF NOT EXISTS go_iface_methods (
    file TEXT NOT NULL,
    interface TEXT NOT NULL,
    method TEXT NOT NULL,
    FOREIGN KEY (file) REFERENCES files(path)
);
CREATE INDEX IF NOT EXISTS idx_go_iface_file ON go_iface_methods(file);
"""


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)


def delete_file_rows(conn, path):
    """Delete every row belonging to `path` across all relationship tables."""
    conn.execute("DELETE FROM symbols WHERE file = ?", (path,))
    conn.execute("DELETE FROM refs WHERE from_file = ?", (path,))
    conn.execute("DELETE FROM imports WHERE file = ?", (path,))
    conn.execute("DELETE FROM inherits WHERE file = ?", (path,))
    conn.execute("DELETE FROM implements WHERE file = ?", (path,))
    conn.execute("DELETE FROM tests WHERE test_file = ?", (path,))
    conn.execute("DELETE FROM go_iface_methods WHERE file = ?", (path,))
    conn.execute("DELETE FROM files WHERE path = ?", (path,))


def write_file_record(conn, path, language, mtime, content_hash):
    conn.execute(
        "INSERT INTO files (path, language, mtime, hash) VALUES (?, ?, ?, ?)",
        (path, language, mtime, content_hash))


def write_extracted(conn, ef):
    """Write an ExtractedFile's symbols/imports/inherits/implements (not refs;
    refs are written repo-wide after resolution, see write_resolved_refs)."""
    for s in ef.symbols:
        conn.execute(
            "INSERT INTO symbols (qualname, kind, file, line_start, "
            "line_end, exported) VALUES (?, ?, ?, ?, ?, ?)",
            (s.qualname, s.kind, s.file, s.line_start, s.line_end,
             int(s.exported)))
    for imp in ef.imports:
        conn.execute(
            "INSERT INTO imports (file, line, module, symbol, alias) "
            "VALUES (?, ?, ?, ?, ?)",
            (imp.file, imp.line, imp.module, imp.symbol, imp.alias))
    for inh in ef.inherits:
        conn.execute(
            "INSERT INTO inherits (file, line, child, parent) "
            "VALUES (?, ?, ?, ?)",
            (inh.file, inh.line, inh.child, inh.parent))
    for impl in ef.implements:
        conn.execute(
            "INSERT INTO implements (file, line, symbol, interface, "
            "confidence) VALUES (?, ?, ?, ?, 'resolved')",
            (impl.file, impl.line, impl.symbol, impl.interface))
    for iface_name, methods in ef.extra.get("go_interfaces", {}).items():
        for method in methods:
            conn.execute(
                "INSERT INTO go_iface_methods (file, interface, method) "
                "VALUES (?, ?, ?)", (ef.path, iface_name, method))


def write_resolved_refs(conn, resolved_refs):
    for r in resolved_refs:
        conn.execute(
            "INSERT INTO refs (from_file, from_line, to_name, to_symbol, "
            "kind, confidence) VALUES (?, ?, ?, ?, ?, ?)",
            (r.file, r.line, r.to_name, r.to_symbol, r.kind, r.confidence))


def write_go_implements(conn, implements):
    for impl in implements:
        conn.execute(
            "INSERT INTO implements (file, line, symbol, interface, "
            "confidence) VALUES (?, ?, ?, ?, 'heuristic')",
            (impl.file, impl.line, impl.symbol, impl.interface))


def write_test_links(conn, links):
    for link in links:
        conn.execute(
            "INSERT INTO tests (test_file, target_file, source) "
            "VALUES (?, ?, ?)",
            (link.test_file, link.target_file, link.source))


def load_extracted_from_db(conn, path, language):
    """Reconstruct an ExtractedFile-shaped object for an unchanged file so
    the repo-wide resolve/test-seed/go-implements passes can run over the
    full file set without re-parsing untouched files."""
    from .extract import ExtractedFile, Symbol, Ref, Import, Inherit, Implement

    ef = ExtractedFile(path=path, language=language)
    for row in conn.execute(
            "SELECT qualname, kind, line_start, line_end, exported "
            "FROM symbols WHERE file = ?", (path,)):
        ef.symbols.append(Symbol(qualname=row[0], kind=row[1], file=path,
                                  line_start=row[2], line_end=row[3],
                                  exported=bool(row[4])))
    for row in conn.execute(
            "SELECT line, module, symbol, alias FROM imports "
            "WHERE file = ?", (path,)):
        ef.imports.append(Import(file=path, line=row[0], module=row[1],
                                  symbol=row[2], alias=row[3]))
    for row in conn.execute(
            "SELECT line, child, parent FROM inherits WHERE file = ?",
            (path,)):
        ef.inherits.append(Inherit(file=path, line=row[0], child=row[1],
                                    parent=row[2]))
    for row in conn.execute(
            "SELECT line, symbol, interface FROM implements "
            "WHERE file = ? AND confidence = 'resolved'", (path,)):
        ef.implements.append(Implement(file=path, line=row[0], symbol=row[1],
                                        interface=row[2]))
    for row in conn.execute(
            "SELECT from_line, to_name, kind FROM refs WHERE from_file = ?",
            (path,)):
        ef.refs.append(Ref(file=path, line=row[0], to_name=row[1], kind=row[2]))
    if language == "go":
        ifaces = {}
        for row in conn.execute(
                "SELECT interface, method FROM go_iface_methods "
                "WHERE file = ?", (path,)):
            ifaces.setdefault(row[0], set()).add(row[1])
        ef.extra["go_interfaces"] = ifaces
    return ef


def clear_refs_and_derived(conn):
    """Refs/implements(go)/tests are repo-wide derivations, not per-file rows;
    a full rebuild of them is cheap and avoids stale cross-file edges after
    any file changes. Coverage-tagged test rows are the exception: they are
    recorded by `testmap record`, not derivable from source, so they persist
    until their test file changes (delete_file_rows) or either endpoint
    leaves the repo."""
    conn.execute("DELETE FROM refs")
    conn.execute("DELETE FROM implements WHERE confidence = 'heuristic'")
    conn.execute("DELETE FROM tests WHERE source != 'coverage'")
    conn.execute("DELETE FROM tests WHERE source = 'coverage' AND ("
                 "test_file NOT IN (SELECT path FROM files) "
                 "OR target_file NOT IN (SELECT path FROM files))")
