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


# ----------------------------------------------------------------- rendering

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


def test_end_to_end_fingerprint_detection(capsys):
    path = os.path.join(FIX, "pytest_fail.log")
    prog = ("import sys; sys.stdout.write(open(%r, encoding='utf-8').read()); "
            "sys.exit(1)" % path)
    code, out, _ = run(["--", sys.executable, "-c", prog], capsys)
    assert code == 1
    assert "(pytest) 2 problems" in out
    assert "FAIL test_login_mfa  tests/test_auth.py:24" in out
