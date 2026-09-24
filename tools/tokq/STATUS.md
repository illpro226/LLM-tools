# tokq Status

Implemented (v0.1.2) and passing tests.

- `tokq.py` — single-file CLI covering all PRD modes: meter (files/stdin),
  `dir` (token-weighted tree), `lint` (+ `--budget` gate).
- Estimator: tiktoken o200k_base when importable, bytes/3.7 fallback; the
  method is stated once per run. Binary content is flagged and size-estimated.
- `--max-tokens` elides rows, never the summary: the total, the finding
  count and every `BUDGET EXCEEDED` verdict always print. `lint` reports a
  missing path on stderr and lints the rest (exit 2).
- Tests: `tests/test_tokq.py` (30 tests) against committed fixtures in
  `tests/fixtures/`; both estimator paths exercised (tiktoken test skips when
  the package is absent). Fallback startup measured under the 100 ms budget.

Not done / later: no packaging or PATH install story yet (run `./tokq.py` or
symlink it); lint rule table could grow (e.g. generated-code markers).
