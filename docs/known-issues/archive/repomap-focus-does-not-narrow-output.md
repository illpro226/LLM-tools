# repomap --focus ranks but does not narrow

**RESOLVED 2026-07-27 (repomap v0.2.0, ADR-006).** `--focus PATH` now
collapses every file outside the focus to `path [refs N] (K symbols)` plus a
note saying how to get the outlines back. Independently, a run of three or
more consecutive `test_*` functions collapses to one counted line in any
mode — the partial mitigation the issue suggested. The flag name was kept:
narrowing is what "focus" reads as, so the behavior was the mismatch.

**STATUS at filing: open.**

**Date:** 2026-07-27
**Tool:** `repomap` 0.1.0
**Status:** Open

## What I tried

I wanted the symbol outline of one file — `toch/cli.py` in
`G:\DataExtremes\Code\TOCH_SS` — to plan where to patch in two new
subcommands. `xread --headings` correctly refused (markdown only) and
pointed me at `repomap`, so:

```
repomap . --focus toch/cli.py
```

Got back the full directory tree plus the symbol table for **every** ranked
file in the repo: all 24 functions in `toch/cli.py` (what I wanted), then
`resolver.py`, `storage.py`, `server.py`, `models.py`, the v2 modules, and
then every individual test function across all four test files —
`test_parse_duration_days`, `test_rotate_key_creates_backup`, and ~90 more.
Roughly 180 lines for a question about one file.

`--focus` did do something: `toch/cli.py` was ranked first and annotated
`[refs 28]`. But nothing else was suppressed.

## Expected

`--focus PATH` reads as "narrow to this", not "sort by this". I'd expect it
to emit the focused file's outline plus its immediate neighbours (callers
and callees), and drop the long tail — or at minimum collapse unfocused
files to a one-line `path [refs N] (12 symbols)` summary that can be
expanded on request.

If the current behavior is the intended design, the flag is misnamed; `--rank-by`
or `--prioritize` would set the right expectation, and `--only` could cover
the narrowing case.

## Impact / workaround

For this query the tool was almost certainly *more* expensive than the
built-in it replaces — reading the `def` lines out of one 465-line file
directly would have cost less than 180 lines of whole-repo symbol table.
That inverts the suite's core value proposition, and it happens precisely on
the "orient me on one file" question that `repomap` is the recommended
answer for.

Test files dominate the tail because each test function is a top-level `def`.
A repo with a large suite makes this much worse than the ~40/60 split seen
here. A cheap partial mitigation independent of `--focus`: collapse
consecutive `test_*` symbols in a single file to a count.

Workaround: use `repomap` for genuine orientation (first pass on an unfamiliar
repo) and a bounded `Read` with `offset`/`limit` when the target file is
already known.
