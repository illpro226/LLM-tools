# repomap ranks test fixtures above the package they test

**STATUS: open.** Filed 2026-10-08 from a full-suite review session
(dogfooding friction, not a crash).

## What broke

Orienting in repoindex before reviewing it:

```
$ repomap tools/repoindex --max-tokens 1200
tools/repoindex/tests/fixtures/repo/py/mathutil.py  [refs 30]
tools/repoindex/tests/fixtures/repo/js/mathutil.js  [refs 29]
tools/repoindex/tests/fixtures/repo/js/shapes.ts  [refs 26]
...
(… 20 lower-ranked file outlines dropped for --max-tokens 1200)
```

Every outline that fit was a test fixture. `repoindex/extract.py`, `cli.py`,
`resolve.py` and `db.py`, which hold the code, were among the dropped 20.
The tree also listed every fixture file, which spent the budget on paths
under `tests/fixtures/`. `xread --headings` on the four modules was the
call that actually answered "what is in this package".

## Why

The ranker scores a file by how many other files mention its stem and its
top-level names. Fixture sets are small, mirrored, name-sharing families
(`mathutil.py` / `mathutil.js` / `mathutil.go` / `test_mathutil.py`, each
with `add`), so they mention each other far more often than production
modules get mentioned. Nothing weights by path class. sgrep already has
src > tests > generated weights for this reason.

## What changed

Not fixed. Expected: apply sgrep's path classes (tests/fixtures/testdata at
reduced weight) to repomap's score, and collapse `tests/fixtures/`-style
subtrees in the tree under a budget before collapsing source directories.
