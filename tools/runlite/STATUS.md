# runlite Status

Implemented (v0.1.2) and passing tests.

- `runlite.py` — single-file CLI covering all PRD modes: run + distilled
  report (exit code, wall time, problems with `file:line`), `--max-tokens`
  budget (first problem full, rest one line each), `--full-log PATH` raw-log
  export.
- Extractors: pytest, go test, cargo (compile errors + test panics), tsc,
  eslint, jest/vitest, gcc/clang, generic fallback (error-pattern lines +
  last 20). Detection: command name, then log fingerprint, then generic.
- Exit codes: passthrough of the wrapped command; reserved 125 (runlite
  internal) and 127 (command not found).
- Windows: argv[0] resolves through `shutil.which` (PATHEXT-aware) so
  `.cmd`/`.bat` shims (`npx`, `tsc`) spawn instead of exiting 127.
- Tests: `tests/test_runlite.py` (30 tests) against canned logs in
  `tests/fixtures/logs/`; no real toolchains required.

Not done / later: no packaging or PATH install story yet (run `./runlite.py`
or symlink it); no timeout handling; no `--json` report.
