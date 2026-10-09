# runlite Status

Implemented (v0.6.0) and passing tests.

- `runlite.py` — single-file CLI covering all PRD modes: run + distilled
  report (exit code, wall time, problems with `file:line`), `--max-tokens`
  budget, default 2000 (docs/decisions/0011) (first problem full, rest one line each, then the list itself cut
  and counted — ADR-006), `--full-log PATH` raw-log export (a path that
  cannot be written costs the log, never the report or the exit code).
- Extractors: pytest, go test, cargo (compile errors + test panics), tsc,
  eslint, jest/vitest, gcc/clang, next build, generic fallback
  (error-pattern lines + last 20). Detection: command name, then log
  fingerprint, then generic.
- A zero exit suppresses `FAIL`-titled findings (and says which extractor
  produced them): the exit code outranks anything pattern-matched out of
  the log. The generic extractor reports no problems at all on exit 0,
  only a count of lines mentioning a warning.
- The header reports the exact size of the log the report replaced
  (`[log N B]`), from the buffer runlite already holds; omitted when the
  size was not measured, so an unmeasured run never reads as an empty log.
- Exit codes: passthrough of the wrapped command; reserved 125 (runlite
  internal) and 127 (command not found).
- Windows: argv[0] resolves through `shutil.which` (PATHEXT-aware) so
  `.cmd`/`.bat` shims (`npx`, `tsc`) spawn instead of exiting 127.
- `runlite trace [FILE]` (ADR-005) — same job for a trace runlite did not
  produce, read from a file or stdin. Python, Java/JVM, Node, Go, Rust.
  Output is the exception plus this project's frames, with library runs
  collapsed (`… 4 site-packages frames`); `--all-frames` opts out.
  Frames are always innermost-first and chained exceptions
  propagated-first, regardless of how the language prints them. Exit 0
  distilled, 1 no recognizable trace, 125 internal. `--max-tokens`
  (default 2000) degrades to a summary line per exception, never below one
  `path:line` each, and past that to the head of that list plus a count.
  Traces chain only across an explicit marker (Python `During handling…`/
  `direct cause`, Java `Caused by:`/`Suppressed:`, Node `[cause]:`);
  unrelated errors in one log are separate traces. Python exception groups
  list each sub-exception as an `in group` section, nested groups included.
- Known limit: JVM library detection is package-prefix based (JDK, test
  runners, build tools only), so third-party framework frames read as
  project frames — deliberate, see ADR-005.
- Tests: `tests/test_runlite.py` (43) against canned logs in
  `tests/fixtures/logs/`, `tests/test_runlite_trace.py` (48) against canned
  traces in `tests/fixtures/traces/`; 91 total, no real toolchains needed.

Not done / later: no packaging or PATH install story yet (run `./runlite.py`
or symlink it); no timeout handling; no `--json` report.
