#!/usr/bin/env python3
"""Run every live tool's test suite and state the result in one screen.

    python scripts/test_all.py              the nine tools, in parallel
    python scripts/test_all.py --archived   also archive/rq, archive/testmap
    python scripts/test_all.py xread sgrep  just these

One line per tool (counts from pytest's own summary), then the failing
test ids of any tool that failed, then a verdict line. Exit 0 only when
every suite passed. Stdlib only; each suite runs in its own directory, as
AGENTS.md documents (`cd tools/<name> && python -m pytest`).
"""

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = ("tokq", "runlite", "xread", "sgrep", "repomap", "gitbrief",
         "structo", "repoindex", "codediff")
ARCHIVED = ("rq", "testmap")
_COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed)")


def _suite_dir(name):
    for base in ("tools", "archive"):
        path = os.path.join(ROOT, base, name)
        if os.path.isdir(path):
            return path
    return None


def run_suite(name):
    """(name, ok, counts, failures, seconds)."""
    path = _suite_dir(name)
    if path is None:
        return name, False, {}, ["no such tool: %s" % name], 0.0
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"],
        cwd=path, capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    seconds = time.monotonic() - start
    lines = [l for l in proc.stdout.splitlines() if l.strip()]
    counts = {}
    for n, kind in _COUNT.findall(lines[-1] if lines else ""):
        counts[kind.rstrip("s") if kind.startswith("error") else kind] = int(n)
    failures = [l for l in lines if l.startswith(("FAILED ", "ERROR "))]
    if proc.returncode != 0 and not failures:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-5:]
        failures = tail or ["pytest exited %d" % proc.returncode]
    return name, proc.returncode == 0, counts, failures, seconds


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(
        prog="test_all", description="run every tool's pytest suite")
    parser.add_argument("tools", nargs="*", metavar="TOOL",
                        help="subset to run (default: the nine live tools)")
    parser.add_argument("--archived", action="store_true",
                        help="also run archive/rq and archive/testmap")
    parser.add_argument("--serial", action="store_true",
                        help="one suite at a time (default: in parallel)")
    args = parser.parse_args(argv)

    names = list(args.tools or TOOLS) + (list(ARCHIVED) if args.archived
                                         else [])
    start = time.monotonic()
    workers = 1 if args.serial else len(names)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run_suite, names))

    width = max(len(n) for n in names)
    total = 0
    for name, ok, counts, _, seconds in results:
        total += counts.get("passed", 0)
        summary = ", ".join("%d %s" % (n, k) for k, n in counts.items())
        print("%-*s  %-4s  %-28s %6.1fs" % (width, name,
                                             "ok" if ok else "FAIL",
                                             summary or "(no summary)",
                                             seconds))
    failed = [r for r in results if not r[1]]
    for name, _, _, failures, _ in failed:
        print("")
        print("%s:" % name)
        for line in failures:
            print("  " + line)
    print("")
    wall = time.monotonic() - start
    if failed:
        print("%d of %d suites FAILED (%s) in %.0fs"
              % (len(failed), len(results),
                 ", ".join(r[0] for r in failed), wall))
        return 1
    print("all %d suites pass (%d tests) in %.0fs"
          % (len(results), total, wall))
    return 0


if __name__ == "__main__":
    sys.exit(main())
