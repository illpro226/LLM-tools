# runlite Status

Implemented (v0.4.0) and passing tests.

- `runlite.py` — single-file CLI covering all PRD modes: run + distilled
  report (exit code, wall time, problems with `file:line`), `--max-tokens`
  budget (first problem full, rest one line each), `--full-log PATH` raw-log
  export.
- Extractors: pytest, go test, cargo (compile errors + test panics), tsc,
  eslint, jest/vitest, gcc/clang, next build, generic fallback
  (error-pattern lines + last 20). Detection: command name, then log
  fingerprint, then generic.
- A zero exit suppresses `FAIL`-titled findings (and says which extractor
  produced them): the exit code outranks anything pattern-matched out of
  the log.
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
  distilled, 1 no recognizable trace, 125 internal. Unbounded by default;
  `--max-tokens` degrades to a summary line per exception, never below one
  `path:line` each.
- Known limit: JVM library detection is package-prefix based (JDK, test
  runners, build tools only), so third-party framework frames read as
  project frames — deliberate, see ADR-005.
- Tests: `tests/test_runlite.py` (36) against canned logs in
  `tests/fixtures/logs/`, `tests/test_runlite_trace.py` (40) against canned
  traces in `tests/fixtures/traces/`; 76 total, no real toolchains needed.

Not done / later: no packaging or PATH install story yet (run `./runlite.py`
or symlink it); no timeout handling; no `--json` report.
