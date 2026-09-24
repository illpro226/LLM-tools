"""Tests for `runlite trace` — the stack-trace intake.

Separate module from test_runlite.py: the runner tests spawn processes and
assert on exit-code passthrough, while these are pure functions over canned
trace text plus a handful of CLI checks.
"""

import io
import os
import re
import sys

import runlite

TFIX = os.path.join(os.path.dirname(__file__), "fixtures", "traces")


def trace_text(name):
    with open(os.path.join(TFIX, name), encoding="utf-8") as fh:
        return fh.read()


def trace_path(name):
    return os.path.join(TFIX, name)


def run_trace(capsys, name, *opts):
    code = runlite.main(["trace"] + list(opts) + [trace_path(name)])
    return code, capsys.readouterr().out


def stdin_of(monkeypatch, data):
    class Stub:
        buffer = io.BytesIO(data)
    monkeypatch.setattr(sys, "stdin", Stub())


# ------------------------------------------------------- per-language parsing

def test_python_reports_propagated_exception_first():
    traces = runlite.parse_python_trace(trace_text("python_chained.txt"))
    assert len(traces) == 1
    secs = traces[0]["sections"]
    assert secs[0]["header"].startswith("ValueError")
    assert secs[0]["kind"] == "raised"
    # The marker names the relation between the pair, so it arrives attached
    # to the later exception and has to land on the older one once the pair
    # is reordered propagated-first.
    assert secs[1]["header"].startswith("KeyError")
    assert secs[1]["kind"] == "during handling of"


def test_python_frames_are_innermost_first():
    trace = runlite.parse_python_trace(trace_text("python_chained.txt"))[0]
    frames = trace["sections"][0]["frames"]
    assert frames[0]["ref"] == "/app/parser.py:42"
    assert frames[-1]["ref"] == "/app/main.py:11"


def test_python_direct_cause_marker_recognized():
    text = ('Traceback (most recent call last):\n'
            '  File "/a.py", line 1, in f\n'
            'KeyError: 1\n'
            '\n'
            'The above exception was the direct cause of the following '
            'exception:\n'
            '\n'
            'Traceback (most recent call last):\n'
            '  File "/b.py", line 2, in g\n'
            'ValueError: bad\n')
    secs = runlite.parse_python_trace(text)[0]["sections"]
    assert secs[0]["header"] == "ValueError: bad"
    assert secs[1]["kind"] == "direct cause of"


def test_java_caused_by_becomes_a_section():
    trace = runlite.parse_java_trace(trace_text("java_caused_by.txt"))[0]
    secs = trace["sections"]
    assert [s["kind"] for s in secs] == ["raised", "caused by"]
    assert secs[1]["header"].startswith("java.lang.NullPointerException")


def test_java_module_prefixed_frame_does_not_truncate_section():
    """`at java.base/java.util.Optional.orElseGet(Optional.java:364)` has a
    "/" in the qualifier. An unmatched frame ends the section, so the two
    frames below it would vanish with nothing said."""
    trace = runlite.parse_java_trace(trace_text("java_caused_by.txt"))[0]
    refs = [f["ref"] for f in trace["sections"][1]["frames"]]
    assert "Optional.java:364" in refs
    assert "Boot.java:40" in refs


def test_java_jdk_frame_is_library_by_package():
    trace = runlite.parse_java_trace(trace_text("java_caused_by.txt"))[0]
    frame = next(f for f in trace["sections"][1]["frames"]
                 if "Optional.java" in f["ref"])
    assert frame["project"] is False


def test_node_header_is_the_error_not_the_source_echo():
    trace = runlite.parse_node_trace(trace_text("node_stack.txt"))[0]
    assert trace["sections"][0]["header"] == (
        "TypeError: handler is not a function")


def test_node_strips_column_from_ref():
    trace = runlite.parse_node_trace(trace_text("node_stack.txt"))[0]
    assert trace["sections"][0]["frames"][0]["ref"] == "/app/src/index.js:14"


def test_node_internal_and_modules_are_library():
    trace = runlite.parse_node_trace(trace_text("node_stack.txt"))[0]
    by_ref = {f["ref"]: f for f in trace["sections"][0]["frames"]}
    assert not by_ref["node:internal/modules/cjs/loader:1105"]["project"]
    assert not by_ref[
        "/app/node_modules/express/lib/router/index.js:280"]["project"]


def test_go_drops_the_argument_dump_from_frame_names():
    trace = runlite.parse_go_trace(trace_text("go_panic.txt"))[0]
    funcs = [f["func"] for f in trace["sections"][0]["frames"]]
    assert "main.handle" in funcs
    assert not any("0x" in f for f in funcs)


def test_go_internal_dir_is_project_code():
    """Go projects use internal/ for their own packages; it must not read as
    a library path the way node_modules does."""
    trace = runlite.parse_go_trace(trace_text("go_panic.txt"))[0]
    frame = next(f for f in trace["sections"][0]["frames"]
                 if "handler.go" in f["ref"])
    assert frame["project"] is True


def test_rust_new_format_takes_message_from_next_line():
    trace = runlite.parse_rust_trace(trace_text("rust_panic.txt"))[0]
    assert trace["sections"][0]["header"] == (
        "panicked: attempt to divide by zero")


def test_rust_old_format_message_is_inline():
    text = "thread 'main' panicked at 'index out of bounds', src/lib.rs:7:9\n"
    trace = runlite.parse_rust_trace(text)[0]
    assert trace["sections"][0]["header"] == "panicked: index out of bounds"
    assert trace["sections"][0]["frames"][0]["ref"] == "src/lib.rs:7"


def test_rust_panic_site_not_duplicated_by_backtrace():
    """The panic line spells it "src/calc.rs", the backtrace "./src/calc.rs"."""
    trace = runlite.parse_rust_trace(trace_text("rust_panic.txt"))[0]
    hits = [f for f in trace["sections"][0]["frames"]
            if "calc.rs:12" in f["ref"]]
    assert len(hits) == 1


def test_rust_panic_site_kept_when_no_backtrace():
    text = ("thread 'main' panicked at src/calc.rs:12:5:\n"
            "attempt to divide by zero\n"
            "note: run with `RUST_BACKTRACE=1` to display a backtrace\n")
    trace = runlite.parse_rust_trace(text)[0]
    assert trace["sections"][0]["frames"][0]["ref"] == "src/calc.rs:12"


# ------------------------------------------------------------ frame selection

def test_library_runs_collapse_and_project_frames_survive():
    trace = runlite.parse_python_trace(trace_text("python_chained.txt"))[0]
    items = runlite.select_frames(trace["sections"][0]["frames"])
    assert [i[0] for i in items].count("collapsed") == 1
    assert [i[1]["ref"] for i in items if i[0] == "frame"] == [
        "/app/parser.py:42", "/app/service.py:27", "/app/main.py:11"]


def test_panic_machinery_is_not_kept_just_for_being_innermost():
    """Rust and Go put unwind internals at frame 0; leading with those buries
    the line that actually broke."""
    trace = runlite.parse_rust_trace(trace_text("rust_panic.txt"))[0]
    items = runlite.select_frames(trace["sections"][0]["frames"])
    assert items[0][0] == "collapsed"
    assert items[1][1]["ref"] == "./src/calc.rs:12"


def test_all_library_trace_keeps_both_ends():
    frames = [runlite._frame("/x/site-packages/a.py", str(n), "f%d" % n)
              for n in range(5)]
    items = runlite.select_frames(frames)
    kept = [i[1]["ref"] for i in items if i[0] == "frame"]
    assert kept == ["/x/site-packages/a.py:0", "/x/site-packages/a.py:4"]


def test_no_frames_renders_a_note_not_a_bare_header(capsys):
    trace = {"lang": "python", "sections": [
        runlite._section("raised", "ValueError: x", [])]}
    lines, shown = runlite._trace_lines(trace, False)
    assert shown == 0
    assert lines[-1].strip() == "(no frames with a file:line)"


def test_collapsed_run_names_a_shared_origin():
    trace = runlite.parse_go_trace(trace_text("go_panic.txt"))[0]
    items = runlite.select_frames(trace["sections"][0]["frames"])
    assert [i[2] for i in items if i[0] == "collapsed"] == ["go stdlib"]


def test_mixed_run_falls_back_to_neutral_label():
    trace = runlite.parse_node_trace(trace_text("node_stack.txt"))[0]
    items = runlite.select_frames(trace["sections"][0]["frames"])
    assert [i[2] for i in items if i[0] == "collapsed"] == ["library"]


# ------------------------------------------------------------------ detection

def test_detect_picks_the_language_that_leads_a_mixed_log():
    text = ("some deploy noise\n" + trace_text("go_panic.txt")
            + "\n" + trace_text("python_chained.txt"))
    lang, traces = runlite.detect_traces(text)
    assert lang == "go"
    assert traces


def test_python_wins_when_it_leads():
    text = (trace_text("python_chained.txt") + "\n"
            + trace_text("go_panic.txt"))
    lang, _ = runlite.detect_traces(text)
    assert lang == "python"


def test_multiple_traces_of_one_language_all_reported():
    text = trace_text("go_panic.txt") + "\n" + trace_text("go_panic.txt")
    lang, traces = runlite.detect_traces(text)
    assert lang == "go"
    assert len(traces) == 2


def test_detection_returns_empty_for_ordinary_log_text():
    lang, traces = runlite.detect_traces("building...\nok\ndone in 3s\n")
    assert lang == "" and traces == []


# ----------------------------------------------------------------------- CLI

def test_trace_is_a_subcommand_not_a_wrapped_command(capsys):
    code, out = run_trace(capsys, "python_chained.txt")
    assert code == 0
    assert out.startswith("# runlite trace: python, 1 trace,")


def test_trace_reads_stdin(monkeypatch, capsys):
    stdin_of(monkeypatch, trace_text("go_panic.txt").encode("utf-8"))
    code = runlite.main(["trace"])
    assert code == 0
    assert "# runlite trace: go," in capsys.readouterr().out


def test_trace_reports_input_size(capsys):
    _, out = run_trace(capsys, "go_panic.txt")
    assert "[input %d B]" % os.path.getsize(trace_path("go_panic.txt")) in out


def test_unrecognized_input_exits_1_and_says_so(monkeypatch, capsys):
    stdin_of(monkeypatch, b"nothing trace-shaped here\n")
    code = runlite.main(["trace"])
    out = capsys.readouterr().out
    assert code == runlite.EXIT_NO_TRACE
    assert "no recognized stack trace" in out


def test_missing_file_is_an_internal_error(capsys):
    code = runlite.main(["trace", trace_path("no-such-file.txt")])
    assert code == runlite.EXIT_INTERNAL
    assert "runlite:" in capsys.readouterr().err


def test_all_frames_disables_collapsing(capsys):
    _, out = run_trace(capsys, "rust_panic.txt", "--all-frames")
    assert "…" not in out
    assert "panicking.rs:645" in out


def test_wrapped_command_named_trace_still_wraps(capsys):
    """`trace` is a subcommand only in argv[0]; after -- it is a program."""
    code = runlite.main(["--", sys.executable, "-c", "print('trace')"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("# runlite: exit 0")


def test_invalid_utf8_input_does_not_crash(monkeypatch, capsys):
    raw = trace_text("go_panic.txt").encode("utf-8") + b"\xff\xfe garbage\n"
    stdin_of(monkeypatch, raw)
    assert runlite.main(["trace"]) == 0
    assert "# runlite trace: go," in capsys.readouterr().out


# -------------------------------------------------------------------- budget

def test_budget_floor_still_carries_a_path_line(capsys):
    """The floor rung is the one that must not degrade into headers alone:
    an exception with no reference cannot be followed up with xread."""
    _, out = run_trace(capsys, "python_chained.txt", "--max-tokens", "60")
    assert "summary only" in out
    assert "/app/parser.py:42" in out


def test_budget_degradation_names_the_flag(capsys):
    _, out = run_trace(capsys, "python_chained.txt", "--max-tokens", "60")
    assert "--max-tokens 60" in out
    assert "--max-tokens 0" in out


def test_budget_floor_admits_dropped_chained_exceptions(capsys):
    _, out = run_trace(capsys, "python_chained.txt", "--max-tokens", "60")
    assert "(+1 chained)" in out


def test_every_budget_rung_is_bounded_and_monotonic(capsys):
    """INVARIANTS: each rung must be bounded, not merely smaller."""
    prev = None
    for budget in (400, 200, 120, 90, 75, 60, 30, 10):
        _, out = run_trace(capsys, "python_chained.txt",
                           "--max-tokens", str(budget))
        if prev is not None:
            assert len(out) <= prev
        prev = len(out)


def test_multi_trace_budget_collapses_the_later_traces(capsys, monkeypatch):
    text = trace_text("go_panic.txt") + "\n" + trace_text("go_panic.txt")
    stdin_of(monkeypatch, text.encode("utf-8"))
    runlite.main(["trace", "--max-tokens", "70"])
    out = capsys.readouterr().out
    assert "trimmed to fit --max-tokens 70" in out
    # Trace #1 keeps its frames; the second is down to one line.
    assert "/app/pick.go:14" in out
    assert out.count("panic: runtime error") == 2


def test_unbounded_default_matches_max_tokens_zero(capsys):
    _, a = run_trace(capsys, "python_chained.txt")
    _, b = run_trace(capsys, "python_chained.txt", "--max-tokens", "0")
    assert a == b


def test_output_is_deterministic_and_free_of_ansi(capsys):
    _, a = run_trace(capsys, "java_caused_by.txt")
    _, b = run_trace(capsys, "java_caused_by.txt")
    assert a == b
    assert "\x1b[" not in a


def test_trace_floor_is_bounded_for_many_traces(capsys, monkeypatch):
    """One summary per trace is O(traces); a log holding hundreds must
    still fit, keep trace #1, and count the rest."""
    one = trace_text("python_chained.txt")
    stdin_of(monkeypatch, ("\n".join([one] * 200)).encode("utf-8"))
    runlite.main(["trace", "--max-tokens", "150"])
    out = capsys.readouterr().out.splitlines()
    assert runlite._tokens_of(out) <= 150
    assert out[0].startswith("# runlite trace: python, 200 traces")
    assert re.match(r"^\(… \d+ more traces not listed for --max-tokens "
                    r"150\)$", out[-1])


UNRELATED = """2026-09-24 10:00:01 ERROR request failed
Traceback (most recent call last):
  File "/app/handlers.py", line 10, in handle
    return parse(body)
  File "/app/parser.py", line 42, in parse
    raise ValueError("bad")
ValueError: bad
2026-09-24 10:05:00 INFO recovered
2026-09-24 10:07:13 ERROR job crashed
Traceback (most recent call last):
  File "/app/jobs.py", line 7, in run
    total = 1 / count
ZeroDivisionError: division by zero
"""


def test_unrelated_python_tracebacks_are_separate_traces():
    """Only a relation marker chains two tracebacks. Two errors minutes
    apart in a service log folded into one 'chain', the later presented as
    raised while handling the earlier - a causal claim the log never made."""
    lang, traces = runlite.detect_traces(UNRELATED)
    assert lang == "python" and len(traces) == 2
    assert [t["sections"][0]["header"] for t in traces] == [
        "ValueError: bad", "ZeroDivisionError: division by zero"]
    assert all(len(t["sections"]) == 1 for t in traces)
    # a real chain in the same log still stays one trace
    _, chained = runlite.detect_traces(
        UNRELATED + trace_text("python_chained.txt"))
    assert len(chained) == 3 and len(chained[2]["sections"]) > 1
