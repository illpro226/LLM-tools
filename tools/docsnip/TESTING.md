# docsnip Testing

Fixture-based, per repo conventions (AGENTS.md). The PRD requires a fixture
virtualenv and a fixture `node_modules` — small purpose-built packages, not
real-world installs, so tests are hermetic.

## Fixtures

- `tests/fixtures/venv/` — a tiny installed Python package with: a module
  function (defaults + annotations), a class with methods (nested resolution),
  docstrings, and a version marker for cache-invalidation tests.
- `tests/fixtures/node_modules/` — a tiny package with `package.json`
  `types` field, `.d.ts` declarations, and JSDoc-only source for the fallback.
- READMEs with multiple headed sections in both packages.

## Test areas

- **Python backend** — signature (with defaults/annotations), parameter table,
  docstring, and `path:line` correct for module- and class-level symbols;
  static extraction path taken where possible (import spy asserts no
  unnecessary import).
- **npm backend** — `.d.ts` preferred when present; JSDoc fallback engages
  when it is not; typed signatures correct.
- **README extraction** — `--readme --section usage` returns exactly that
  section's content; unknown section errors shortly.
- **Cache** — second identical query served from `~/.cache/docsnip/`
  (extraction spy not called); bumping the fixture package version
  invalidates; cache dir override respected in tests.
- **Errors** — not-installed vs symbol-not-found produce distinct short
  messages and nonzero exits; near-miss suggestion appears for a typo query.
- **Token cap** — signature and parameter table survive every budget;
  docstring trims paragraph-by-paragraph.

## Running

`python -m pytest` from `tools/docsnip/`.
