import io
import os
import subprocess
import sys
import time

import pytest

import tokq

FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name):
    return os.path.join(FIX, name)


def run(argv, capsys):
    code = tokq.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def heuristic_tokens(nbytes):
    return round(nbytes / tokq.BYTES_PER_TOKEN)


# ---------------------------------------------------------------- estimator

def test_heuristic_estimate_and_header(capsys):
    code, out, _ = run(["--tokenizer", "heuristic", fx("plain_100b.txt")], capsys)
    assert code == 0
    assert "# estimator: heuristic (bytes/3.7)" in out
    assert "%d  %s" % (heuristic_tokens(100), fx("plain_100b.txt")) in out


def test_fallback_engages_when_tiktoken_unavailable(capsys, monkeypatch):
    # Block the import even if tiktoken is installed on this machine.
    monkeypatch.setitem(sys.modules, "tiktoken", None)
    code, out, _ = run(["--tokenizer", "auto", fx("plain_100b.txt")], capsys)
    assert code == 0
    assert "heuristic" in out.splitlines()[0]


def test_tiktoken_real_counts(capsys):
    tiktoken = pytest.importorskip("tiktoken")
    enc = tiktoken.get_encoding("o200k_base")
    with open(fx("plain_100b.txt")) as fh:
        expected = len(enc.encode(fh.read()))
    code, out, _ = run(["--tokenizer", "tiktoken", fx("plain_100b.txt")], capsys)
    assert code == 0
    assert "tiktoken (o200k_base)" in out.splitlines()[0]
    assert "%d  %s" % (expected, fx("plain_100b.txt")) in out


def test_estimator_stated_exactly_once(capsys):
    _, out, _ = run(["--tokenizer", "heuristic",
                     fx("plain_100b.txt"), fx("bundle.js")], capsys)
    headers = [l for l in out.splitlines() if l.startswith("# estimator:")]
    assert len(headers) == 1


# -------------------------------------------------------------------- meter

def test_meter_total_sums_files(capsys):
    _, out, _ = run(["--tokenizer", "heuristic",
                     fx("plain_100b.txt"), fx("bundle.js")], capsys)
    total = heuristic_tokens(100) + heuristic_tokens(1201)
    assert "%d  total (2 files)" % total in out


def test_meter_stdin(capsys, monkeypatch):
    class FakeStdin:
        buffer = io.BytesIO(b"x" * 37)

    monkeypatch.setattr(sys, "stdin", FakeStdin)
    code, out, _ = run(["--tokenizer", "heuristic", "-"], capsys)
    assert code == 0
    assert "%d  (stdin)" % heuristic_tokens(37) in out


def test_meter_flags_binary(capsys):
    _, out, _ = run(["--tokenizer", "heuristic", fx("binaryish.dat")], capsys)
    assert "[binary: size-based estimate]" in out


def test_meter_missing_file_exits_nonzero(capsys):
    code, out, err = run(["--tokenizer", "heuristic", fx("nope.txt")], capsys)
    assert code == 2
    assert "nope.txt" in err


# ---------------------------------------------------------------------- dir

def test_dir_heaviest_first_with_percentages(capsys):
    _, out, _ = run(["dir", fx("tree"), "--tokenizer", "heuristic"], capsys)
    # 400 + 200 + 100 bytes -> 108 + 54 + 27 tokens, total 189
    assert ": 189 tokens across 3 files" in out
    lines = out.splitlines()
    order = [l.split()[-1] for l in lines if "%" in l]
    assert order == ["a.txt", "sub/", "sub/b.txt", "sub/c.txt"]
    assert " 57.1%  a.txt" in out
    assert " 42.9%  sub/" in out
    assert " 14.3%  sub/c.txt" in out


def test_dir_prunes_skip_list(capsys):
    _, out, _ = run(["dir", fx("tree"), "--tokenizer", "heuristic"], capsys)
    assert "node_modules" not in out


def test_dir_deterministic(capsys):
    _, first, _ = run(["dir", fx("tree"), "--tokenizer", "heuristic"], capsys)
    _, second, _ = run(["dir", fx("tree"), "--tokenizer", "heuristic"], capsys)
    assert first == second


def test_dir_top_truncates(capsys):
    _, out, _ = run(["dir", fx("tree"), "--top", "2",
                     "--tokenizer", "heuristic"], capsys)
    assert "(+2 more paths" in out


# --------------------------------------------------------------------- lint

def lint(paths, capsys, *extra):
    return run(["lint", "--tokenizer", "heuristic", *extra, *paths], capsys)


def test_lint_lockfile_by_name(capsys):
    _, out, _ = lint([fx("package-lock.json")], capsys)
    assert "LOCKFILE" in out
    assert "structo" in out


def test_lint_minified_by_name(capsys):
    _, out, _ = lint([fx("tiny.min.js")], capsys)
    assert "MINIFIED" in out


def test_lint_minified_by_long_lines(capsys):
    _, out, _ = lint([fx("bundle.js")], capsys)
    assert "MINIFIED" in out
    assert "max line 1200 chars" in out


def test_lint_high_entropy(capsys):
    _, out, _ = lint([fx("entropy.b64")], capsys)
    assert "HIGH-ENTROPY" in out


def test_lint_binary(capsys):
    _, out, _ = lint([fx("binaryish.dat")], capsys)
    assert "BINARY" in out


def test_lint_big_source_suggests_xread(capsys, tmp_path):
    big = tmp_path / "big.py"
    big.write_text("def f():\n    return 1\n" * 900)  # ~20 KB, short lines
    _, out, _ = lint([str(big)], capsys, "--threshold", "1000")
    assert "BIG-FILE" in out
    assert "xread" in out


def test_lint_big_data_suggests_structo(capsys, tmp_path):
    big = tmp_path / "big.json"
    rows = ",\n".join('{"id": %d, "name": "row"}' % i for i in range(700))
    big.write_text("[\n%s\n]\n" % rows)
    _, out, _ = lint([str(big)], capsys, "--threshold", "1000")
    assert "BIG-DATA" in out
    assert "structo" in out


def test_lint_big_dir_suggests_repomap(capsys, tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    for i in range(4):
        (d / ("mod%d.py" % i)).write_text("x = 1\n" * 300)
    _, out, _ = lint([str(d)], capsys, "--threshold", "1000")
    assert "BIG-DIR" in out
    assert "repomap" in out


def test_lint_clean_file_no_findings(capsys):
    code, out, _ = lint([fx("plain_100b.txt")], capsys)
    assert code == 0
    assert "0 findings" in out


# ------------------------------------------------------------- budget gate

def test_budget_boundary_not_exceeded(capsys):
    # plain_100b.txt is exactly 27 heuristic tokens; at the boundary it passes.
    code, out, _ = lint([fx("plain_100b.txt")], capsys, "--budget", "27")
    assert code == 0
    assert "BUDGET EXCEEDED" not in out


def test_budget_exceeded_exits_nonzero(capsys):
    code, out, _ = lint([fx("plain_100b.txt")], capsys, "--budget", "26")
    assert code == 1
    assert "BUDGET EXCEEDED" in out


# ------------------------------------------------------------------ startup

def test_fallback_startup_under_100ms():
    # Spec: <100 ms in the fallback path. Allow a 5x multiplier for slow/cold
    # CI machines; take the best of three runs to shed interpreter cold-start
    # noise from the measurement.
    script = os.path.join(os.path.dirname(FIX), "..", "tokq.py")
    cmd = [sys.executable, script, "--tokenizer", "heuristic",
           fx("plain_100b.txt")]
    best = min(_timed_run(cmd) for _ in range(3))
    assert best < 0.5, "fallback startup took %.3fs" % best


def _timed_run(cmd):
    start = time.perf_counter()
    subprocess.run(cmd, check=True, capture_output=True)
    return time.perf_counter() - start


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
        tokq._pin_utf8()
        assert _sys.stdout.encoding.lower().replace("-", "") == "utf8"
        assert _sys.stderr.encoding.lower().replace("-", "") == "utf8"
    finally:
        _sys.stdout, _sys.stderr = saved
