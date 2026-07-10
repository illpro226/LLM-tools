# docsnip Roadmap

## M1 — Scaffold and Python backend

- CLI entry point; fixture virtualenv for tests.
- Python symbol resolution (nested paths), static-first signature/docstring
  extraction with `path:line`.
- Distinct not-installed / symbol-not-found errors.

## M2 — npm backend

- Fixture `node_modules`; resolution via package.json types field.
- `.d.ts`-preferred extraction with JSDoc fallback.

## M3 — README and cache

- `--readme PACKAGE --section NAME` heading extraction.
- `~/.cache/docsnip/` version-keyed cache; hit/invalidation tests.

## M4 — Budget and polish

- `--max-tokens N` (docstring trims first, signature survives).
- Near-miss suggestions for symbol typos.

## Later

- Additional ecosystems (Go modules, cargo docs) if demand appears.
