#!/usr/bin/env python3
"""runlite — command output distiller.

Runs a build/test/lint command, captures stdout+stderr merged, and prints a
failure-focused report — exit code, wall time, and extracted problems with
file:line references — instead of thousands of lines of passing noise.

    runlite -- pytest -x
    runlite --max-tokens 400 -- go test ./...
    runlite --full-log build.log -- make test

Extractors are pure functions over the captured text (pytest, jest/vitest,
go test, cargo, tsc, eslint, gcc/clang, plus a generic fallback), chosen by
command name first, then log fingerprint. runlite exits with the wrapped
command's exit code; its own failures use the reserved codes 125 (internal)
and 127 (command not found).
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

__version__ = "0.1.3"

EXIT_INTERNAL = 125   # runlite's own failure, never the wrapped command's
EXIT_NOT_FOUND = 127

TAIL_LINES = 20       # generic fallback keeps this many trailing lines
MAX_CONTEXT = 6       # cc extractor: context lines kept per diagnostic

# Loose path:line matcher for attaching references to free-form lines.
FILE_LINE = re.compile(r"([A-Za-z0-9_.\\/-]+\.[A-Za-z][A-Za-z0-9]*):(\d+)")


# ----------------------------------------------------------------- problems
# A problem is {"title": one-liner, "ref": "path:line" or "", "detail": [..]}.

def _problem(title, ref="", detail=None):
    return {"title": title, "ref": ref, "detail": detail or []}


def _trim(lines):
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


# --------------------------------------------------------------- extractors
# Each parse function takes the captured log text and returns
# (problems, tail_lines); only the generic fallback uses tail_lines.

_PYTEST_SECTION = re.compile(r"^={4,}\s(.+?)\s={4,}$")
_PYTEST_SEP = re.compile(r"^_{4,}\s(.+?)\s_{4,}$")
_PYTEST_REF = re.compile(r"^([^\s:]+):(\d+):")


def parse_pytest(log):
    problems = []
    in_failures = False
    title, body = None, []

    def flush():
        nonlocal title, body
        if title is not None:
            ref = ""
            for line in body:
                m = _PYTEST_REF.match(line)
                if m:
                    ref = "%s:%s" % (m.group(1), m.group(2))
            problems.append(_problem("FAIL %s" % title, ref, _trim(body)))
        title, body = None, []

    for line in log.splitlines():
        m = _PYTEST_SECTION.match(line)
        if m:
            flush()
            in_failures = m.group(1) in ("FAILURES", "ERRORS")
            continue
        if in_failures:
            m = _PYTEST_SEP.match(line)
            if m:
                flush()
                title = m.group(1)
            elif title is not None:
                body.append(line.rstrip())
    flush()

    if not problems:  # -q runs: no FAILURES section, only the short summary
        for line in log.splitlines():
            m = re.match(r"^(FAILED|ERROR)\s+(\S+)(?:\s+-\s+(.*))?$", line)
            if m and "::" in m.group(2):
                title = "%s %s" % (m.group(1), m.group(2))
                if m.group(3):
                    title += " - " + m.group(3)
                problems.append(_problem(title, m.group(2).split("::")[0]))
    return problems, []


_GO_FAIL = re.compile(r"^\s*--- FAIL: (\S+)")
_GO_BUILD = re.compile(r"^([^\s:]+\.go):(\d+)(?::\d+)?: (.+)$")
_GO_REF = re.compile(r"([^\s:]+\.go):(\d+)")


def parse_gotest(log):
    problems = []
    name, body = None, []

    def flush():
        nonlocal name, body
        if name is not None:
            ref = ""
            for line in body:
                m = _GO_REF.search(line)
                if m:
                    ref = "%s:%s" % (m.group(1), m.group(2))
                    break
            problems.append(_problem("FAIL %s" % name, ref, _trim(body)))
        name, body = None, []

    for line in log.splitlines():
        m = _GO_FAIL.match(line)
        if m:
            flush()
            name = m.group(1)
            continue
        if name is not None and (line.startswith("    ") or line.startswith("\t")):
            body.append(line.rstrip())
            continue
        flush()
        m = _GO_BUILD.match(line)
        if m:  # compile errors appear outside any --- FAIL block
            problems.append(_problem(m.group(3),
                                     "%s:%s" % (m.group(1), m.group(2))))
    flush()
    return problems, []


_CARGO_DIAG = re.compile(r"^(error(?:\[E\d+\])?|warning): (.+)$")
_CARGO_ARROW = re.compile(r"^\s*-->\s+([^\s:]+):(\d+):\d+")
_CARGO_TESTHDR = re.compile(r"^---- (\S+) (?:stdout|stderr) ----$")
_CARGO_PANIC = re.compile(r"panicked at\s+([^\s:]+):(\d+):\d+")
_CARGO_NOISE = re.compile(
    r"aborting due to|could not compile|test failed, to rerun"
    r"|generated \d+ warning|build failed")


def parse_cargo(log):
    lines = log.splitlines()
    problems = []
    i = 0
    while i < len(lines):
        m = _CARGO_DIAG.match(lines[i])
        if m and not _CARGO_NOISE.search(m.group(2)):
            body, ref = [], ""
            j = i + 1
            while j < len(lines) and lines[j].strip():
                body.append(lines[j].rstrip())
                a = _CARGO_ARROW.match(lines[j])
                if a and not ref:
                    ref = "%s:%s" % (a.group(1), a.group(2))
                j += 1
            problems.append(_problem("%s: %s" % (m.group(1), m.group(2)),
                                     ref, body))
            i = j
            continue
        m = _CARGO_TESTHDR.match(lines[i])
        if m:
            body, ref = [], ""
            j = i + 1
            while (j < len(lines) and not _CARGO_TESTHDR.match(lines[j])
                   and not lines[j].startswith("failures:")):
                body.append(lines[j].rstrip())
                p = _CARGO_PANIC.search(lines[j])
                if p and not ref:
                    ref = "%s:%s" % (p.group(1), p.group(2))
                j += 1
            problems.append(_problem("FAIL %s" % m.group(1), ref, _trim(body)))
            i = j
            continue
        i += 1
    return problems, []


_TSC_PAREN = re.compile(r"^(.+?)\((\d+),\d+\): (error|warning) (TS\d+): (.+)$")
_TSC_COLON = re.compile(r"^(.+?):(\d+):\d+ - (error|warning) (TS\d+): (.+)$")


def parse_tsc(log):
    problems = []
    for line in log.splitlines():
        m = _TSC_PAREN.match(line) or _TSC_COLON.match(line)
        if m:
            path, ln, sev, code, msg = m.groups()
            problems.append(_problem("%s %s: %s" % (sev, code, msg),
                                     "%s:%s" % (path, ln)))
    return problems, []


_ESLINT_FILE = re.compile(r"^\S.*\.(?:[cm]?[jt]sx?|vue|svelte)$")
_ESLINT_MSG = re.compile(
    r"^\s+(\d+):\d+\s+(error|warning)\s+(.+?)(?:\s{2,}(\S+))?$")


def parse_eslint(log):
    problems = []
    current = None
    for line in log.splitlines():
        if _ESLINT_FILE.match(line):
            current = line.strip()
            continue
        m = _ESLINT_MSG.match(line)
        if m and current:
            ln, sev, msg, rule = m.groups()
            title = "%s: %s" % (sev, msg)
            if rule:
                title += " (%s)" % rule
            problems.append(_problem(title, "%s:%s" % (current, ln)))
    return problems, []


_CC_DIAG = re.compile(
    r"^([^\s:][^:]*):(\d+):(?:\d+:)?\s*(fatal error|error|warning|note): (.+)$")
_CC_SUMMARY = re.compile(
    r"^\d+ (?:errors?|warnings?)|^compilation terminated| generated\.$")


def parse_cc(log):
    problems = []
    cur = None
    for line in log.splitlines():
        m = _CC_DIAG.match(line)
        if m:
            path, ln, sev, msg = m.groups()
            if sev == "note" and cur is not None:
                cur["detail"].append(line.rstrip())
                continue
            cur = _problem("%s: %s" % (sev, msg), "%s:%s" % (path, ln))
            problems.append(cur)
        elif cur is not None:
            if _CC_SUMMARY.search(line) or not line.strip():
                cur = None
            elif len(cur["detail"]) < MAX_CONTEXT:
                cur["detail"].append(line.rstrip())
    return problems, []


_JS_BULLET = re.compile(r"^\s*● (.+)$")                 # jest failure block
_JS_VITEST = re.compile(r"^\s*FAIL\s+(\S+\s*>\s*.+)$")  # vitest failed test
_JS_STOP = re.compile(
    r"^\s*(● |PASS |FAIL |Tests?:|Test Suites:|Test Files|Snapshots:"
    r"|Time:|⎯+)")
_JS_REF = re.compile(r"([^\s():]+\.[cm]?[jt]sx?):(\d+)")


def parse_jstest(log):
    lines = log.splitlines()
    problems = []
    i = 0
    while i < len(lines):
        m = _JS_BULLET.match(lines[i]) or _JS_VITEST.match(lines[i])
        if m:
            body, ref = [], ""
            j = i + 1
            while j < len(lines) and not _JS_STOP.match(lines[j]):
                body.append(lines[j].rstrip())
                r = _JS_REF.search(lines[j])
                if r and not ref:
                    ref = "%s:%s" % (r.group(1), r.group(2))
                j += 1
            problems.append(_problem("FAIL %s" % m.group(1).strip(),
                                     ref, _trim(body)))
            i = j
            continue
        i += 1
    return problems, []


_ERRORISH = re.compile(
    r"error|fail|fatal|exception|traceback|panic|assert|warning", re.I)


def parse_generic(log):
    lines = log.splitlines()
    problems = []
    for line in lines:
        if _ERRORISH.search(line):
            m = FILE_LINE.search(line)
            problems.append(_problem(line.strip(), m.group(0) if m else ""))
    return problems, lines[-TAIL_LINES:]


# ---------------------------------------------------------------- detection

class Extractor:
    def __init__(self, name, parse, fingerprint, cmds=(), cmd_match=None):
        self.name = name
        self.parse = parse
        self.fingerprint = re.compile(fingerprint, re.M)
        self._cmds = set(cmds)
        self._cmd_match = cmd_match

    def matches_cmd(self, toks):
        if self._cmd_match:
            return self._cmd_match(toks)
        return bool(self._cmds & set(toks))


EXTRACTORS = [
    Extractor("pytest", parse_pytest,
              r"^=+ test session starts =+$|short test summary info",
              cmds=("pytest", "py.test")),
    Extractor("go test", parse_gotest,
              r"^\s*--- (FAIL|PASS): |^ok\s+\S+\s+[\d.]+s|^FAIL\s+\S+\s+[\d.]+s",
              cmd_match=lambda t: bool(t) and t[0] == "go" and "test" in t),
    Extractor("cargo", parse_cargo,
              r"^error\[E\d+\]|^\s+Compiling \S+ v\d|panicked at",
              cmds=("cargo",)),
    Extractor("tsc", parse_tsc, r"\berror TS\d+", cmds=("tsc",)),
    Extractor("eslint", parse_eslint,
              r"^[✖x] \d+ problems?|^\s+\d+:\d+\s+(error|warning)\s{2}",
              cmds=("eslint",)),
    Extractor("jest/vitest", parse_jstest,
              r"^Test Suites: |^\s*● |^ FAIL  |^\s*Test Files\s+\d",
              cmds=("jest", "vitest")),
    Extractor("cc", parse_cc,
              r"^[^:\n]+:\d+:\d+: (fatal error|error|warning): ",
              cmds=("gcc", "g++", "clang", "clang++", "cc", "c++")),
]

GENERIC = Extractor("generic", parse_generic, r"(?!)")


def _cmd_tokens(cmd):
    toks = []
    for arg in cmd:
        base = os.path.basename(arg).lower()
        for suffix in (".exe", ".cmd", ".bat", ".py", ".js"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        toks.append(base)
    return toks


def detect(cmd, log):
    toks = _cmd_tokens(cmd)
    for ext in EXTRACTORS:
        if ext.matches_cmd(toks):
            return ext
    for ext in EXTRACTORS:
        if ext.fingerprint.search(log):
            return ext
    return GENERIC


# ---------------------------------------------------------------- rendering

def _tokens_of(lines):
    return sum(len(line) + 1 for line in lines) // 4


def _one_line(p):
    return p["title"] + ("  " + p["ref"] if p["ref"] else "")


def _block(p):
    return [_one_line(p)] + ["  " + d for d in p["detail"]]


def render(exit_code, wall, ext_name, problems, tail, max_tokens, log_path):
    n = len(problems)
    if n:
        count = "%d problem%s" % (n, "s"[: n != 1])
    elif exit_code == 0:
        count = "no problems"
    else:  # a failing run with nothing parsed must not read as a pass
        count = "no findings (see log tail)" if tail else "no findings"
    header = ["# runlite: exit %d in %.2fs (%s) %s"
              % (exit_code, wall, ext_name, count)]
    if log_path:
        header.append("# raw log: %s" % log_path)

    lines = list(header)
    for p in problems:
        lines.append("")
        lines.extend(_block(p))
    if tail:
        lines.append("")
        lines.append("log tail (last %d lines)" % len(tail))
        lines.extend("  " + t for t in tail)

    if max_tokens and _tokens_of(lines) > max_tokens and problems:
        # Budget rule (ADR-004): first problem in full, rest one line each.
        lines = list(header)
        lines.append("")
        lines.extend(_block(problems[0]))
        if len(problems) > 1:
            lines.append("")
            lines.extend(_one_line(p) for p in problems[1:])
            lines.append("(… %d problem%s collapsed to one line each for "
                         "--max-tokens %d)"
                         % (n - 1, "s"[: n - 1 != 1], max_tokens))
        while _tokens_of(lines) > max_tokens and problems[0]["detail"]:
            # Still over: shrink the first problem's detail from the bottom.
            cut = lines.index("") + 1 + 1 + len(problems[0]["detail"])
            del lines[cut - 1]
            problems[0]["detail"].pop()
            if not problems[0]["detail"] or _tokens_of(lines) <= max_tokens:
                lines.insert(cut - 1, "  (… detail truncated)")
                break
    return lines


# ---------------------------------------------------------------------- CLI

def _resolve_windows_cmd(cmd):
    """Windows CreateProcess ignores PATHEXT, so bare names of .cmd/.bat
    shims (npx, tsc, npm) raise FileNotFoundError even though a shell finds
    them. Resolve argv[0] the way a shell would; leave it unchanged when
    nothing matches so the not-found path still reports the bare name
    (known-issue runlite-npx-not-found-windows)."""
    resolved = shutil.which(cmd[0])
    if resolved:
        return [resolved] + cmd[1:]
    return cmd


def _split_argv(argv):
    """Split runlite's own options from the wrapped command."""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1:]
    takes_value = {"--max-tokens", "--full-log"}
    i = 0
    while i < len(argv):
        if argv[i] in takes_value:
            i += 2
        elif argv[i].startswith("-"):
            i += 1
        else:
            return argv[:i], argv[i:]
    return argv, []


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    opts, cmd = _split_argv(argv)

    parser = argparse.ArgumentParser(
        prog="runlite",
        description="run a command and print a failure-focused report",
        usage="runlite [options] -- CMD [ARGS...]")
    parser.add_argument("--max-tokens", type=int, metavar="N", default=0,
                        help="over budget: first problem full, rest one line")
    parser.add_argument("--full-log", metavar="PATH", default="",
                        help="also write the raw log to PATH and print it")
    parser.add_argument("--version", action="version",
                        version="runlite %s" % __version__)
    args = parser.parse_args(opts)

    if not cmd:
        print("runlite: no command given (usage: runlite [options] -- CMD)",
              file=sys.stderr)
        return EXIT_INTERNAL

    # Detection and messages keep the command as typed; only the spawn
    # uses the resolved path.
    spawn = _resolve_windows_cmd(cmd) if os.name == "nt" else cmd
    try:
        start = time.monotonic()
        proc = subprocess.run(spawn, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        wall = time.monotonic() - start
    except FileNotFoundError:
        print("runlite: command not found: %s" % cmd[0], file=sys.stderr)
        return EXIT_NOT_FOUND
    except OSError as exc:
        print("runlite: %s" % exc, file=sys.stderr)
        return EXIT_INTERNAL

    raw = proc.stdout or b""
    log = raw.decode("utf-8", errors="replace")

    if args.full_log:
        parent = os.path.dirname(args.full_log)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(args.full_log, "wb") as fh:
            fh.write(raw)

    ext = detect(cmd, log)
    problems, tail = ext.parse(log)
    if proc.returncode != 0 and not problems and not tail:
        # The named extractor parsed nothing from a failing run (e.g. the
        # test framework itself is missing); never report less than the log.
        problems, tail = parse_generic(log)
    lines = render(proc.returncode, wall, ext.name, problems, tail,
                   args.max_tokens, args.full_log)
    try:  # tool logs carry symbols (✕, ●, ⎯) a cp1252 console default would eat
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("\n".join(lines))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
