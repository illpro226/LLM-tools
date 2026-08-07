# runlite Changelog

- 2026-08-07: v0.4.0 — `runlite trace [FILE]` (or stdin) distills a stack
  trace runlite did not produce: one that arrived from a log file, CI, a
  service, a paste. Python, Java/JVM, Node, Go and Rust, parsed to the
  exception plus the frames that are this project's code, with runs of
  library frames collapsed to `… 4 site-packages frames`. Two
  normalizations make the output readable without knowing the language:
  frames are always innermost-first, and chained exceptions
  (`Caused by:`, `During handling of…`) are always propagated-first —
  Python needs both reversed. Keeping the innermost frame unconditionally
  turned out to be wrong for Rust and Go, whose frame 0 is always unwind
  machinery (`rust_begin_unwind`, `runtime.gopanic`), so the ends are kept
  only when no frame is project code at all. Exits 0 when it distilled a
  trace, 1 when the input held none (never silently), 125 on its own
  failure. Unbounded by default like the rest of runlite (ADR 0005);
  `--max-tokens` ladders trace-#1-full → per-section frame caps → a
  summary line per trace, every rung naming the flag and keeping at least
  one `path:line` per exception. `--all-frames` opts out of collapsing.
  40 new tests in `tests/test_runlite_trace.py` (76 total). See ADR-005.
- 2026-08-06: v0.3.0 — the header reports the size of the log the report
  stands in for: `# runlite: exit 1 in 12.4s (pytest) 3 problems
  [log 128431 B]`. Two reasons, one for each reader. For the caller, a
  four-line report over a 400 KB log is a different claim than the same
  four lines over 900 B — the figure says how much was suppressed rather
  than absent. For the savings hook, it is the only honest baseline
  available: runlite already buffers the whole log, so the number is exact
  rather than estimated, and the alternative (re-running the build to
  measure it) is slow, side-effecting and not even deterministic. runlite
  had logged 180 calls with no credited savings at all before this.
  `render()` omits the field when the size was not measured, so an
  unmeasured run never prints as an empty log. 2 new tests (36 total).
- 2026-08-06: v0.2.0 — a run that exited 0 never reports failure-shaped
  findings, and a `next build` extractor. `next build` ends every
  successful build with a route-type legend (`●  (SSG) …`) that trips the
  jest/vitest bullet fingerprint, so three green builds in a row reported
  `exit 0 … 1 problem / FAIL (SSG)` — a headline and a body saying opposite
  things, with the body the one a reader believes. Two guards, because
  either alone leaves the class open: the new extractor claims Next.js logs
  before jest/vitest sees them (and still surfaces real `Failed to
  compile.` / `Type error:` blocks, with the path Next prints on the line
  above), and `render` now drops `FAIL`-titled problems on a zero exit,
  naming the misfiring extractor rather than hiding it. 4 new tests
  (34 total). Closes
  docs/known-issues/archive/runlite-next-build-legend-read-as-failure.md.
- 2026-07-31: stderr pinned to UTF-8 at entry alongside stdout. Error messages
  carry the same non-ASCII punctuation as normal output (em dashes,
  ellipses, arrows); on a cp1252 console they reached the caller as
  invalid UTF-8 bytes. stdout was already pinned, but always after the
  error path had already printed.
- 2026-07-27: v0.1.3 — stdout pinned to UTF-8 so log symbols (✕, ●, ⎯)
  survive a cp1252 console instead of degrading to `?`.
- 2026-07-19: v0.1.2 — a failing run whose extractor parses nothing (e.g.
  `pytest` selected by command name but the framework itself missing) now
  falls back to the generic extractor so the log tail always appears, and
  the header says "no findings (see log tail)" instead of "no problems"
  on nonzero exits (fixes known-issue
  `runlite-pytest-extractor-swallows-missing-module`). 29 tests.

- 2026-07-17: v0.1.1 — Windows: resolve the wrapped command's argv[0]
  through `shutil.which` (PATHEXT-aware) before spawning, so `.cmd`/`.bat`
  shims like `npx`/`tsc` launch instead of exiting 127; detection and the
  not-found message keep the command as typed (fixes known-issue
  `runlite-npx-not-found-windows`). 27 tests.

- 2026-07-07: v0.1.0 — initial implementation: runner with exit-code
  passthrough, extractor registry (pytest, jest/vitest, go test, cargo, tsc,
  eslint, gcc/clang, generic fallback), `--max-tokens` budget rule,
  `--full-log` raw-log export; 25 fixture-based tests.
- 2026-07-06: Added initial documentation scaffold.
