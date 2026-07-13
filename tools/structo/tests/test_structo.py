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
                      ("sample.xml", "xml"), ("sample.log", "log")):
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
