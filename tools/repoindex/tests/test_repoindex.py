import os
import sqlite3
import time

import pytest

from repoindex import cli, extract


def _connect(repo):
    return sqlite3.connect(str(repo / ".repoindex" / "index.db"))


def _rows(conn, query, params=()):
    return conn.execute(query, params).fetchall()


def _touch(path, delta=5):
    future = time.time() + delta
    os.utime(path, (future, future))


# --------------------------------------------------------- per-table extraction

def test_build_creates_expected_tables(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    for table in ("files", "symbols", "refs", "imports", "inherits",
                  "implements", "tests"):
        conn.execute(f"SELECT * FROM {table} LIMIT 1")  # raises if missing


def test_python_symbols_visibility(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = {r[0]: r for r in _rows(
        conn, "SELECT qualname, kind, exported, line_start FROM symbols "
              "WHERE file = 'py/mathutil.py'")}
    assert rows["py/mathutil.py::add"][1] == "func"
    assert rows["py/mathutil.py::add"][2] == 1
    assert rows["py/mathutil.py::_scale"][2] == 0
    assert rows["py/mathutil.py::PI"][1] == "const"


def test_python_class_and_methods(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = {r[0]: r[1] for r in _rows(
        conn, "SELECT qualname, kind FROM symbols WHERE file = 'py/shapes.py'")}
    assert rows["py/shapes.py::Rectangle"] == "class"
    assert rows["py/shapes.py::Rectangle.area"] == "method"
    assert rows["py/shapes.py::Square"] == "class"


def test_python_inheritance_chain_and_abc_implements(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    inh = _rows(conn, "SELECT child, parent FROM inherits "
                       "WHERE file = 'py/shapes.py'")
    assert ("py/shapes.py::Square", "Rectangle") in inh
    impl = _rows(conn, "SELECT symbol, interface FROM implements "
                        "WHERE file = 'py/shapes.py'")
    assert ("py/shapes.py::Rectangle", "Shape") in impl


def test_python_imports_with_alias(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    imps = _rows(conn, "SELECT module, symbol, alias FROM imports "
                        "WHERE file = 'py/app.py'")
    assert ("shapes", "Square", "Sq") in imps
    assert ("mathutil", "add", None) in imps


def test_go_symbols_and_visibility(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = {r[0]: r[1] for r in _rows(
        conn, "SELECT qualname, exported FROM symbols "
              "WHERE file = 'go/mathutil/mathutil.go'")}
    assert rows["go/mathutil/mathutil.go::Add"] == 1
    assert rows["go/mathutil/mathutil.go::privateHelper"] == 0


def test_js_ts_class_interface_and_methods(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    kinds = {r[0]: r[1] for r in _rows(
        conn, "SELECT qualname, kind FROM symbols WHERE file = 'js/shapes.ts'")}
    assert kinds["js/shapes.ts::Shape"] == "interface"
    assert kinds["js/shapes.ts::Rectangle"] == "class"
    assert kinds["js/shapes.ts::Rectangle.area"] == "method"


def test_js_ts_extends_and_implements(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    inh = _rows(conn, "SELECT child, parent FROM inherits "
                       "WHERE file = 'js/shapes.ts'")
    assert ("js/shapes.ts::Square", "Rectangle") in inh
    impl = _rows(conn, "SELECT symbol, interface FROM implements "
                        "WHERE file = 'js/shapes.ts'")
    assert ("js/shapes.ts::Rectangle", "Shape") in impl


# --------------------------------------------------------------- resolution

def test_call_cycle_resolved(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT to_symbol, confidence FROM refs "
                        "WHERE from_file='py/app.py' AND to_name='pong'")
    assert rows == [("py/app.py::pong", "resolved")]
    rows = _rows(conn, "SELECT to_symbol, confidence FROM refs "
                        "WHERE from_file='py/app.py' AND to_name='ping'")
    assert ("py/app.py::ping", "resolved") in rows


def test_import_linked_call_resolved(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT to_symbol, confidence FROM refs "
                        "WHERE from_file='py/app.py' AND to_name='add'")
    assert rows == [("py/mathutil.py::add", "resolved")]


def test_dynamic_call_is_heuristic_not_dropped(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT to_name, confidence FROM refs "
                        "WHERE from_file='py/dynamic.py'")
    assert rows  # not dropped
    assert all(conf == "heuristic" for _, conf in rows)


def test_ambiguous_bare_name_is_heuristic(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT to_symbol, confidence FROM refs "
                        "WHERE from_file='py/dynamic.py' AND to_name='run'")
    assert rows == [(None, "heuristic")]
    # both candidates genuinely exist -- the ambiguity is real, not a miss
    both = _rows(conn, "SELECT qualname FROM symbols WHERE qualname LIKE '%::run'")
    assert len(both) == 2


def test_reads_and_writes_resolved(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    kinds = {r[0] for r in _rows(
        conn, "SELECT kind FROM refs WHERE from_file='py/app.py' "
              "AND to_name='counter'")}
    assert "read" in kinds
    assert "write" in kinds


def test_type_use_resolved(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT to_symbol FROM refs WHERE from_file='py/app.py' "
                        "AND kind='type-use' AND to_name='Rectangle'")
    assert rows and rows[0][0] == "py/shapes.py::Rectangle"


def test_go_structural_implements_is_heuristic(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT symbol, interface, confidence FROM implements "
                        "WHERE file LIKE 'go/shapes%'")
    assert len(rows) == 2
    assert all(conf == "heuristic" for _, _, conf in rows)


def test_dead_symbol_has_no_inbound_refs(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT * FROM refs "
                        "WHERE to_symbol = 'py/dead.py::unused_helper'")
    assert rows == []


# ------------------------------------------------------------ test seeding

def test_import_linked_test(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT source FROM tests WHERE "
                        "test_file='tests_py/test_mathutil.py' "
                        "AND target_file='py/mathutil.py'")
    assert rows == [("import",)]


def test_convention_linked_test(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT source FROM tests WHERE "
                        "test_file='tests_py/test_app.py' "
                        "AND target_file='py/app.py'")
    assert rows == [("convention",)]


def test_go_test_links(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT test_file, target_file, source FROM tests "
                        "WHERE test_file LIKE 'go/%'")
    assert ("go/mathutil/mathutil_test.go", "go/mathutil/mathutil.go",
            "convention") in rows
    assert ("go/integration/integration_test.go", "go/mathutil/mathutil.go",
            "import") in rows


# --------------------------------------------------------- incremental update

def test_update_does_not_reparse_untouched_file(repo, monkeypatch):
    cli.build(str(repo))
    calls = []
    real_extract = extract.extract

    def spy(path, source, lang=None):
        calls.append(path)
        return real_extract(path, source, lang=lang)

    monkeypatch.setattr(extract, "extract", spy)

    _touch(repo / "py" / "dead.py")  # mtime only, no content change
    changed = repo / "py" / "mathutil.py"
    changed.write_text(changed.read_text() + "\n\ndef extra():\n    return 1\n")

    cli.update(str(repo))

    reparsed = {os.path.basename(c) for c in calls}
    assert "mathutil.py" in reparsed
    assert "dead.py" not in reparsed


def test_update_hash_short_circuits_mtime_only_touch(repo, monkeypatch):
    cli.build(str(repo))
    calls = []
    real_extract = extract.extract
    monkeypatch.setattr(extract, "extract",
                          lambda p, s, lang=None: (calls.append(p),
                                                    real_extract(p, s, lang=lang))[1])

    _touch(repo / "py" / "dead.py")
    cli.update(str(repo))
    assert not calls


def test_update_reflects_new_symbol(repo):
    cli.build(str(repo))
    changed = repo / "py" / "mathutil.py"
    changed.write_text(changed.read_text() + "\n\ndef extra():\n    return 1\n")
    cli.update(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT qualname FROM symbols "
                        "WHERE qualname='py/mathutil.py::extra'")
    assert rows


def test_update_removes_deleted_file_rows(repo):
    cli.build(str(repo))
    (repo / "py" / "dead.py").unlink()
    cli.update(str(repo))
    conn = _connect(repo)
    assert _rows(conn, "SELECT * FROM files WHERE path='py/dead.py'") == []
    assert _rows(conn, "SELECT * FROM symbols WHERE file='py/dead.py'") == []


def test_update_preserves_coverage_test_rows(repo):
    """testmap-recorded coverage rows are not derivable from source; an
    update must not wipe them (db.clear_refs_and_derived exception)."""
    cli.build(str(repo))
    conn = _connect(repo)
    conn.execute("INSERT INTO tests (test_file, target_file, source) "
                 "VALUES ('tests_py/test_mathutil.py', 'py/app.py', "
                 "'coverage')")
    conn.commit()
    conn.close()

    changed = repo / "py" / "mathutil.py"
    changed.write_text(changed.read_text() + "\n\ndef extra():\n    return 1\n")
    cli.update(str(repo))

    conn = _connect(repo)
    rows = _rows(conn, "SELECT source FROM tests WHERE "
                        "test_file='tests_py/test_mathutil.py' "
                        "AND target_file='py/app.py'")
    assert rows == [("coverage",)]


def test_update_drops_coverage_rows_for_removed_files(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    conn.execute("INSERT INTO tests (test_file, target_file, source) "
                 "VALUES ('tests_py/test_mathutil.py', 'py/dead.py', "
                 "'coverage')")
    conn.commit()
    conn.close()

    (repo / "py" / "dead.py").unlink()
    cli.update(str(repo))

    conn = _connect(repo)
    assert _rows(conn, "SELECT * FROM tests WHERE source='coverage'") == []


class _CountingConn:
    """sqlite3.Connection can't be monkeypatched directly (immutable C type);
    wrap it instead so `.commit()` calls can be counted."""

    def __init__(self, inner, commits):
        self._inner = inner
        self._commits = commits

    def commit(self):
        self._commits.append(1)
        return self._inner.commit()

    def __getattr__(self, name):
        return getattr(self._inner, name)


def test_build_is_one_transaction(repo, monkeypatch):
    from repoindex import db as dbmod
    commits = []
    real_connect = dbmod.connect
    monkeypatch.setattr(dbmod, "connect",
                          lambda p: _CountingConn(real_connect(p), commits))
    cli.build(str(repo))
    assert len(commits) == 1


def test_update_is_one_transaction(repo, monkeypatch):
    cli.build(str(repo))
    from repoindex import db as dbmod
    commits = []
    real_connect = dbmod.connect
    monkeypatch.setattr(dbmod, "connect",
                          lambda p: _CountingConn(real_connect(p), commits))
    changed = repo / "py" / "mathutil.py"
    changed.write_text(changed.read_text() + "\n\ndef extra():\n    return 1\n")
    cli.update(str(repo))
    assert len(commits) == 1


# ------------------------------------------------------------------- status

def test_status_fresh_after_build(repo, capsys):
    cli.build(str(repo))
    capsys.readouterr()
    code = cli.status(str(repo))
    out = capsys.readouterr().out
    assert code == 0
    assert "fresh" in out
    assert "python:" in out


def test_status_stale_after_edit(repo, capsys):
    cli.build(str(repo))
    capsys.readouterr()
    _touch(repo / "py" / "mathutil.py")
    code = cli.status(str(repo))
    out = capsys.readouterr().out
    assert code == 0
    assert "stale" in out


def test_status_no_index_is_clear_error(repo, capsys):
    code = cli.status(str(repo))
    out = capsys.readouterr().out
    assert code == 1
    assert "build" in out


# ---------------------------------------------------------------------- sql

def test_sql_select_column_aligned(repo, capsys):
    cli.build(str(repo))
    capsys.readouterr()
    code = cli.sql(str(repo), "SELECT path FROM files WHERE path='py/mathutil.py'")
    out = capsys.readouterr().out
    assert code == 0
    lines = out.splitlines()
    assert lines[0].strip() == "path"
    assert "py/mathutil.py" in lines[2]


@pytest.mark.parametrize("stmt", [
    "DELETE FROM files",
    "UPDATE files SET path='x'",
    "DROP TABLE files",
    "INSERT INTO files VALUES ('x','python',0,'h')",
])
def test_sql_rejects_writes(repo, capsys, stmt):
    cli.build(str(repo))
    capsys.readouterr()
    code = cli.sql(str(repo), stmt)
    err = capsys.readouterr().err
    assert code != 0
    assert "read-only" in err


# ------------------------------------------------------------- library surface

def test_extract_is_pure_and_standalone():
    ef = extract.extract("standalone.py", "def f():\n    return 1\n")
    assert ef.symbols[0].qualname == "standalone.py::f"
    assert ef.language == "python"


def test_extract_takes_content_not_a_real_path(tmp_path):
    missing = str(tmp_path / "does_not_exist_on_disk.py")
    ef = extract.extract(missing, "def g():\n    pass\n")
    assert ef.symbols[0].qualname == f"{missing}::g"


# --------------------------------------------------- extraction regressions

def test_js_braces_in_comments_do_not_corrupt_depth():
    src = (
        "// helper { brace inside a line comment\n"
        "/* and one inside a block comment } */\n"
        "export function foo() {\n"
        "  return 1;\n"
        "}\n"
        "export function bar() {\n"
        "  return 2;\n"
        "}\n"
    )
    ef = extract.extract("a.js", src)
    names = {s.qualname for s in ef.symbols}
    assert "a.js::foo" in names
    assert "a.js::bar" in names


def test_python_module_level_call_is_a_ref():
    ef = extract.extract("m.py", "def create():\n    return 1\n\napp = create()\n")
    assert ("create", "call") in {(r.to_name, r.kind) for r in ef.refs}


def test_python_class_body_call_is_a_ref():
    src = "def factory():\n    return []\n\nclass C:\n    items = factory()\n"
    ef = extract.extract("m.py", src)
    assert ("factory", "call") in {(r.to_name, r.kind) for r in ef.refs}


def test_python_nested_def_refs_not_double_counted():
    src = (
        "def target():\n    return 1\n\n"
        "if True:\n"
        "    def wrapper():\n"
        "        return target()\n"
    )
    ef = extract.extract("m.py", src)
    assert len([r for r in ef.refs if r.to_name == "target"]) == 1


def test_python_local_shadowing_does_not_resolve():
    # Known-issue repoindex-local-var-shadowing-resolved-ref: a call through
    # a function-local variable must not resolve to an unrelated repo-wide
    # symbol of the same name. The call becomes <dynamic> (heuristic).
    from repoindex import resolve
    lib = extract.extract(
        "other/extractors.py", "def extract(src):\n    return src\n")
    use = extract.extract(
        "tool/main.py",
        "def pick():\n    return len\n\n"
        "def run(src):\n"
        "    extract = pick()\n"
        "    return extract(src)\n")
    rows = resolve.resolve_refs([lib, use])
    assert not [r for r in rows
                if r.file == "tool/main.py" and r.to_name == "extract"]
    dyn = [r for r in rows
           if r.file == "tool/main.py" and r.to_name == "<dynamic>"]
    assert dyn and all(r.confidence == "heuristic" for r in dyn)


def test_python_call_through_parameter_is_dynamic():
    ef = extract.extract(
        "m.py", "def apply(fn, x):\n    return fn(x)\n")
    assert ("fn", "call") not in {(r.to_name, r.kind) for r in ef.refs}
    assert ("<dynamic>", "call") in {(r.to_name, r.kind) for r in ef.refs}


def test_python_local_assignment_shadows_module_var_refs():
    # `x = ...` inside a function without `global` binds a local; it is not
    # a write to the module-level `x` (and later reads are local too).
    src = "x = 1\n\ndef f():\n    x = 2\n    return x\n\ndef g():\n    global x\n    x = 3\n"
    ef = extract.extract("m.py", src)
    writes = [r for r in ef.refs if r.to_name == "x" and r.kind == "write"]
    assert [w.line for w in writes] == [9]  # only the `global x` write


def test_ts_local_shadowing_does_not_resolve():
    # Same known issue as the Python case, JS/TS side: a call through a
    # function-local binding must not resolve to an unrelated repo-wide
    # symbol of the same name.
    from repoindex import resolve
    lib = extract.extract(
        "other/extractors.ts",
        "export function extract(src: string) {\n  return src;\n}\n")
    use = extract.extract(
        "tool/main.ts",
        "function pick() {\n  return null;\n}\n"
        "export function run(src) {\n"
        "  const extract = pick();\n"
        "  return extract(src);\n"
        "}\n")
    rows = resolve.resolve_refs([lib, use])
    assert not [r for r in rows
                if r.file == "tool/main.ts" and r.to_name == "extract"]
    dyn = [r for r in rows
           if r.file == "tool/main.ts" and r.to_name == "<dynamic>"]
    assert dyn and all(r.confidence == "heuristic" for r in dyn)
    # the un-shadowed call on the binding line itself is still a real ref
    assert [r for r in rows
            if r.file == "tool/main.ts" and r.to_name == "pick"]


def test_ts_call_through_parameter_is_dynamic():
    ef = extract.extract(
        "m.ts", "export function apply(fn, x) {\n  return fn(x);\n}\n")
    calls = {(r.to_name, r.kind) for r in ef.refs}
    assert ("fn", "call") not in calls
    assert ("<dynamic>", "call") in calls


def test_ts_one_liner_arrow_param_is_dynamic():
    ef = extract.extract("m.ts", "export const call = (fn) => fn(1);\n")
    calls = {r.to_name for r in ef.refs if r.kind == "call"}
    assert "fn" not in calls
    assert "<dynamic>" in calls


def test_ts_import_binding_is_not_shadowed():
    src = ("import { add } from './mathutil';\n"
           "export function run() {\n  return add(1, 2);\n}\n")
    ef = extract.extract("m.ts", src)
    assert ("add", "call") in {(r.to_name, r.kind) for r in ef.refs}


def test_ts_local_in_anonymous_callback_is_dynamic():
    src = ("describe('x', () => {\n"
           "  const extract = pick();\n"
           "  extract(1);\n"
           "});\n")
    ef = extract.extract("m.test.ts", src)
    calls = {(r.to_name, r.line) for r in ef.refs if r.kind == "call"}
    assert ("extract", 3) not in calls
    assert ("<dynamic>", 3) in calls
    assert ("pick", 2) in calls


def test_go_local_shadowing_call_is_dynamic():
    src = ("package m\n\n"
           "func pick() func(int) int {\n"
           "\treturn nil\n"
           "}\n\n"
           "func run(x int) int {\n"
           "\textract := pick()\n"
           "\treturn extract(x)\n"
           "}\n")
    ef = extract.extract("m.go", src)
    calls = {(r.to_name, r.line) for r in ef.refs if r.kind == "call"}
    assert ("extract", 9) not in calls
    assert ("<dynamic>", 9) in calls
    assert ("pick", 8) in calls


def test_go_call_through_param_or_receiver_is_dynamic():
    src = ("package m\n\n"
           "func (s *Server) apply(fn func()) {\n"
           "\tfn()\n"
           "\ts.draw()\n"
           "}\n")
    ef = extract.extract("m.go", src)
    calls = {r.to_name for r in ef.refs if r.kind == "call"}
    assert calls == {"<dynamic>"}


def test_go_import_qualified_call_still_resolves(repo):
    cli.build(str(repo))
    conn = _connect(repo)
    rows = _rows(conn, "SELECT to_symbol, confidence FROM refs "
                        "WHERE from_file='go/app/app.go' "
                        "AND to_name='mathutil.Add'")
    assert rows == [("go/mathutil/mathutil.go::Add", "resolved")]


def test_package_import_links_named_modules():
    # known-issue repoindex-package-module-tests-not-linked: a test doing
    # `from pkg import mod` must link to pkg/__init__.py and pkg/mod.py,
    # not silently produce no row (pkg.py doesn't exist).
    from repoindex import resolve
    files = [
        extract.extract("tool/pkg/__init__.py", ""),
        extract.extract("tool/pkg/extract.py", "def extract():\n    return 1\n"),
        extract.extract("tool/pkg/other.py", "def o():\n    return 2\n"),
        extract.extract(
            "tool/tests/test_pkg.py",
            "from pkg import extract\n\n"
            "def test_x():\n    assert extract.extract() == 1\n"),
    ]
    links = {(l.test_file, l.target_file, l.source)
             for l in resolve.seed_tests(files)}
    assert ("tool/tests/test_pkg.py", "tool/pkg/extract.py", "import") in links
    assert ("tool/tests/test_pkg.py", "tool/pkg/__init__.py", "import") in links
    # only the named module is linked, not every module in the package
    assert not any(t == "tool/pkg/other.py" for _, t, _ in links)


def test_python_whole_module_import_resolves():
    from repoindex import resolve
    lib = extract.extract("lib.py", "def add(a, b):\n    return a + b\n")
    use = extract.extract(
        "use.py", "import lib\n\ndef run():\n    return lib.add(1, 2)\n")
    rows = [r for r in resolve.resolve_refs([lib, use])
            if r.to_name == "lib.add"]
    assert rows
    assert rows[0].to_symbol == "lib.py::add"
    assert rows[0].confidence == "resolved"


# ------------------------------------------------------------- housekeeping

def test_gitignore_gets_entry(repo):
    cli.build(str(repo))
    gi = (repo / ".gitignore").read_text()
    assert ".repoindex/" in gi


def test_gitignore_not_duplicated_on_rebuild(repo):
    cli.build(str(repo))
    cli.build(str(repo))
    gi = (repo / ".gitignore").read_text()
    assert gi.count(".repoindex/") == 1


# --------------------------------------------------------------- determinism

def test_build_is_deterministic(repo):
    cli.build(str(repo))
    conn1 = _connect(repo)
    snap1 = sorted(_rows(conn1, "SELECT qualname, kind, file, line_start "
                                 "FROM symbols"))
    conn1.close()

    cli.build(str(repo))
    conn2 = _connect(repo)
    snap2 = sorted(_rows(conn2, "SELECT qualname, kind, file, line_start "
                                 "FROM symbols"))
    conn2.close()

    assert snap1 == snap2


# ------------------------------------------------ stderr encoding (INVARIANTS)

def test_pin_utf8_covers_stderr():
    """Error text carries the same non-ASCII punctuation as normal output
    and is read by the same agent; a cp1252 console would emit invalid
    UTF-8 bytes. stdout was pinned long before stderr was."""
    import io as _io
    import sys as _sys
    saved = _sys.stdout, _sys.stderr
    try:
        _sys.stdout = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252")
        _sys.stderr = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252")
        cli._pin_utf8()
        assert _sys.stdout.encoding.lower().replace("-", "") == "utf8"
        assert _sys.stderr.encoding.lower().replace("-", "") == "utf8"
    finally:
        _sys.stdout, _sys.stderr = saved
