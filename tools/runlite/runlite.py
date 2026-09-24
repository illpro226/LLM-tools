#!/usr/bin/env python3
"""runlite — command output distiller.

Runs a build/test/lint command, captures stdout+stderr merged, and prints a
failure-focused report — exit code, wall time, and extracted problems with
file:line references — instead of thousands of lines of passing noise.

    runlite -- pytest -x
    runlite --max-tokens 400 -- go test ./...
    runlite --full-log build.log -- make test

Extractors are pure functions over the captured text (pytest, jest/vitest,
go test, cargo, tsc, eslint, gcc/clang, next build, plus a generic
fallback), chosen by command name first, then log fingerprint. A run that
exited 0 never reports failure-shaped findings: the exit code is the
reliable signal and a contradicted finding is an extractor misfire.
runlite exits with the wrapped command's exit code; its own failures use
the reserved codes 125 (internal) and 127 (command not found).

    runlite trace app.log
    kubectl logs pod | runlite trace

`trace` does the same job for a stack trace runlite did not produce —
one that arrived from a log file, CI, a service, a paste. Python, Java,
Node, Go and Rust traces are parsed to the exception plus the frames that
are this project's code, with library runs collapsed. It exits 0 when it
distilled a trace, 1 when the input held none, 125 on its own failure.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time

__version__ = "0.5.0"

EXIT_INTERNAL = 125   # runlite's own failure, never the wrapped command's
EXIT_NOT_FOUND = 127
EXIT_NO_TRACE = 1     # `trace` only: input held no recognizable stack trace

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


# A `next build` reports errors with these markers; everything else it
# prints on the way to exit 0 — including the route-type legend — is noise.
_NEXT_ERR = re.compile(
    r"^\s*(?:⨯|Failed to compile\.|Type error:|Error:|SyntaxError:|"
    r"Module not found:|Build error occurred)")
NEXT_DETAIL_LINES = 8


def parse_next_build(log):
    """Next.js build: only real compile/type errors count as problems.

    Every successful `next build` ends with a route-type legend whose `●`
    and `ƒ` glyphs read as jest bullets, so the jest/vitest extractor
    claimed the log by fingerprint and rewrote the legend to `FAIL` — a
    green build reporting a failure (known-issue
    archive/runlite-next-build-legend-read-as-failure). Finding nothing here
    returns no tail either, so a failing build still falls through to the
    generic extractor rather than being reported as clean.
    """
    lines = log.splitlines()
    problems = []
    i = 0
    while i < len(lines):
        if _NEXT_ERR.match(lines[i]):
            body = []
            j = i + 1
            while (j < len(lines) and len(body) < NEXT_DETAIL_LINES
                   and lines[j].strip()):
                body.append(lines[j].rstrip())
                j += 1
            m = FILE_LINE.search("\n".join([lines[i]] + body))
            if not m and i:
                # `Type error:` carries no path — Next.js prints the
                # offending `./path:line:col` on the line just above it.
                m = FILE_LINE.search(lines[i - 1])
            problems.append(_problem(lines[i].strip(),
                                     m.group(0) if m else "", _trim(body)))
            i = j
            continue
        i += 1
    return problems, (lines[-TAIL_LINES:] if problems else [])


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
    # Before jest/vitest: `next build` output trips that extractor's bullet
    # fingerprint, and first match wins.
    Extractor("next build", parse_next_build,
              r"^\s*(?:▲ Next\.js|Creating an optimized production build)"
              r"|^Route \(app\)|^Route \(pages\)|prerendered as static HTML",
              cmd_match=lambda t: "next" in t and "build" in t),
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
    # The generic extractor's title is the raw log line, which usually
    # already carries the path:line it was found by; saying it twice is
    # pure overhead on the extractor that emits the most lines.
    if p["ref"] and p["ref"] not in p["title"]:
        return p["title"] + "  " + p["ref"]
    return p["title"]


def _block(p):
    return [_one_line(p)] + ["  " + d for d in p["detail"]]


# How every extractor labels a test that failed. On a run that exited 0 no
# test failed, so such a finding is an extractor misfire by construction.
_FAILURE_TITLE = re.compile(r"^FAIL(?:ED)?\b")


def render(exit_code, wall, ext_name, problems, tail, max_tokens, log_path,
           log_bytes=None, log_error=None):
    dropped = 0
    if exit_code == 0:
        # The exit code is the reliable signal; a "1 problem / FAIL" body
        # under an `exit 0` headline is read as the detail and reported to
        # the user as a failing build.
        kept = [p for p in problems if not _FAILURE_TITLE.match(p["title"])]
        dropped = len(problems) - len(kept)
        problems = kept
    n = len(problems)
    if n:
        count = "%d problem%s" % (n, "s"[: n != 1])
    elif exit_code == 0:
        count = "no problems"
    else:  # a failing run with nothing parsed must not read as a pass
        count = "no findings (see log tail)" if tail else "no findings"
    # The size of the log this report stands in for. runlite already holds
    # the whole thing in memory, so this is exact, not an estimate - the
    # only baseline in the suite that is. It tells the caller how much they
    # are *not* reading (a 400 KB log summarized to four lines is a
    # different claim than a 900 B one), and it lets the savings hook credit
    # runlite without re-running the build to measure it.
    size = " [log %d B]" % log_bytes if log_bytes is not None else ""
    header = ["# runlite: exit %d in %.2fs (%s) %s%s"
              % (exit_code, wall, ext_name, count, size)]
    if dropped:
        header.append("# note: dropped %d failure-shaped finding%s — the run "
                      "exited 0, so nothing failed (the %s extractor matched "
                      "output it does not own)"
                      % (dropped, "s"[: dropped != 1], ext_name))
    if log_error:
        header.append("# raw log: NOT written to %s (%s)" % log_error)
    elif log_path:
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
        return _degrade(header, problems, tail, max_tokens)
    return lines


def _degrade(header, problems, tail, max_tokens):
    """Over budget. ADR-004: the first problem in full, the rest one line
    each; then the first problem's detail shrinks from the bottom; then
    (ADR-006) the one-line list itself is cut. That last rung is what makes
    the ladder terminate: one line per problem is still O(problems), and a
    log with 300 warnings printed 300 lines against `--max-tokens 100`."""
    first, rest = problems[0], problems[1:]

    def assemble(keep_detail, listed):
        out = list(header) + ["", _one_line(first)]
        out += ["  " + d for d in first["detail"][:keep_detail]]
        if keep_detail < len(first["detail"]):
            out.append("  (… detail truncated)")
        if rest:
            out += [""] + [_one_line(p) for p in rest[:listed]]
            out.append("(… %d problem%s collapsed to one line each for "
                       "--max-tokens %d)"
                       % (len(rest), "s"[: len(rest) != 1], max_tokens))
            if listed < len(rest):
                out.append("(… %d of them not listed; the raw log has every "
                           "one — rerun with --full-log PATH)"
                           % (len(rest) - listed))
        if tail:
            # The generic extractor's tail is half its answer; losing it
            # unannounced reads as "the log ended here".
            out.append("(log tail dropped for --max-tokens %d)" % max_tokens)
        return out

    for keep in range(len(first["detail"]), -1, -1):
        lines = assemble(keep, len(rest))
        if _tokens_of(lines) <= max_tokens:
            return lines
    # Most one-liners that fit, hiding at least two: a "not listed" line
    # costs about what a single hidden one-liner does, so hiding one buys
    # nothing and loses its reference.
    lo, hi, best = 0, len(rest) - 2, None
    while lo <= hi:
        mid = (lo + hi) // 2
        cand = assemble(0, mid)
        if _tokens_of(cand) <= max_tokens:
            best, lo = cand, mid + 1
        else:
            hi = mid - 1
    if best is not None:
        return best
    return assemble(0, 0) if len(rest) >= 2 else assemble(0, len(rest))


# -------------------------------------------------------------------- traces
# `runlite trace` distills a stack trace that arrived from somewhere runlite
# did not run: a log file, CI output, a service, a paste. Same job as the
# extractors above (drop the noise, keep the path:line), different intake.
#
# A trace is {"lang": str, "sections": [section]}, where a section is
# {"kind": "raised"|"during handling of"|"direct cause of"|"caused by",
#  "header": str, "frames": [frame]} and a frame is
# {"ref": "path:line", "func": str, "project": bool}.
#
# Two normalizations make the output readable without knowing the language:
# frames are always innermost-first (the failure site leads), and chained
# exceptions are always propagated-first (what the caller actually saw
# leads). Python is the language that needs both reversed.

# Path fragments that mean "not this project's code", each with the label a
# collapsed run of them gets. Checked against the path lowercased with
# backslashes normalized to forward slashes.
_LIB_PATH = (
    ("site-packages", "site-packages"),
    ("dist-packages", "site-packages"),
    ("/lib/python", "python stdlib"),
    ("/lib64/python", "python stdlib"),
    ("/.pyenv/", "python stdlib"),
    ("node_modules", "node_modules"),
    ("/vendor/", "vendored"),
    ("/rustc/", "rust stdlib"),
    ("/library/std/", "rust stdlib"),
    ("/library/core/", "rust stdlib"),
    ("/library/alloc/", "rust stdlib"),
    ("/.rustup/", "rust stdlib"),
    (".cargo/registry", "crate"),
    ("/usr/local/go/src/", "go stdlib"),
    ("/go/pkg/mod/", "go module"),
)
# Synthetic frames: not files at all, never the caller's code.
_LIB_PREFIX = (
    ("node:", "node internal"),
    ("<frozen", "interpreter"),
    ("<string", "interpreter"),
    ("<built-in", "interpreter"),
)
# Package prefixes for languages whose frames name a package, not a path.
# ("internal/" is deliberately absent: Go projects use it for their own code.)
_LIB_PKG = (
    "java.", "javax.", "jdk.", "sun.", "com.sun.", "org.junit.",
    "org.gradle.", "org.apache.maven.", "org.testng.", "kotlin.", "scala.",
    "runtime.", "testing.", "core::", "std::", "alloc::", "rust_begin_unwind",
)


def _lib_label(path):
    """The label for a library frame, or "" if the path looks like project
    code."""
    p = (path or "").replace("\\", "/").lower()
    for frag, label in _LIB_PATH:
        if frag in p:
            return label
    for frag, label in _LIB_PREFIX:
        if p.startswith(frag):
            return label
    return ""


def _is_library(path, func):
    if _lib_label(path):
        return True
    f = (func or "").lstrip()
    return f.startswith(_LIB_PKG)


def _same_ref(a, b):
    """Two path:line refs pointing at the same place, allowing for the
    "./" and backslash spellings that differ within one trace."""
    def norm(r):
        r = r.replace("\\", "/")
        return r[2:] if r.startswith("./") else r
    return norm(a) == norm(b)


def _frame(path, line, func):
    return {"ref": "%s:%s" % (path, line), "func": (func or "").strip(),
            "project": not _is_library(path, func)}


def _section(kind, header, frames):
    return {"kind": kind, "header": header.strip(), "frames": frames}


# ---- python

_PY_START = re.compile(r"^Traceback \(most recent call last\):\s*$")
_PY_FRAME = re.compile(r'^\s+File "(.+?)", line (\d+)(?:, in (.+?))?\s*$')
_PY_DURING = "During handling of the above exception"
_PY_CAUSE = "The above exception was the direct cause"


def parse_python_trace(text):
    lines = text.splitlines()
    chains, pending = [], None   # pending: a relation marker since the last
    i = 0                        # block, or None
    while i < len(lines):
        if _PY_DURING in lines[i]:
            pending = "during handling of"
        elif _PY_CAUSE in lines[i]:
            pending = "direct cause of"
        elif _PY_START.match(lines[i]):
            frames = []
            j = i + 1
            while j < len(lines):
                m = _PY_FRAME.match(lines[j])
                if m:
                    frames.append(_frame(m.group(1), m.group(2), m.group(3)))
                elif lines[j].strip() and not lines[j][:1].isspace():
                    break  # unindented: the exception line ends the block
                j += 1
            header = lines[j].strip() if j < len(lines) else "(no exception line)"
            # Python prints outermost-first; lead with the failure site.
            frames.reverse()
            block = {"kind": pending or "raised", "header": header,
                     "frames": frames}
            if pending and chains:
                chains[-1].append(block)
            else:
                # Python writes a relation marker between the tracebacks of
                # one chain. Without one, this is a separate failure — two
                # errors hours apart in a service log used to fold into one
                # "chain", the later one presented as raised while handling
                # the earlier.
                chains.append([block])
            pending = None
            i = j
        i += 1
    traces = []
    for blocks in chains:
        # A marker sits between two exceptions and names the relation, so
        # it arrives attached to the *later* block ("B occurred during
        # handling of A"). Reading propagated-first, that phrase has to
        # label A, the block before it — hence the shift, then the reverse.
        # The last block in text order is the one that propagated and is
        # what "raised" belongs to.
        kinds = [b["kind"] for b in blocks]
        for k in range(len(blocks) - 1):
            blocks[k]["kind"] = kinds[k + 1]
        blocks[-1]["kind"] = "raised"
        blocks.reverse()
        traces.append({"lang": "python",
                       "sections": [_section(b["kind"], b["header"],
                                             b["frames"]) for b in blocks]})
    return traces


# ---- java / jvm

_JAVA_FRAME = re.compile(
    r"^\s+at ([\w$./<>]+)\(([^()]+?\.(?:java|kt|kts|scala|groovy)):(\d+)\)\s*$")
_JAVA_FRAME_NOSRC = re.compile(r"^\s+at ([\w$./<>]+)\((?:Native Method"
                               r"|Unknown Source)\)\s*$")
_JAVA_HEAD = re.compile(
    r"^(?:Exception in thread \"[^\"]*\" )?([\w$.]*(?:Exception|Error|Throwable)"
    r"(?::.*)?)\s*$")
_JAVA_CAUSE = re.compile(r"^Caused by:\s+(.+?)\s*$")
_JAVA_SUPPRESSED = re.compile(r"^\s+Suppressed:\s+(.+?)\s*$")
_JAVA_ELIDED = re.compile(r"^\s+\.\.\. \d+ (?:more|common frames omitted)\s*$")


def parse_java_trace(text):
    lines = text.splitlines()
    sections = []
    i = 0
    while i < len(lines):
        head, kind = None, None
        m = _JAVA_CAUSE.match(lines[i])
        if m:
            head, kind = m.group(1), "caused by"
        else:
            m = _JAVA_SUPPRESSED.match(lines[i])
            if m:
                head, kind = m.group(1), "suppressed"
            else:
                m = _JAVA_HEAD.match(lines[i])
                # A bare header only starts a trace if frames follow it.
                if m and i + 1 < len(lines) and (
                        _JAVA_FRAME.match(lines[i + 1])
                        or _JAVA_FRAME_NOSRC.match(lines[i + 1])):
                    head = m.group(1)
                    kind = "raised" if not sections else "caused by"
        if head is None:
            i += 1
            continue
        frames = []
        j = i + 1
        while j < len(lines):
            f = _JAVA_FRAME.match(lines[j])
            if f:
                frames.append(_frame(f.group(2), f.group(3), f.group(1)))
            elif _JAVA_FRAME_NOSRC.match(lines[j]) or _JAVA_ELIDED.match(lines[j]):
                pass  # no path:line to stand on; nothing to report
            else:
                break
            j += 1
        # JVM frames are already innermost-first, as are Caused-by chains.
        sections.append(_section(kind, head, frames))
        i = j
    if not sections:
        return []
    return [{"lang": "java", "sections": sections}]


# ---- node / javascript

_JS_FRAME = re.compile(
    r"^\s+at (?:(?:new |async )?(.+?) \()?([^()]+?):(\d+):\d+\)?\s*$")
_JS_HEAD = re.compile(r"^\s*(?:Uncaught )?([\w$.]*(?:Error|Exception)\b.*)$")


def parse_node_trace(text):
    lines = text.splitlines()
    sections = []
    i = 0
    while i < len(lines):
        if not _JS_FRAME.match(lines[i]):
            i += 1
            continue
        # Header is the nearest non-blank line above the frame run. Node
        # precedes it with a source echo and a caret line; those never
        # match _JS_HEAD, so an unrecognizable header degrades to a label
        # rather than to a source line masquerading as one.
        head = "(unlabeled stack)"
        k = i - 1
        while k >= 0 and not lines[k].strip():
            k -= 1
        if k >= 0:
            m = _JS_HEAD.match(lines[k])
            if m:
                head = m.group(1).strip()
        frames = []
        j = i
        while j < len(lines):
            f = _JS_FRAME.match(lines[j])
            if not f:
                break
            frames.append(_frame(f.group(2), f.group(3), f.group(1)))
            j += 1
        # V8 prints innermost-first already.
        sections.append(_section("raised" if not sections else "caused by",
                                 head, frames))
        i = j
    if not sections:
        return []
    return [{"lang": "node", "sections": sections}]


# ---- go

_GO_PANIC = re.compile(r"^(panic:|fatal error:)\s*(.*)$")
_GO_SIGNAL = re.compile(r"^\[signal .*\]$")
_GO_FUNC = re.compile(r"^(\S+\(.*\))$|^created by (\S+)")
_GO_LOC = re.compile(r"^\t(.+?):(\d+)(?: \+0x[0-9a-f]+)?\s*$")


def parse_go_trace(text):
    lines = text.splitlines()
    traces = []
    i = 0
    while i < len(lines):
        m = _GO_PANIC.match(lines[i])
        if not m:
            i += 1
            continue
        head = ("%s %s" % (m.group(1), m.group(2))).strip()
        frames = []
        j = i + 1
        if j < len(lines) and _GO_SIGNAL.match(lines[j].strip()):
            head += " " + lines[j].strip()
            j += 1
        while j < len(lines):
            if _GO_PANIC.match(lines[j]):
                break
            f = _GO_FUNC.match(lines[j])
            if f and j + 1 < len(lines):
                loc = _GO_LOC.match(lines[j + 1])
                if loc:
                    func = f.group(1) or f.group(2)
                    # Strip the argument dump: `main.work(0x14, 0x0)` names
                    # a function, the hex values say nothing.
                    func = func.split("(")[0]
                    frames.append(_frame(loc.group(1), loc.group(2), func))
                    j += 2
                    continue
            j += 1
        # Go prints the panicking goroutine innermost-first.
        traces.append({"lang": "go",
                       "sections": [_section("raised", head, frames)]})
        i = j
    return traces


# ---- rust

_RS_PANIC_NEW = re.compile(r"^thread '(.+?)' panicked at (.+?):(\d+):\d+:\s*$")
_RS_PANIC_OLD = re.compile(
    r"^thread '(.+?)' panicked at '(.*)', (.+?):(\d+):\d+\s*$")
_RS_FRAME = re.compile(r"^\s+\d+:\s+(.+?)\s*$")
_RS_AT = re.compile(r"^\s+at (.+?):(\d+)(?::\d+)?\s*$")


def parse_rust_trace(text):
    lines = text.splitlines()
    traces = []
    i = 0
    while i < len(lines):
        new = _RS_PANIC_NEW.match(lines[i])
        old = _RS_PANIC_OLD.match(lines[i])
        if not (new or old):
            i += 1
            continue
        if new:
            # 1.72+ puts the location on the panic line and the message next.
            site = _frame(new.group(2), new.group(3), "")
            msg = lines[i + 1].strip() if i + 1 < len(lines) else ""
            j = i + 2
        else:
            site = _frame(old.group(3), old.group(4), "")
            msg = old.group(2)
            j = i + 1
        head = "panicked: %s" % msg if msg else "panicked"
        frames = []
        while j < len(lines):
            if _RS_PANIC_NEW.match(lines[j]) or _RS_PANIC_OLD.match(lines[j]):
                break
            f = _RS_FRAME.match(lines[j])
            if f and j + 1 < len(lines):
                at = _RS_AT.match(lines[j + 1])
                if at:
                    frames.append(_frame(at.group(1), at.group(2), f.group(1)))
                    j += 2
                    continue
            j += 1
        # The panic site is the one frame always worth having; a trace with
        # RUST_BACKTRACE unset has nothing else at all. The backtrace spells
        # the same file "./src/calc.rs" where the panic line says
        # "src/calc.rs", so compare normalized or it lands twice.
        if not any(_same_ref(fr["ref"], site["ref"]) for fr in frames):
            frames.insert(0, site)
        traces.append({"lang": "rust",
                       "sections": [_section("raised", head, frames)]})
        i = j
    return traces


TRACE_PARSERS = [
    ("python", re.compile(r"^Traceback \(most recent call last\):\s*$", re.M),
     parse_python_trace),
    ("rust", re.compile(r"^thread '.+?' panicked at ", re.M),
     parse_rust_trace),
    ("go", re.compile(r"^(?:panic:|fatal error:).*\n(?:.*\n)?goroutine \d+ \[",
                      re.M), parse_go_trace),
    ("java", re.compile(r"^\s+at [\w$./<>]+\([^()]+?\.(?:java|kt|kts|scala"
                        r"|groovy):\d+\)\s*$", re.M), parse_java_trace),
    ("node", re.compile(r"^\s+at .*?:\d+:\d+\)?\s*$", re.M),
     parse_node_trace),
]


def detect_traces(text):
    """Return (lang, traces). Parsers are tried in order of their earliest
    fingerprint match, so a mixed log picks the trace that actually leads.
    A parser that fingerprints but yields nothing falls through to the next
    rather than reporting an empty result."""
    hits = []
    for rank, (name, fingerprint, parse) in enumerate(TRACE_PARSERS):
        m = fingerprint.search(text)
        if m:
            hits.append((m.start(), rank, name, parse))
    hits.sort()
    for _, _, name, parse in hits:
        traces = parse(text)
        if traces:
            return name, traces
    return "", []


# ---- frame selection

def select_frames(frames):
    """Keep every project frame and collapse each run of the rest.
    Returns a list of ("frame", frame) / ("collapsed", count, where) items.

    When no frame is this project's code, keep the innermost and outermost
    instead: an all-library trace still has to show where it entered and
    where it blew up rather than render as a bare exception line. The ends
    are *not* kept otherwise, because in Rust and Go the innermost frames
    are always panic machinery (`rust_begin_unwind`, `runtime.gopanic`) —
    leading with those buries the line that actually broke."""
    if not frames:
        return []
    keep = {i for i, f in enumerate(frames) if f["project"]}
    if not keep:
        keep = {0, len(frames) - 1}
    out, run = [], []
    for i, f in enumerate(frames):
        if i in keep:
            if run:
                out.append(("collapsed", len(run), _where(run)))
                run = []
            out.append(("frame", f))
        else:
            run.append(f)
    if run:
        out.append(("collapsed", len(run), _where(run)))
    return out


def _where(frames):
    """Shortest honest description of a collapsed run: the shared label if
    every frame in the run agrees on one, else the neutral "library"."""
    marks = {_lib_label(f["ref"].rsplit(":", 1)[0]) or "library"
             for f in frames}
    return marks.pop() if len(marks) == 1 else "library"


# ---- rendering

def _frame_line(f):
    return "  %s%s" % (f["ref"], "  in " + f["func"] if f["func"] else "")


def _trace_lines(trace, all_frames, limit=None):
    """Render one trace. `limit` caps the rendered items per section, the
    ladder's rung between "whole trace" and "one line per trace"; the cap
    keeps the innermost items, which are nearest the failure."""
    lines, shown = [], 0
    for n, sec in enumerate(trace["sections"]):
        prefix = "" if n == 0 else sec["kind"] + "  "
        lines.append(prefix + sec["header"])
        items = ([("frame", f) for f in sec["frames"]] if all_frames
                 else select_frames(sec["frames"]))
        cut = 0
        if limit is not None and len(items) > limit:
            cut = len(items) - limit
            items = items[:limit]
        for item in items:
            if item[0] == "frame":
                lines.append(_frame_line(item[1]))
                shown += 1
            else:
                lines.append("  … %d %s frame%s"
                             % (item[1], item[2], "s"[: item[1] != 1]))
        if cut:
            lines.append("  … %d outer frame%s" % (cut, "s"[: cut != 1]))
        if not sec["frames"]:
            lines.append("  (no frames with a file:line)")
    return lines, shown


def _trace_summary(trace):
    """One line per trace, for the over-budget rung: the propagated
    exception plus the innermost project frame that carries it."""
    sec = trace["sections"][0]
    ref = ""
    for f in sec["frames"]:
        if f["project"]:
            ref = "  " + f["ref"]
            break
    else:
        if sec["frames"]:
            ref = "  " + sec["frames"][0]["ref"]
    # A chained exception dropped without a word reads as one that never
    # happened; the count is two tokens and keeps the summary honest.
    rest = len(trace["sections"]) - 1
    chained = "  (+%d chained)" % rest if rest else ""
    return sec["header"] + ref + chained


def render_traces(lang, traces, all_frames, max_tokens, input_bytes):
    total = sum(len(s["frames"]) for t in traces for s in t["sections"])

    def assemble(limit, collapse_rest, note):
        lead = traces[:1] if collapse_rest else traces
        bodies, shown = [], 0
        for t in lead:
            body, n = _trace_lines(t, all_frames, limit)
            bodies.append(body)
            shown += n
        n = len(traces)
        frames = "%d frames" % total if total != 1 else "1 frame"
        seen = "" if shown == total else " → %d shown" % shown
        lines = ["# runlite trace: %s, %d trace%s, %s%s (innermost first)"
                 " [input %d B]"
                 % (lang, n, "s"[: n != 1], frames, seen, input_bytes)]
        if note:
            lines.append(note)
        for body in bodies:
            lines.append("")
            lines.extend(body)
        if collapse_rest and len(traces) > 1:
            lines.append("")
            lines.extend(_trace_summary(t) for t in traces[1:])
        return lines

    lines = assemble(None, False, "")
    if not max_tokens or _tokens_of(lines) <= max_tokens:
        return lines

    # Degradation ladder. Every rung is bounded, and every rung says so and
    # names the flag (ADR-005) — a trimmed trace that looked complete would
    # be read as "the caller's code appears nowhere in this stack".
    note = ("# note: trimmed to fit --max-tokens %d (raise it, or "
            "--max-tokens 0 for the whole trace)" % max_tokens)
    # 1. Trace #1 in full, the rest to one line each — ADR-004's rule, and
    #    trace #1 is the one that propagated.
    if len(traces) > 1:
        lines = assemble(None, True, note)
        if _tokens_of(lines) <= max_tokens:
            return lines
    # 2. Cap frames per section, innermost kept: the failure site is the
    #    last thing worth giving up.
    for limit in (6, 4, 3, 2, 1):
        lines = assemble(limit, True, note)
        if _tokens_of(lines) <= max_tokens:
            return lines
    # 3. Floor: every exception, each with the one path:line that carries
    #    it, never empty of references...
    head = ["# runlite trace: %s, %d trace%s, %s (summary only)"
            " [input %d B]"
            % (lang, len(traces), "s"[: len(traces) != 1],
               "%d frames" % total if total != 1 else "1 frame", input_bytes),
            note, ""]
    summaries = [_trace_summary(t) for t in traces]
    if _tokens_of(head + summaries) <= max_tokens:
        return head + summaries
    # ...and, since one line per trace is still O(traces) for a log that
    # holds thousands, the head of that list plus a count. Trace #1, the
    # one that propagated, always stays.
    def more(n):
        return "(… %d more trace%s not listed for --max-tokens %d)" % (
            n, "s"[: n != 1], max_tokens)

    used, k = sum(len(l) + 1 for l in head), 0
    for line in summaries:
        cost = len(line) + 1 + len(more(len(summaries) - k - 1)) + 1
        if k and (used + cost) // 4 > max_tokens:
            break
        used += len(line) + 1
        k += 1
    if len(summaries) - k < 2:
        # A count line costs about what the one summary it would hide does;
        # hiding a single trace buys nothing and loses its reference.
        return head + summaries
    return head + summaries[:k] + [more(len(summaries) - k)]


def _read_trace_input(path):
    """Return (text, bytes) or raise OSError."""
    if not path or path == "-":
        data = sys.stdin.buffer.read()
    else:
        with open(path, "rb") as fh:
            data = fh.read()
    return data.decode("utf-8", errors="replace"), len(data)


def main_trace(argv):
    parser = argparse.ArgumentParser(
        prog="runlite trace",
        description="distill a stack trace read from a file or stdin",
        usage="runlite trace [options] [FILE]")
    parser.add_argument("path", nargs="?", default="-", metavar="FILE",
                        help="trace file, or - / omitted for stdin")
    parser.add_argument("--max-tokens", type=int, metavar="N", default=0,
                        help="over budget: first trace full, rest one line")
    parser.add_argument("--all-frames", action="store_true",
                        help="do not collapse runs of library frames")
    args = parser.parse_args(argv)

    try:
        text, nbytes = _read_trace_input(args.path)
    except OSError as exc:
        print("runlite: %s" % exc, file=sys.stderr)
        return EXIT_INTERNAL

    lang, traces = detect_traces(text)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    if not traces:
        # Distinguishable from "distilled a trace", and never silent: the
        # caller needs to know the input was not understood, not assume it
        # held nothing worth reporting.
        print("# runlite trace: no recognized stack trace [input %d B]"
              % nbytes)
        return EXIT_NO_TRACE
    print("\n".join(render_traces(lang, traces, args.all_frames,
                                  args.max_tokens, nbytes)))
    return 0


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
    try:  # error text carries the same non-ASCII punctuation as output;
        # a cp1252 console default turns it into invalid UTF-8 bytes
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    argv = sys.argv[1:] if argv is None else list(argv)
    # Checked before option splitting so `trace` is a subcommand, not a
    # command to wrap; `runlite -- trace ...` still wraps a program named
    # trace.
    if argv and argv[0] == "trace":
        return main_trace(argv[1:])
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

    log_error = None
    if args.full_log:
        # The command has already run: a bad log path must cost the log,
        # never the report. Raising here threw a traceback, exited 1 instead
        # of the command's code, and lost the result of a build that might
        # have taken minutes.
        try:
            parent = os.path.dirname(args.full_log)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(args.full_log, "wb") as fh:
                fh.write(raw)
        except OSError as exc:
            log_error = (args.full_log, exc.strerror or str(exc))
            print("runlite: could not write --full-log %s: %s" % log_error,
                  file=sys.stderr)

    ext = detect(cmd, log)
    problems, tail = ext.parse(log)
    if proc.returncode != 0 and not problems and not tail:
        # The named extractor parsed nothing from a failing run (e.g. the
        # test framework itself is missing); never report less than the log.
        problems, tail = parse_generic(log)
    lines = render(proc.returncode, wall, ext.name, problems, tail,
                   args.max_tokens, args.full_log, len(raw), log_error)
    try:  # tool logs carry symbols (✕, ●, ⎯) a cp1252 console default would eat
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    print("\n".join(lines))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
