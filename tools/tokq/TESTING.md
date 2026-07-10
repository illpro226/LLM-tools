# tokq Testing

Fixture-based, per repo conventions (AGENTS.md). Both estimator paths
(tiktoken and fallback) are exercised explicitly — tests patch tiktoken out to
force the fallback.

## Fixtures

- `tests/fixtures/` — plain-text files of known byte sizes; a lockfile
  (`package-lock.json`), a minified single-long-line JS file, a high-entropy
  blob, a binary-ish file with NUL bytes; a small directory tree with known
  per-subtree weights.

## Test areas

- **Estimator** — with tiktoken available: real counts, header says
  tokenizer; with tiktoken import-blocked: bytes/3.7 estimates, header says
  heuristic. Never silently mixed within a run.
- **Meter** — per-file values and total for file args; stdin path via piped
  input; binary-ish content flagged and size-estimated.
- **dir** — heaviest-first ordering with cumulative percentages; skip-list
  pruning applied; deterministic across runs.
- **lint** — each fixture triggers its rule: size threshold, lockfile name
  pattern, minified long-line ratio, entropy; each finding carries the right
  cheaper-tool suggestion (`structo` / `xread` / `repomap`).
- **Budget gate** — `lint --budget N` exits nonzero when exceeded, zero
  otherwise; boundary value tested.
- **Startup** — fallback-path startup measured under 100 ms (marked test,
  generous CI multiplier documented in-line).

## Running

`python -m pytest` from `tools/tokq/`.
