# docsnip Architecture

Status: planned — no implementation exists yet. This describes the intended design.

## Overview

`docsnip` resolves a symbol query to an installed package, extracts signature +
docs via an ecosystem-specific backend, and serves results through a
version-keyed cache.

```
query ──► backend (python | npm) ──► locate package
cache lookup (package@version, symbol) ──► hit? render : extract
extract ──► {signature, params, doc, path:line} ──► cache ──► render(budget)
```

## Components

- **Python backend** — resolves `pkg.mod.Class.method` by walking importlib
  metadata and module files. Prefers static extraction (parse the source with
  `ast`/`inspect.getsource` semantics) over importing, importing a module only
  when static resolution fails and never executing beyond import. Yields the
  real signature (with defaults/annotations), parameter table, docstring, and
  definition `path:line`.
- **npm backend** — resolves via `node_modules` package.json (`types`/`typings`
  field first), extracts from `.d.ts` declarations preferentially, falling back
  to JSDoc in source. Yields typed signature, params, JSDoc, `path:line`.
- **README extractor** — `--readme PACKAGE --section NAME` locates the installed
  package's README and returns the named heading's section only.
- **Cache** — `~/.cache/docsnip/` keyed by `(ecosystem, package, version,
  query)`; version comes from installed metadata so upgrades invalidate
  naturally. Cache entries are the rendered-model JSON, not raw source.
- **Error surface** — distinct short messages for "package not installed"
  (with the likely install command) and "symbol not found" (with near-miss
  suggestions from the package's symbol table).
- **Renderer / budget** — signature and params always survive `--max-tokens N`;
  docstring body is trimmed paragraph-by-paragraph first.

## Key decisions

- Language: Python; the npm backend parses `.d.ts` with tree-sitter's TypeScript
  grammar rather than embedding a TS toolchain.
- Static-first extraction is a safety and speed decision: avoid running package
  code where possible.
- Backends share one output model so the renderer and cache are ecosystem-blind.

## Dependencies

Stdlib + `tree-sitter` (TypeScript grammar) for the npm backend.
