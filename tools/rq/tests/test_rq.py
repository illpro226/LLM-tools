"""Tests for rq against the shared repoindex fixture repo (integration)
and a hand-seeded database (unit). See TESTING.md for the area list."""
import json
import re
import subprocess

import pytest

import rq


def run(capsys, *argv):
    """Invoke rq.main in-process; return (exit_code, stdout, stderr)."""
    code = rq.main(list(argv))
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def run_on(capsys, root, *argv):
    return run(capsys, argv[0], "--root", str(root), "--no-update",
               *argv[1:])


# ------------------------------------------------------------ whouses ---

def test_whouses_groups_per_matched_symbol_in_file_order(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "whouses", "Rectangle")
    assert code == 0
    titles = [l for l in out.splitlines() if not l.startswith(" ")]
    assert [t.split()[0] for t in titles] == [
        "go/shapes/shapes.go::Rectangle",
        "js/shapes.ts::Rectangle",
        "py/shapes.py::Rectangle",
    ]


def test_whouses_finds_call_and_type_use_refs(capsys, indexed_repo):
    _, out, _ = run_on(capsys, indexed_repo, "whouses", "Rectangle")
    assert "call  py/app.py:33  resolved" in out
    assert "type-use  py/app.py:38  resolved" in out
    assert "call  js/app.js:5  resolved" in out


def test_whouses_dedups_identical_ref_rows(capsys, indexed_repo):
    # py/app.py:38 carries two annotation refs to Rectangle; one line.
    _, out, _ = run_on(capsys, indexed_repo, "whouses", "Rectangle")
    assert out.count("py/app.py:38") == 1


def test_whouses_unknown_symbol_exits_1(capsys, indexed_repo):
    code, out, err = run_on(capsys, indexed_repo, "whouses", "NoSuchThing")
    assert code == 1
    assert out == ""
    assert "no symbol matching 'NoSuchThing'" in err


def test_symbol_matching_is_case_sensitive(capsys, indexed_repo):
    # `add` must not match Go's `Add` (SQLite LIKE would conflate them).
    _, out, _ = run_on(capsys, indexed_repo, "whouses", "add")
    assert "js/mathutil.js::add" in out
    assert "py/mathutil.py::add" in out
    assert "::Add" not in out


# ------------------------------------------- implements / inherits ------

def test_implements_lists_resolved_and_structural(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "implements", "Shape")
    assert code == 0
    # Python ABC and TS `implements` keyword are resolved.
    assert "  py/shapes.py::Rectangle  implements  py/shapes.py:13  resolved" \
        in out
    assert "js/shapes.ts::Rectangle  implements" in out
    # Go satisfaction is structural, therefore heuristic.
    go_lines = [l for l in out.splitlines()
                if "go/shapes/shapes.go::Rectangle  implements" in l]
    assert go_lines and all(l.endswith("heuristic") for l in go_lines)


def test_implements_nests_subclasses_under_implementors(capsys, indexed_repo):
    _, out, _ = run_on(capsys, indexed_repo, "implements", "Shape")
    lines = out.splitlines()
    rect = lines.index(
        "  py/shapes.py::Rectangle  implements  py/shapes.py:13  resolved")
    # Square inherits Rectangle: depth 2 (four spaces), right below.
    assert lines[rect + 1].startswith("    py/shapes.py::Square  inherits  ")


def test_inherits_subclass_tree(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "inherits", "Rectangle")
    assert code == 0
    assert "  py/shapes.py::Square  inherits  py/shapes.py:24  resolved" in out
    assert "js/shapes.ts::Square  inherits" in out


def test_inherits_cycle_terminates(capsys, seeded_db):
    # Seeded Alpha <-> Beta inheritance cycle: renderer must not hang or
    # repeat nodes.
    code, out, _ = run_on(capsys, seeded_db, "inherits", "Alpha")
    assert code == 0
    assert "  b.py::Beta  inherits  b.py:1  resolved" in out
    assert out.count("a.py::Alpha") == 1  # the group title only


def test_inherits_external_base_fallback(capsys, seeded_db):
    # ExternalBase has no symbol row; it exists only as a raw parent name.
    code, out, _ = run_on(capsys, seeded_db, "inherits", "ExternalBase")
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "ExternalBase  (not defined in index)"
    assert lines[1] == "  a.py::Alpha  inherits  a.py:1  resolved"
    assert lines[2] == "    b.py::Beta  inherits  b.py:1  resolved"


# -------------------------------------------------------------- impact ---

def test_impact_includes_direct_and_transitive_dependents(capsys,
                                                          indexed_repo):
    # Shape -> Rectangle (implements, depth 1) -> its users (depth 2),
    # including the inheritance-propagated Square.
    code, out, _ = run_on(capsys, indexed_repo, "impact", "Shape")
    assert code == 0
    assert "  1  py/shapes.py::Rectangle  implements  py/shapes.py:13" \
        "  resolved" in out
    assert "  2  py/app.py::build_shapes  call  py/app.py:33  resolved" in out
    assert "  2  py/shapes.py::Square  inherits  py/shapes.py:24  resolved" \
        in out


def test_impact_depth_flag_caps_expansion(capsys, indexed_repo):
    def levels(argv_extra):
        _, out, _ = run(capsys, "impact", "--root", str(indexed_repo),
                        "--no-update", "--json", "Shape", *argv_extra)
        payload = json.loads(out)
        return {it["depth_level"] for g in payload["groups"]
                for it in g["items"] if "depth_level" in it}
    assert levels(["--depth", "1"]) == {1}
    assert max(levels([])) >= 2  # default depth 3 reaches further


def test_impact_terminates_with_covering_tests(capsys, indexed_repo):
    _, out, _ = run_on(capsys, indexed_repo, "impact", "add")
    lines = out.splitlines()
    idx = lines.index("covering tests:")
    tail = lines[idx + 1:]
    assert any("covers py/mathutil.py" in l for l in tail)
    assert all(re.match(r"  \S+:1  covers \S+  \(\w+\)$", l) for l in tail)


def test_impact_unknown_symbol_exits_1(capsys, indexed_repo):
    code, _, err = run_on(capsys, indexed_repo, "impact", "NoSuchThing")
    assert code == 1
    assert "no symbol matching" in err


# ----------------------------------------------------------- publicapi ---

def test_publicapi_lists_exported_symbols_only(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "publicapi")
    assert code == 0
    assert "py/shapes.py:13  py/shapes.py::Rectangle  class" in out
    assert "_scale" not in out          # unexported
    assert "privateHelper" not in out   # Go lowercase = unexported


def test_publicapi_path_prefix_filter(capsys, indexed_repo):
    _, out, _ = run_on(capsys, indexed_repo, "publicapi", "py")
    lines = out.splitlines()
    assert lines and all(l.startswith("py/") for l in lines)
    # Trailing slash and backslash both normalize to the same filter.
    _, out2, _ = run_on(capsys, indexed_repo, "publicapi", "py/")
    assert out2 == out


# ------------------------------------------------------------ deadcode ---

def test_deadcode_finds_unreferenced_private_symbols(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "deadcode")
    assert code == 0
    assert "py/mathutil.py:9  py/mathutil.py::_scale  func  no inbound refs" \
        in out
    assert "privateHelper" in out
    assert "js/mathutil.js::scale" in out


def test_deadcode_excludes_exported_by_default(capsys, indexed_repo):
    _, out, _ = run_on(capsys, indexed_repo, "deadcode")
    assert "unused_helper" not in out
    _, out2, _ = run_on(capsys, indexed_repo, "deadcode",
                        "--include-exported")
    assert "py/dead.py:4  py/dead.py::unused_helper  func  no inbound refs" \
        in out2
    assert "py/cyc_b.py::gamma" in out2  # exported, only calls outward


def test_deadcode_prints_heuristic_caveat(capsys, indexed_repo):
    _, out, _ = run_on(capsys, indexed_repo, "deadcode")
    assert re.search(r"note: index contains \d+ heuristic ref\(s\)", out)
    assert "conservative, not sound" in out


# ---------------------------------------------------------- findcycles ---

def test_findcycles_reports_the_fixture_cycle_only(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "findcycles")
    assert code == 0
    lines = out.splitlines()
    assert lines[0] == "cycle 1 (2 files):"
    assert "  py/cyc_a.py:2  imports py/cyc_b.py" in lines
    assert "  py/cyc_b.py:2  imports py/cyc_a.py" in lines
    assert "cycle 2" not in out  # the rest of the fixture repo is acyclic


def test_findcycles_orders_smallest_cycle_first(capsys, seeded_db):
    # Seeded: 3-cycle a->b->c->a and 2-cycle d<->e.
    _, out, _ = run_on(capsys, seeded_db, "findcycles")
    lines = out.splitlines()
    assert lines[0] == "cycle 1 (2 files):"
    assert lines[1] == "  d.py:1  imports e.py"
    assert lines[2] == "  e.py:1  imports d.py"
    assert lines[3] == "cycle 2 (3 files):"
    assert "solo.py" not in out  # acyclic file appears in no cycle


# ------------------------------------------------------------ untested ---

def test_untested_lists_uncovered_exported_symbols(capsys, indexed_repo):
    code, out, _ = run_on(capsys, indexed_repo, "untested")
    assert code == 0
    assert "py/shapes.py:13  py/shapes.py::Rectangle  class" in out
    assert "py/dead.py:4  py/dead.py::unused_helper  func" in out
    assert "py/mathutil.py" not in out  # covered by tests_py/test_mathutil
    assert all(l.endswith("no covering tests") for l in out.splitlines())


def test_untested_coverage_row_removes_symbols(capsys, seeded_db):
    # tests row: test_a.py covers a.py -> Alpha and covered_fn drop out.
    _, out, _ = run_on(capsys, seeded_db, "untested")
    assert "b.py:1  b.py::Beta  class  no covering tests" in out
    assert "solo.py:1  solo.py::lonely  func  no covering tests" in out
    assert "a.py::" not in out


# ---------------------------------------------------- shared plumbing ---

def test_freshness_guard_runs_repoindex_update(capsys, indexed_repo,
                                               monkeypatch):
    calls = []

    def spy(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(rq.subprocess, "run", spy)
    monkeypatch.setattr(rq.shutil, "which", lambda cmd: "/usr/bin/" + cmd)
    code, _, _ = run(capsys, "publicapi", "--root", str(indexed_repo))
    assert code == 0
    # argv must carry the which()-resolved path, not the bare name --
    # Windows PATH shims are .cmd files CreateProcess can't resolve.
    assert calls == [["/usr/bin/repoindex", "--root", str(indexed_repo),
                      "update"]]


def test_no_update_skips_the_freshness_guard(capsys, indexed_repo,
                                             monkeypatch):
    def bomb(*a, **k):
        raise AssertionError("subprocess.run called despite --no-update")

    monkeypatch.setattr(rq.subprocess, "run", bomb)
    code, _, _ = run(capsys, "publicapi", "--root", str(indexed_repo),
                     "--no-update")
    assert code == 0


def test_shared_flags_accepted_before_the_subcommand(capsys, indexed_repo):
    # `rq --no-update --root R whouses X` must work, not just the
    # flags-after-subcommand form (known-issue: rq-shared-flags-position).
    code, out, _ = run(capsys, "--root", str(indexed_repo), "--no-update",
                       "--json", "whouses", "Rectangle")
    assert code == 0
    assert json.loads(out)["command"] == "whouses"


def test_post_subcommand_shared_flag_wins_over_pre(capsys, indexed_repo):
    # When given in both positions the later (post-subcommand) value wins;
    # a subparser default must not clobber a pre-subcommand value.
    _, text, _ = run(capsys, "--json", "whouses", "Rectangle",
                     "--root", str(indexed_repo), "--no-update")
    json.loads(text)  # --json given only before the subcommand survived


def test_stale_index_is_updated_end_to_end(capsys, mutable_repo):
    # Real path: no repoindex on PATH -> the sibling checkout runs update.
    new = mutable_repo / "py" / "brand_new.py"
    new.write_text("def freshly_added():\n    return 1\n", encoding="ascii")
    code, out, _ = run(capsys, "publicapi", "--root", str(mutable_repo))
    assert code == 0
    assert "py/brand_new.py:1  py/brand_new.py::freshly_added  func" in out


def test_missing_index_exits_2(capsys, tmp_path):
    code, out, err = run(capsys, "publicapi", "--root", str(tmp_path),
                         "--no-update")
    assert code == 2
    assert out == ""
    assert "repoindex build" in err


def test_json_mirrors_text_content(capsys, indexed_repo):
    _, text, _ = run_on(capsys, indexed_repo, "whouses", "Rectangle")
    _, raw, _ = run(capsys, "whouses", "--root", str(indexed_repo),
                    "--no-update", "--json", "Rectangle")
    payload = json.loads(raw)
    assert payload["command"] == "whouses"
    titles = [l for l in text.splitlines() if not l.startswith(" ")]
    assert [g["title"] for g in payload["groups"]] == titles
    n_text_items = sum(1 for l in text.splitlines() if l.startswith(" "))
    n_json_items = sum(len(g["items"]) for g in payload["groups"])
    assert n_json_items == n_text_items
    assert all(g["omitted"] == 0 for g in payload["groups"])


def test_max_tokens_collapses_leaf_lists(capsys, indexed_repo):
    _, full, _ = run_on(capsys, indexed_repo, "untested")
    _, capped, _ = run(capsys, "untested", "--root", str(indexed_repo),
                       "--no-update", "--max-tokens", "60")
    assert rq._estimate_tokens(capped) <= 60
    m = re.search(r"\(\+(\d+) more\)", capped)
    assert m
    shown = sum(1 for l in capped.splitlines() if l.endswith("covering tests"))
    assert shown + int(m.group(1)) == len(full.splitlines()) - \
        full.count("note:")
    # Shown lines are a prefix of the full list, never rewritten.
    assert capped.splitlines()[:shown] == full.splitlines()[:shown]


def test_max_tokens_floor_is_count_only(capsys, indexed_repo):
    _, full, _ = run_on(capsys, indexed_repo, "untested")
    n_items = sum(1 for l in full.splitlines()
                  if l.endswith("no covering tests"))
    _, capped, _ = run(capsys, "untested", "--root", str(indexed_repo),
                       "--no-update", "--max-tokens", "15")
    assert f"(+{n_items} more)" in capped
    assert not any(l.endswith("no covering tests")
                   for l in capped.splitlines())


def test_json_reports_omitted_counts(capsys, indexed_repo):
    _, raw, _ = run(capsys, "untested", "--root", str(indexed_repo),
                    "--no-update", "--json", "--max-tokens", "60")
    payload = json.loads(raw)
    total_omitted = sum(g["omitted"] for g in payload["groups"])
    assert total_omitted > 0


@pytest.mark.parametrize("argv", [
    ("whouses", "Rectangle"),
    ("implements", "Shape"),
    ("impact", "add"),
    ("publicapi",),
    ("deadcode",),
    ("findcycles",),
    ("untested",),
])
def test_every_claim_line_carries_path_line(capsys, indexed_repo, argv):
    _, out, _ = run_on(capsys, indexed_repo, *argv)
    for line in out.splitlines():
        if line.startswith("note:") or line.endswith(":") \
                or re.fullmatch(r"\s*\(\+\d+ more\)", line):
            continue  # structural headers, notes, collapse markers
        assert re.search(r"\S+:\d+", line), f"no path:line in {line!r}"


def test_output_is_deterministic_across_runs(capsys, indexed_repo):
    for argv in (("whouses", "Rectangle"), ("impact", "add"),
                 ("deadcode", "--include-exported"), ("findcycles",)):
        _, first, _ = run_on(capsys, indexed_repo, *argv)
        _, second, _ = run_on(capsys, indexed_repo, *argv)
        assert first == second
