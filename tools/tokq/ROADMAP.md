# tokq Roadmap

`tokq` is the suite's suggested first build — it measures the savings of
everything else.

## M1 — Estimator and meter

- Estimator with lazy tiktoken + bytes/3.7 fallback, method noted in output.
- `tokq FILE...` and stdin metering; startup-time budget test (<100 ms fallback).

## M2 — Directory tree

- `tokq dir PATH` du-style token tree, heaviest-first, with skip-list pruning.

## M3 — Lint

- Rule table: size threshold, lockfile/minified/generated patterns,
  long-line/entropy heuristics; cheaper-tool suggestions per finding.
- `--budget N` nonzero-exit gating.

## M4 — Hardening

- Binary-content flagging; deterministic ordering; fixture tests for
  estimates, thresholds, suggestions, and exit codes.

## Later

- Per-model encodings if agents need them; badge/summary output for CI.
