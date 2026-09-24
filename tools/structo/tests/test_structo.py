import json
import os
import shutil

import pytest

import structo

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name):
    return os.path.join(FIX, name)


def run(argv, capsys):
    code = structo.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def ok(argv, capsys):
    code, out, err = run(argv, capsys)
    assert code == 0, err
    return out


def norm(out):
    return [" ".join(l.split()) for l in out.splitlines()]


def has_yaml():
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


# --------------------------------------------------------------- detection

def test_detection_by_extension(capsys):
    for name, fmt in (("sample.json", "json"), ("sample.jsonl", "jsonl"),
                      ("sample.csv", "csv"), ("sample.tsv", "tsv"),
                      ("sample.xml", "xml"), ("sample.log", "log"),
                      ("sample.toml", "toml")):
        out = ok([fx(name)], capsys)
        assert "format: %s (extension)" % fmt in out


def test_detection_by_sniffing(tmp_path, capsys):
    cases = [("sample.json", "json"), ("sample.jsonl", "jsonl"),
             ("sample.csv", "csv"), ("sample.tsv", "tsv"),
             ("sample.xml", "xml"), ("sample.log", "log"),
             ("sample.yaml", "yaml")]
    for name, fmt in cases:
        bare = tmp_path / ("noext_" + fmt)
        shutil.copyfile(fx(name), bare)
        if fmt == "yaml" and not has_yaml():
            continue
        out = ok([str(bare)], capsys)
        assert "format: %s (sniffed)" % fmt in out, (name, out)


def test_binary_input_errors(tmp_path, capsys):
    blob = tmp_path / "blob"
    blob.write_bytes(b"\x00\x01\x02data")
    code, out, err = run([str(blob)], capsys)
    assert code == 2
    assert "binary" in err


# ------------------------------------------------------------- json schema

def test_json_schema_types_and_optionality(capsys):
    out = ok([fx("sample.json")], capsys)
    lines = norm(out)
    assert "root: object" in lines
    assert any(l.startswith("name: str 100% e.g.") for l in lines)
    assert any(l.startswith("version: int 100%") for l in lines)
    assert any(l.startswith("extra: null 100%") for l in lines)
    # note is present on 5 of the first 10 sampled items
    assert any(l.startswith("note: str 50%") for l in lines)


def test_json_array_lengths_and_sampling(capsys):
    out = ok([fx("sample.json")], capsys)
    lines = norm(out)
    tags = next(l for l in lines if l.startswith("tags:"))
    assert "len 3" in tags and "sampled" not in tags   # small array: exact
    items = next(l for l in lines if l.startswith("items: array"))
    assert "len 25" in items                           # length always exact
    assert "(first 10 sampled ~)" in items             # elements estimated


def test_json_sample_flag_changes_sampling(capsys):
    out = ok([fx("sample.json"), "--sample", "25"], capsys)
    items = next(l for l in norm(out) if l.startswith("items:"))
    assert "sampled" not in items
    # with all 25 items aggregated, note presence is 13/25 = 52%
    assert any(l.startswith("note: str 52%") for l in norm(out))


def test_jsonl_records_and_optionality(capsys):
    out = ok([fx("sample.jsonl")], capsys)
    assert "records 5" in out
    lines = norm(out)
    assert "root: object ×5" in lines
    assert any(l.startswith("email: str 60%") for l in lines)
    assert any(l.startswith("age: int 100%") for l in lines)


@pytest.mark.skipif(not has_yaml(), reason="PyYAML not installed")
def test_yaml_schema(capsys):
    out = ok([fx("sample.yaml")], capsys)
    lines = norm(out)
    assert "format: yaml (extension)" in norm(out)[0]
    assert any(l.startswith("server: object 100%") for l in lines)
    assert any(l.startswith("port: int 100%") for l in lines)
    features = next(l for l in lines if l.startswith("features:"))
    assert "len 2" in features
    assert any(l.startswith("flag: int 50%") for l in lines)


# ------------------------------------------------------------------- toml

def test_toml_schema(capsys):
    out = ok([fx("sample.toml")], capsys)
    lines = norm(out)
    assert "format: toml (extension)" in lines[0]
    assert any(l.startswith("project: object 100%") for l in lines)
    assert any(l.startswith("scripts: object 100%") for l in lines)
    assert any(l.startswith("keywords: array 100%") and "len 2" in l
               for l in lines)
    assert any(l.startswith("retries: int 50%") for l in lines)
    # a TOML date is its own type, not a string, and shows its value
    assert any(l.startswith("released: datetime 100%") and "2026-08-21" in l
               for l in lines)


def test_toml_table_header_is_not_sniffed_as_json(tmp_path, capsys):
    """The reported bug: `[project]` sniffed as JSON and came back as soup."""
    bare = tmp_path / "noext"
    shutil.copyfile(fx("sample.toml"), bare)
    out = ok([str(bare)], capsys)
    assert "format: toml (sniffed)" in out
    assert any(l.startswith("project: object") for l in norm(out))


def test_toml_path_and_raw(capsys):
    out = ok([fx("sample.toml"), "--path", "project.scripts"], capsys)
    lines = norm(out)
    assert any(l.startswith("demo: str 100%") for l in lines)
    assert not any(l.startswith("version:") for l in lines)
    assert ok([fx("sample.toml"), "--raw", "--path", "project.scripts.demo"],
              capsys) == "demo.cli:main\n"
    assert ok([fx("sample.toml"), "--raw", "--path", "meta.released"],
              capsys) == "2026-08-21\n"
    assert ok([fx("sample.toml"), "--raw", "--path", "project.keywords"],
              capsys).startswith("[")


def test_toml_select_array_of_tables(capsys):
    out = ok([fx("sample.toml"), "--select", "name,enabled",
              "--path", "tool.runner.jobs"], capsys)
    assert rows(out) == [["name", "enabled"], ["alpha", "true"],
                         ["beta", "false"]]


def test_toml_select_needs_an_array(capsys):
    code, _, err = run([fx("sample.toml"), "--select", "name"], capsys)
    assert code == 2
    assert "not an array of tables" in err


def test_toml_path_not_found(capsys):
    code, _, err = run([fx("sample.toml"), "--path", "project.nope"], capsys)
    assert code == 2
    assert "--path not found" in err


def test_invalid_toml_errors_rather_than_guessing(tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_text("[project\nname = 1\n", encoding="utf-8")
    code, out, err = run([str(bad)], capsys)
    assert code == 2
    assert "not valid toml" in err
    assert out == ""


def test_ini_sniff_falls_back_to_log(tmp_path, capsys):
    """A sniff is a guess: ini-ish files summarize as a log, not an error."""
    ini = tmp_path / "thing.ini"
    ini.write_text("[section]\nkey = value\n", encoding="utf-8")
    out = ok([str(ini)], capsys)
    assert "format: log (sniffed)" in out


def test_dotenv_is_not_claimed_as_toml(tmp_path, capsys):
    env = tmp_path / "dotenv"
    env.write_text("FOO=bar\nBAZ=qux\n", encoding="utf-8")
    out = ok([str(env)], capsys)
    assert "format: log (sniffed)" in out


# ------------------------------------------------------------------- zoom

def test_path_zoom_object(capsys):
    out = ok([fx("sample.json"), "--path", "owner"], capsys)
    lines = norm(out)
    assert any(l.startswith("name: str 100%") for l in lines)
    assert not any(l.startswith("items:") for l in lines)


def test_path_zoom_array_index(capsys):
    out = ok([fx("sample.json"), "--path", "tags[0]"], capsys)
    assert 'e.g. "red"' in out
    assert "green" not in out


def test_path_zoom_jsonl_per_record(capsys):
    out = ok([fx("sample.jsonl"), "--path", "user"], capsys)
    lines = norm(out)
    assert any(l.startswith("root: str ×5") for l in lines)


def test_path_not_found_errors(capsys):
    code, out, err = run([fx("sample.json"), "--path", "nope.missing"],
                         capsys)
    assert code == 2
    assert "--path not found" in err


def test_path_on_csv_errors(capsys):
    code, out, err = run([fx("sample.csv"), "--path", "a"], capsys)
    assert code == 2
    assert "--path zooms into" in err


def test_path_jsonl_record_index(capsys):
    out = ok([fx("sample.jsonl"), "--path", "[1]"], capsys)
    assert "record 1" in out
    lines = norm(out)
    assert any(l.startswith("user: str 100%") for l in lines)
    assert not any(l.startswith("email:") for l in lines)


def test_path_jsonl_record_index_with_subpath(capsys):
    out = ok([fx("sample.jsonl"), "--path", "[0].user"], capsys)
    assert '"alice"' in out
    assert "age" not in out


def test_path_jsonl_negative_record_index(capsys):
    """`[-1]` is the last record — the normal ask for an append-only log,
    where the count isn't known without reading the file first."""
    out = ok([fx("sample.jsonl"), "--path", "[-1]"], capsys)
    assert '"eve"' in out


def test_negative_record_header_resolves_the_index(capsys):
    """The header names the absolute record, so learning "which one was
    that / how many are there" doesn't cost a second call."""
    out = ok([fx("sample.jsonl"), "--path", "[-2]"], capsys)
    assert "record -2 (3)" in out


def test_raw_jsonl_negative_index_with_subpath(capsys):
    out = ok([fx("sample.jsonl"), "--raw", "--path", "[-1].user"], capsys)
    assert out == "eve\n"


def test_negative_record_out_of_range(capsys):
    code, out, err = run([fx("sample.jsonl"), "--path", "[-9]"], capsys)
    assert code == 2
    assert "record [-9] not found" in err
    assert "5 records" in err


def test_negative_index_refused_inside_a_document(capsys):
    """Streaming can't seek backwards through an array whose length isn't
    known until it closes, so this refuses loudly instead of reporting the
    path as simply absent."""
    code, out, err = run([fx("sample.json"), "--path", "tags[-1]"], capsys)
    assert code == 2
    assert "negative index [-1]" in err
    assert "JSONL record" in err


def test_negative_index_refused_in_select(capsys):
    code, out, err = run([fx("sample.jsonl"), "--select", "tags[-1]"], capsys)
    assert code == 2
    assert "negative index [-1]" in err


def test_negative_record_lookup_stays_streaming():
    """Memory is O(|index|), not O(file): the ring buffer holds |N| records,
    so the streaming invariant survives the feature."""
    import collections as _c
    seen_maxlen = []
    real = _c.deque

    class Probe(_c.deque):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            seen_maxlen.append(kw.get("maxlen"))

    structo.collections.deque = Probe
    try:
        record, idx = structo._nth_record(fx("sample.jsonl"), -2)
    finally:
        structo.collections.deque = real
    assert record["user"] == "dan" and idx == 3
    assert seen_maxlen == [2]  # not 5, the record count


def test_path_jsonl_record_out_of_range(capsys):
    code, out, err = run([fx("sample.jsonl"), "--path", "[9]"], capsys)
    assert code == 2
    assert "record [9] not found" in err
    assert "5 records" in err


# -------------------------------------------------------------------- raw

def test_raw_jsonl_string_field(capsys):
    out = ok([fx("sample.jsonl"), "--raw", "--path", "[0].email"], capsys)
    assert out == "a@x.io\n"


def test_raw_jsonl_whole_record(capsys):
    out = ok([fx("sample.jsonl"), "--raw", "--path", "[1]"], capsys)
    assert json.loads(out) == {"user": "bob", "age": 44}


def test_raw_jsonl_needs_record_index(capsys):
    code, out, err = run([fx("sample.jsonl"), "--raw", "--path", "user"],
                         capsys)
    assert code == 2
    assert "record index" in err


def test_raw_json_scalars(capsys):
    out = ok([fx("sample.json"), "--raw", "--path", "owner.email"], capsys)
    assert out == "a@example.com\n"
    out = ok([fx("sample.json"), "--raw", "--path", "items[2].id"], capsys)
    assert out == "3\n"


def test_raw_json_object_prints_json(capsys):
    out = ok([fx("sample.json"), "--raw", "--path", "owner"], capsys)
    assert json.loads(out) == {"name": "Alice", "email": "a@example.com"}


def test_raw_json_full_fidelity(tmp_path, capsys):
    text = "x" * 100 + "\nline2\ttab é 😀 \"quoted\" back\\slash"
    doc = tmp_path / "doc.json"
    doc.write_text(json.dumps({"a": [{"b": text}, {"b": "other"}]}),
                   encoding="utf-8")
    out = ok([str(doc), "--raw", "--path", "a[0].b"], capsys)
    assert out == text + "\n"


def test_raw_requires_path(capsys):
    code, out, err = run([fx("sample.json"), "--raw"], capsys)
    assert code == 2
    assert "--raw needs --path" in err


def test_raw_not_found(capsys):
    code, out, err = run([fx("sample.json"), "--raw", "--path",
                          "owner.phone"], capsys)
    assert code == 2
    assert "--path not found" in err


def test_raw_refuses_max_tokens_overflow(capsys):
    code, out, err = run([fx("sample.json"), "--raw", "--path", "items",
                          "--max-tokens", "5"], capsys)
    assert code == 2
    assert "never truncates" in err


@pytest.mark.skipif(not has_yaml(), reason="PyYAML not installed")
def test_raw_yaml_values(capsys):
    out = ok([fx("sample.yaml"), "--raw", "--path", "server.host"], capsys)
    assert out == "localhost\n"
    out = ok([fx("sample.yaml"), "--raw", "--path", "features[1].flag"],
             capsys)
    assert out == "3\n"


# -------------------------------------------------------------------- csv

def test_csv_columns(capsys):
    out = ok([fx("sample.csv")], capsys)
    lines = norm(out)
    assert "columns (4), rows 5:" in lines
    assert "id int null 0% min 1 max 5 distinct 5" in lines
    assert "score float null 20% min 1 max 4.25 distinct 4" in lines
    assert "active bool null 20% distinct 2" in lines
    name = next(l for l in lines if l.startswith("name str"))
    assert 'min "Alice" max "Eve"' in name


def test_csv_exactly_three_sample_rows(capsys):
    out = ok([fx("sample.csv")], capsys)
    idx = out.index("sample rows (3):")
    rows = [l.strip() for l in out[idx:].splitlines()[1:4]]
    assert rows == ["1,Alice,3.5,true", "2,Bob,,false", "3,Cara,4.25,true"]
    assert "4,Dan" not in out


def test_tsv_delimiter(capsys):
    out = ok([fx("sample.tsv")], capsys)
    lines = norm(out)
    assert "columns (3), rows 3:" in lines
    assert any(l.startswith("pop int null 0% min 8.1e+06") for l in lines)


# -------------------------------------------------------------------- log

def test_log_summary(capsys):
    out = ok([fx("sample.log")], capsys)
    assert "lines 10, timestamp iso-8601" in out
    lines = norm(out)
    assert "5× INFO GET /api/users/<n> took <n> ms" in lines
    assert "2× WARN cache miss for <hex>" in lines
    assert "first %s:1" % fx("sample.log") in out
    assert "last  %s:10" % fx("sample.log") in out
    assert "server started" in out and "shutdown complete" in out


# -------------------------------------------------------------------- xml

def test_xml_tree(capsys):
    out = ok([fx("sample.xml")], capsys)
    lines = norm(out)
    assert "catalog ×1" in lines
    assert "book ×2 @id ×2 @lang ×1" in lines
    assert "title ×2 text ×2" in lines
    assert "note ×1 text ×1" in lines


# ----------------------------------------------------------- token budget

def test_budget_drops_examples_first(capsys):
    full = ok([fx("sample.json")], capsys)
    budget = structo._est(full.splitlines()) - 3
    out = ok([fx("sample.json"), "--max-tokens", str(budget)], capsys)
    assert structo._est(out.splitlines()) <= budget
    assert "e.g." not in out                    # examples dropped first
    assert any(l.startswith("items:") for l in norm(out))


def test_budget_collapses_nesting_but_keeps_top_level(capsys):
    out = ok([fx("sample.json"), "--max-tokens", "70"], capsys)
    assert structo._est(out.splitlines()) <= 70
    lines = norm(out)
    for key in ("name:", "items:", "owner:"):   # top level survives
        assert any(l.startswith(key) for l in lines), key
    assert not any(l.startswith("id:") for l in lines)  # deep keys gone


def test_budget_csv_drops_samples_then_detail(capsys):
    full = ok([fx("sample.csv")], capsys)
    budget = structo._est(full.splitlines()) - 3
    out = ok([fx("sample.csv"), "--max-tokens", str(budget)], capsys)
    assert structo._est(out.splitlines()) <= budget
    assert "sample rows" not in out
    assert "columns (4), rows 5:" in out
    tiny = ok([fx("sample.csv"), "--max-tokens", "45"], capsys)
    assert structo._est(tiny.splitlines()) <= 45
    assert "columns (4)" in tiny                # top level never dropped


# ---------------------------------------------------------------- --select

def rows(out):
    return [l.split("\t") for l in out.splitlines()]


def test_select_jsonl_one_row_per_record(capsys):
    out = ok([fx("sample.jsonl"), "--select", "user,age,email"], capsys)
    got = rows(out)
    assert got[0] == ["user", "age", "email"]
    assert len(got) == 6                        # header + 5 records
    assert got[1] == ["alice", "31", "a@x.io"]
    assert [r[2] for r in got[1:]].count("") == 2    # 60% present


def test_select_json_array_at_path(capsys):
    out = ok([fx("sample.json"), "--select", "id,value", "--path", "items"],
             capsys)
    got = rows(out)
    assert got[0] == ["id", "value"]
    assert len(got) == 26                       # all 25, never sampled
    assert got[1] == ["1", "1.5"]


def test_select_json_top_level_array(tmp_path, capsys):
    arr = tmp_path / "arr.json"
    arr.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    assert rows(ok([str(arr), "--select", "a"], capsys)) == \
        [["a"], ["1"], ["2"]]


def test_select_csv_projects_and_reorders(capsys):
    out = ok([fx("sample.csv"), "--select", "name,id"], capsys)
    got = rows(out)
    assert got[0] == ["name", "id"]
    assert got[1] == ["Alice", "1"]
    assert len(got) == 6                        # header + 5 rows


@pytest.mark.skipif(not has_yaml(), reason="PyYAML not installed")
def test_select_yaml_sequence(capsys):
    out = ok([fx("sample.yaml"), "--select", "name,enabled",
              "--path", "features"], capsys)
    assert rows(out) == [["name", "enabled"], ["alpha", "true"],
                         ["beta", "false"]]


def test_select_dotted_indexed_and_container_fields(tmp_path, capsys):
    src = tmp_path / "r.jsonl"
    src.write_text(
        json.dumps({"id": 1, "m": {"h": "n1"}, "tags": ["a", "b"]}) + "\n"
        + json.dumps({"id": 2, "tags": []}) + "\n", encoding="utf-8")
    got = rows(ok([str(src), "--select", "id,m.h,tags,tags[0],nope"],
                  capsys))
    assert got[1] == ["1", "n1", '["a","b"]', "a", ""]
    assert got[2] == ["2", "", "[]", "", ""]    # missing renders empty


def test_select_cells_never_break_the_row(tmp_path, capsys):
    src = tmp_path / "r.jsonl"
    src.write_text(json.dumps({"s": "one\ttwo\nthree", "n": None}) + "\n",
                   encoding="utf-8")
    out = ok([str(src), "--select", "s,n"], capsys)
    assert len(out.splitlines()) == 2
    assert rows(out)[1] == ["one two three", "null"]


def test_select_skips_unparsable_lines_like_the_summary(tmp_path, capsys):
    src = tmp_path / "r.jsonl"
    src.write_text('{"a": 1}\nnot json\n\n{"a": 2}\n', encoding="utf-8")
    assert rows(ok([str(src), "--select", "a"], capsys)) == \
        [["a"], ["1"], ["2"]]


def test_select_refuses_budget_rather_than_dropping_records(capsys):
    code, out, err = run([fx("sample.jsonl"), "--select", "user,age",
                          "--max-tokens", "2"], capsys)
    assert code == 2
    assert "never drops records" in err
    assert "5 rows" in err
    assert out == ""                            # nothing printed at all


def test_select_within_budget_prints_every_row(capsys):
    out = ok([fx("sample.jsonl"), "--select", "user", "--max-tokens", "500"],
             capsys)
    assert len(rows(out)) == 6


def test_select_errors(capsys):
    cases = [
        ([fx("sample.jsonl"), "--select", "user", "--raw"], "pick one"),
        ([fx("sample.jsonl"), "--select", "user", "--path", "[0]"],
         "every jsonl line as a record"),
        ([fx("sample.json"), "--select", "a", "--path", "owner"],
         "is not an array"),
        ([fx("sample.json"), "--select", "a", "--path", "nope"],
         "--path not found"),
        ([fx("sample.log"), "--select", "a"], "record-shaped data"),
        ([fx("sample.jsonl"), "--select", "user,,age"], "empty field"),
    ]
    for argv, want in cases:
        code, out, err = run(argv, capsys)
        assert code == 2, argv
        assert want in err, (argv, err)
        assert out == "", argv          # no header emitted before an error


def test_select_is_deterministic(capsys):
    argv = [fx("sample.jsonl"), "--select", "user,age,email"]
    assert ok(argv, capsys) == ok(argv, capsys)


# ------------------------------------------------------------ determinism

def test_output_is_deterministic(capsys):
    for name in ("sample.json", "sample.jsonl", "sample.csv",
                 "sample.log", "sample.xml"):
        assert ok([fx(name)], capsys) == ok([fx(name)], capsys)


def test_missing_file_errors(capsys):
    code, out, err = run([fx("no_such_file.json")], capsys)
    assert code == 2
    assert "not a file" in err


# -------------------------------------------------------------- streaming

@pytest.mark.slow
def test_memory_bounded_on_large_jsonl(tmp_path, capsys):
    import tracemalloc
    big = tmp_path / "big.jsonl"
    row = {"user": "u%06d", "age": 30, "tags": ["a", "b", "c"],
           "note": "x" * 120}
    with open(big, "w", encoding="utf-8", newline="\n") as fh:
        for i in range(120_000):                # ~25 MB
            row["user"] = "u%06d" % i
            fh.write(json.dumps(row) + "\n")
    size_mb = os.path.getsize(big) / 1e6
    assert size_mb > 20
    tracemalloc.start()
    out = ok([str(big)], capsys)
    peak_mb = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()
    assert "records 120000" in out
    assert peak_mb < 15, "peak %.1f MB not O(schema+samples)" % peak_mb


@pytest.mark.slow
def test_select_memory_bounded_on_large_json_array(tmp_path, capsys):
    import tracemalloc
    big = tmp_path / "big.json"
    with open(big, "w", encoding="utf-8", newline="\n") as fh:
        fh.write('{"rows": [')
        for i in range(120_000):                # ~25 MB
            fh.write("," if i else "")
            fh.write(json.dumps({"id": i, "note": "x" * 160}))
        fh.write("]}")
    assert os.path.getsize(big) / 1e6 > 20
    tracemalloc.start()
    out = ok([str(big), "--select", "id", "--path", "rows"], capsys)
    peak_mb = tracemalloc.get_traced_memory()[1] / 1e6
    tracemalloc.stop()
    assert len(out.splitlines()) == 120_001
    assert peak_mb < 25, "peak %.1f MB not O(one record)" % peak_mb


# ------------------------------------------- default token cap (ADR-006)

def test_default_max_tokens_is_on():
    assert structo.DEFAULT_MAX_TOKENS > 0


def test_select_is_exempt_from_the_default_budget(tmp_path, capsys):
    """--select feeds awk/sort and refuses rather than truncates, so a
    default cap there would turn an ordinary pipe into an error."""
    src = tmp_path / "rows.jsonl"
    src.write_text("\n".join(
        '{"a": %d, "b": "value-%d"}' % (i, i) for i in range(4000)),
        encoding="utf-8")
    out = ok([str(src), "--select", "a,b"], capsys)
    # header row + one row per record, nothing dropped
    assert len(out.strip().splitlines()) == 4001


def test_raw_is_exempt_from_the_default_budget(tmp_path, capsys):
    src = tmp_path / "one.json"
    src.write_text('{"blob": "%s"}' % ("x" * 40000), encoding="utf-8")
    out = ok([str(src), "--path", "blob", "--raw"], capsys)
    assert len(out.strip()) == 40000


def test_explicit_max_tokens_still_refuses_on_select(tmp_path, capsys):
    """The exemption is only about the *default* - an explicit cap must
    still behave exactly as it did before."""
    src = tmp_path / "rows.jsonl"
    src.write_text("\n".join(
        '{"a": %d, "b": "value-%d"}' % (i, i) for i in range(4000)),
        encoding="utf-8")
    code, _, err = run([str(src), "--select", "a,b", "--max-tokens", "50"],
                       capsys)
    assert code != 0
    assert "budget" in err


def test_schema_output_is_capped_by_default(tmp_path, capsys):
    wide = {"f%d" % i: i for i in range(4000)}
    src = tmp_path / "wide.json"
    src.write_text(json.dumps(wide), encoding="utf-8")
    out = ok([str(src)], capsys)
    est = len(out.rstrip("\n").encode("utf-8")) // 4 + 1
    assert est <= structo.DEFAULT_MAX_TOKENS


# ------------------------------------------------ byte-order marks (v0.6.1)
# Excel's "CSV UTF-8" and PowerShell 5's Out-File write a UTF-8 BOM. Read as
# plain utf-8 it stayed glued to the first field, and both failures were
# silent: wrong data, exit 0.

BOM = b"\xef\xbb\xbf"


def test_bom_csv_select_finds_the_first_column(tmp_path, capsys):
    p = tmp_path / "people.csv"
    p.write_bytes(BOM + b"id,name\n1,a\n2,b\n")
    out = ok([str(p), "--select", "id,name"], capsys)
    assert out.splitlines() == ["id\tname", "1\ta", "2\tb"]
    summary = ok([str(p)], capsys)
    assert "﻿" not in summary


def test_bom_jsonl_record_zero_is_the_first_record(tmp_path, capsys):
    p = tmp_path / "events.jsonl"
    p.write_bytes(BOM + b'{"id": 1}\n{"id": 2}\n')
    assert ok([str(p), "--raw", "--path", "[0].id"], capsys).strip() == "1"
    summary = ok([str(p)], capsys)
    assert "records 2" in summary and "unparsable" not in summary
    assert ok([str(p), "--select", "id"], capsys).splitlines() == [
        "id", "1", "2"]


def test_bom_toml_parses(tmp_path, capsys):
    p = tmp_path / "cfg.toml"
    p.write_bytes(BOM + b'[tool]\nname = "x"\n')
    out = ok([str(p), "--raw", "--path", "tool.name"], capsys)
    assert out.strip() == "x"


def test_bom_does_not_defeat_sniffing(tmp_path, capsys):
    p = tmp_path / "noext"
    p.write_bytes(BOM + b'{"a": {"b": 1}}')
    assert "format: json (sniffed)" in ok([str(p)], capsys)


def test_non_utf8_toml_is_an_error_not_a_traceback(tmp_path, capsys):
    """tomllib decodes strict utf-8 itself; its UnicodeDecodeError escaped
    both the explicit .toml path and the sniff that was only guessing."""
    explicit = tmp_path / "latin1.toml"
    explicit.write_bytes(b'name = "caf\xe9"\n')
    code, out, err = run([str(explicit)], capsys)
    assert code == 2 and out == ""
    assert "not valid toml" in err and "utf-8" in err
    sniffed = tmp_path / "settings.conf"
    sniffed.write_bytes(b'name = "caf\xe9"\nport = 80\n')
    assert "format: log (sniffed)" in ok([str(sniffed)], capsys)
