import os
import re
import sys

import runlite

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "logs")


def log(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return fh.read()


def extractor(name):
    if name == "generic":
        return runlite.GENERIC
    return next(e for e in runlite.EXTRACTORS if e.name == name)


def parse(name, fixture):
    return extractor(name).parse(log(fixture))


def run(argv, capsys):
    code = runlite.main(argv)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# -------------------------------------------------------------------- runner

def test_exit_code_passthrough_failure(capsys):
    code, out, _ = run(["--", sys.executable, "-c", "raise SystemExit(3)"],
                       capsys)
    assert code == 3
    assert out.startswith("# runlite: exit 3 in ")


def test_exit_code_passthrough_success(capsys):
    code, out, _ = run(["--", sys.executable, "-c", "print('ok')"], capsys)
    assert code == 0
    assert re.search(r"exit 0 in \d+\.\d\ds", out)


def test_stdout_stderr_merged(tmp_path, capsys):
    dest = tmp_path / "log.txt"
    prog = ("import sys; sys.stdout.write('to-out\\n'); "
            "sys.stderr.write('to-err\\n')")
    code, _, _ = run(["--full-log", str(dest), "--",
                      sys.executable, "-c", prog], capsys)
    assert code == 0
    text = dest.read_text()
    assert "to-out" in text and "to-err" in text


def test_command_not_found(capsys):
    code, _, err = run(["--", "runlite-no-such-cmd-xyz"], capsys)
    assert code == 127
    assert "command not found" in err


def test_no_command_given(capsys):
    code, _, err = run([], capsys)
    assert code == 125
    assert "no command" in err


def test_resolve_windows_cmd(monkeypatch):
    # PATHEXT shims (npx.cmd) resolve through shutil.which; unknown names
    # pass through untouched so the 127 path reports the bare name.
    shim = r"C:\npm\npx.cmd"
    monkeypatch.setattr(runlite.shutil, "which",
                        lambda name: shim if name == "npx" else None)
    assert runlite._resolve_windows_cmd(["npx", "tsc", "--noEmit"]) == \
        [shim, "tsc", "--noEmit"]
    assert runlite._resolve_windows_cmd(["nosuch", "-x"]) == ["nosuch", "-x"]


def test_windows_cmd_shim_runs(tmp_path, capsys, monkeypatch):
    # End-to-end repro of known-issue runlite-npx-not-found-windows: a bare
    # name that only exists as a .cmd shim on PATH must spawn, not 127.
    if os.name != "nt":
        import pytest
        pytest.skip("windows-only: .cmd shims")
    (tmp_path / "shimtool.cmd").write_text("@echo off\necho shim-ran\n")
    monkeypatch.setenv("PATH",
                       str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    code, out, _ = run(["--", "shimtool"], capsys)
    assert code == 0
    assert "exit 0" in out


def test_split_argv_without_separator():
    assert runlite._split_argv(["--max-tokens", "50", "echo", "hi"]) == (
        ["--max-tokens", "50"], ["echo", "hi"])
    assert runlite._split_argv(["--", "--max-tokens", "5"]) == (
        [], ["--max-tokens", "5"])


# ----------------------------------------------------------------- detection

def test_detect_by_command_name():
    assert runlite.detect(["pytest", "-x"], "").name == "pytest"
    assert runlite.detect(["python", "-m", "pytest"], "").name == "pytest"
    assert runlite.detect(["go", "test", "./..."], "").name == "go test"
    assert runlite.detect(["npx", "vitest", "run"], "").name == "jest/vitest"
    assert runlite.detect(["clang", "-c", "x.c"], "").name == "cc"


def test_detect_by_fingerprint_when_wrapped():
    assert runlite.detect(["make", "test"],
                          log("pytest_fail.log")).name == "pytest"
    assert runlite.detect(["make"], log("cargo_fail.log")).name == "cargo"
    assert runlite.detect(["make"], log("gotest_fail.log")).name == "go test"


def test_detect_generic_fallback():
    assert runlite.detect(["make"], log("mixed_unknown.log")).name == "generic"


def test_next_build_wins_over_jest_bullet_fingerprint():
    """`next build`'s route legend uses ● — jest's failure marker."""
    assert runlite.detect(["npm", "run", "build"],
                          log("next_build_pass.log")).name == "next build"
    assert runlite.detect(["npx", "next", "build"], "").name == "next build"


# ---------------------------------------------------------------- extractors

def test_pytest_failures():
    problems, tail = parse("pytest", "pytest_fail.log")
    assert tail == []
    assert [p["title"] for p in problems] == [
        "FAIL test_login_mfa", "FAIL test_retry_count"]
    assert problems[0]["ref"] == "tests/test_auth.py:24"
    assert problems[1]["ref"] == "tests/test_http.py:41"
    assert any("AssertionError" in d for d in problems[0]["detail"])


def test_pytest_passing_is_green():
    problems, _ = parse("pytest", "pytest_pass.log")
    assert problems == []
    lines = runlite.render(0, 0.31, "pytest", [], [], 0, "")
    assert lines == ["# runlite: exit 0 in 0.31s (pytest) no problems"]


def test_gotest_failures():
    problems, _ = parse("go test", "gotest_fail.log")
    assert [p["title"] for p in problems] == [
        "FAIL TestLoginMFA", "FAIL TestRetryCount"]
    assert problems[0]["ref"] == "auth_test.go:24"
    assert problems[1]["ref"] == "client_test.go:41"
    assert any("retries = 3, want 5" in d for d in problems[1]["detail"])


def test_gotest_passing_is_green():
    problems, _ = parse("go test", "gotest_pass.log")
    assert problems == []


def test_cargo_compile_error():
    problems, _ = parse("cargo", "cargo_fail.log")
    assert len(problems) == 1
    assert problems[0]["title"] == "error[E0308]: mismatched types"
    assert problems[0]["ref"] == "src/client.rs:17"
    assert not any("aborting due to" in p["title"] for p in problems)


def test_cargo_test_panic():
    problems, _ = parse("cargo", "cargo_test_fail.log")
    assert len(problems) == 1
    assert problems[0]["title"] == "FAIL tests::retry_count"
    assert problems[0]["ref"] == "src/client.rs:41"
    assert any("panicked at" in d for d in problems[0]["detail"])


def test_tsc_errors():
    problems, _ = parse("tsc", "tsc_fail.log")
    assert len(problems) == 2
    assert problems[0]["title"].startswith("error TS2322: ")
    assert problems[0]["ref"] == "src/auth/login.ts:24"
    assert problems[1]["ref"] == "src/http/client.ts:41"


def test_eslint_problems():
    problems, _ = parse("eslint", "eslint_fail.log")
    assert len(problems) == 3
    assert problems[0]["title"] == "error: 'mfa' is not defined (no-undef)"
    assert problems[0]["ref"] == "/repo/src/auth/login.js:24"
    assert problems[1]["title"].startswith("warning: ")
    assert problems[2]["ref"] == "/repo/src/http/client.js:41"


def test_cc_diagnostics():
    problems, _ = parse("cc", "gcc_fail.log")
    assert len(problems) == 2
    assert problems[0]["title"] == "error: expected ';' after expression"
    assert problems[0]["ref"] == "src/client.c:41"
    assert problems[0]["detail"] == [
        "    retries = 3", "              ^", "              ;"]
    assert problems[1]["title"].startswith("warning: unused variable")
    assert problems[1]["ref"] == "src/auth.c:24"
    assert all("generated" not in d for d in problems[1]["detail"])


def test_jest_failure_block():
    problems, _ = parse("jest/vitest", "jest_fail.log")
    assert len(problems) == 1
    assert problems[0]["title"] == "FAIL login › rejects missing MFA"
    assert problems[0]["ref"] == "src/auth/login.test.ts:23"
    assert any("expect(received).toBe(false)" in d
               for d in problems[0]["detail"])


def test_vitest_failure_block():
    problems, _ = parse("jest/vitest", "vitest_fail.log")
    assert len(problems) == 1
    assert problems[0]["title"] == (
        "FAIL src/math.test.ts > add > handles negatives")
    assert problems[0]["ref"] == "src/math.test.ts:14"


def test_generic_keeps_errorish_and_tail():
    problems, tail = parse("generic", "mixed_unknown.log")
    assert len(tail) == 20
    assert tail[0] == "copying artifact core.pkg"
    titles = [p["title"] for p in problems]
    assert "warning: config value 'threads' ignored" in titles
    error = next(p for p in problems if p["title"].startswith("ERROR:"))
    assert error["ref"] == "core/link.c:88"
    # non-errorish early lines appear nowhere in the rendered report
    lines = runlite.render(1, 1.0, "generic", problems, tail, 0, "")
    assert "Step 2/8" not in "\n".join(lines)


def test_next_build_pass_reports_nothing():
    """A green build must not report the route legend as a failure."""
    problems, tail = parse("next build", "next_build_pass.log")
    assert (problems, tail) == ([], [])
    lines = runlite.render(0, 26.13, "next build", problems, tail, 0, "")
    assert lines == ["# runlite: exit 0 in 26.13s (next build) no problems"]


def test_next_build_failure_keeps_the_type_error():
    problems, tail = parse("next build", "next_build_fail.log")
    titles = [p["title"] for p in problems]
    assert "Failed to compile." in titles
    err = next(p for p in problems if p["title"].startswith("Type error:"))
    assert err["ref"].endswith("src/lib/related.ts:42")
    assert tail  # a failing build still carries its trailing lines


# ----------------------------------------------------------------- rendering

def test_exit_zero_drops_failure_shaped_findings():
    """The exit code is the reliable signal; a FAIL under `exit 0` is a
    misfire, and reads to a user as 'the build is failing'."""
    problems = [runlite._problem("FAIL (SSG)", "", ["detail"]),
                runlite._problem("warning: unused import", "src/a.ts:3")]
    lines = runlite.render(0, 26.13, "jest/vitest", problems, [], 0, "")
    assert "FAIL" not in "\n".join(lines)
    assert "warning: unused import  src/a.ts:3" in lines
    assert "1 problem" in lines[0]
    assert lines[1].startswith("# note: dropped 1 failure-shaped finding")


def test_failing_exit_never_reads_as_pass():
    lines = runlite.render(1, 0.02, "pytest", [], [], 0, "")
    assert lines == ["# runlite: exit 1 in 0.02s (pytest) no findings"]
    lines = runlite.render(1, 0.02, "pytest", [], ["some tail"], 0, "")
    assert lines[0].endswith("no findings (see log tail)")


def test_empty_extract_on_failure_falls_back_to_tail(capsys):
    # A pytest-named command that fails without pytest-format output (the
    # framework itself missing): the report must still carry the log tail.
    prog = ("import sys; sys.stderr.write('no module named pytest\\n'); "
            "sys.exit(1)")
    code, out, _ = run(["--", sys.executable, "-c", prog, "pytest"], capsys)
    assert code == 1
    assert "(pytest) no findings (see log tail)" in out
    assert "no module named pytest" in out


def test_max_tokens_first_full_rest_one_line():
    problems, _ = parse("pytest", "pytest_fail.log")
    lines = runlite.render(1, 0.53, "pytest", problems, [], 60, "")
    assert "FAIL test_login_mfa  tests/test_auth.py:24" in lines
    assert "FAIL test_retry_count  tests/test_http.py:41" in lines
    # the second problem is exactly its one-liner: none of its detail survives
    assert "assert 3 == 5" not in "\n".join(lines)
    assert any(l.startswith("(…") for l in lines)


def test_within_budget_stays_full():
    problems, _ = parse("pytest", "pytest_fail.log")
    lines = runlite.render(1, 0.53, "pytest", problems, [], 100000, "")
    assert any("assert 3 == 5" in l for l in lines)


def test_full_log_byte_exact(tmp_path, capsys):
    dest = tmp_path / "raw.log"
    prog = "import sys; sys.stdout.buffer.write(b'alpha\\nbeta\\n')"
    code, out, _ = run(["--full-log", str(dest), "--",
                        sys.executable, "-c", prog], capsys)
    assert dest.read_bytes() == b"alpha\nbeta\n"
    assert "# raw log: %s" % dest in out


def test_header_reports_the_suppressed_log_size(capsys):
    """The report stands in for a log the caller never sees; say how big it
    was. runlite holds the whole log already, so the figure is exact - and
    it is the only honest baseline the savings hook can get for a build it
    must not re-run."""
    prog = r"import sys; sys.stdout.write('x' * 5000)"
    _, out, _ = run(["--", sys.executable, "-c", prog], capsys)
    assert "[log 5000 B]" in out.splitlines()[0]


def test_log_size_omitted_when_not_measured():
    """render() is called directly by tests and by nothing else; an absent
    measurement must not print as `[log 0 B]`, which would read as an empty
    log rather than an unmeasured one."""
    lines = runlite.render(0, 0.31, "pytest", [], [], 0, "")
    assert lines == ["# runlite: exit 0 in 0.31s (pytest) no problems"]


def test_end_to_end_fingerprint_detection(capsys):
    path = os.path.join(FIX, "pytest_fail.log")
    prog = ("import sys; sys.stdout.write(open(%r, encoding='utf-8').read()); "
            "sys.exit(1)" % path)
    code, out, _ = run(["--", sys.executable, "-c", prog], capsys)
    assert code == 1
    assert "(pytest) 2 problems" in out
    assert "FAIL test_login_mfa  tests/test_auth.py:24" in out


# ------------------------------------------------ stderr encoding (INVARIANTS)

def test_main_pins_stderr_to_utf8(tmp_path, monkeypatch):
    """runlite has no _pin_utf8 helper - main() pins both streams at entry,
    before any error can be printed. Error text carries the same non-ASCII
    punctuation as the reports and is read by the same agent."""
    import io as _io
    import sys as _sys
    saved = _sys.stdout, _sys.stderr
    try:
        _sys.stdout = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252")
        _sys.stderr = _io.TextIOWrapper(_io.BytesIO(), encoding="cp1252")
        runlite.main(["--", sys.executable, "-c", "pass"])
        assert _sys.stderr.encoding.lower().replace("-", "") == "utf8"
    finally:
        _sys.stdout, _sys.stderr = saved
