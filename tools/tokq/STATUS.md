# tokq Status

Implemented (v0.1.0) and passing tests.

- `tokq.py` — single-file CLI covering all PRD modes: meter (files/stdin),
  `dir` (token-weighted tree), `lint` (+ `--budget` gate).
- Estimator: tiktoken o200k_base when importable, bytes/3.7 fallback; the
  method is stated once per run. Binary content is flagged and size-estimated.
- Tests: `tests/test_tokq.py` (24 tests) against committed fixtures in
  `tests/fixtures/`; both estimator paths exercised (tiktoken test skips when
  the package is absent). Fallback startup measured under the 100 ms budget.

Not done / later: no packaging or PATH install story yet (run `./tokq.py` or
symlink it); lint rule table could grow (e.g. generated-code markers).
