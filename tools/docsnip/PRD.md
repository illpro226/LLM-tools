# docsnip PRD

## Problem statement

When an agent needs the signature and behavior of a library symbol, it either web-searches (slow, often version-mismatched) or reads entire vendored sources (token-expensive). The correct answer is already installed locally. `docsnip` extracts just the relevant signature, docstring, and source location from installed packages.

## Target users

- Coding agents answering "what's the signature and behavior of X from library Y".
- Humans wanting quick, version-accurate API lookups without leaving the terminal.

## Scope

### Core behavior

- `docsnip requests.Session.request` — resolve a Python symbol via importlib + inspect, obtaining the real signature and docstring, avoiding execution of arbitrary code where possible.
- `docsnip --npm express Router` — resolve a Node symbol via `node_modules`, preferring `.d.ts` type definitions for extraction.
- Output per symbol: full signature, parameter list with types, docstring/JSDoc, and definition location (`path:line`).
- `docsnip --readme PACKAGE --section usage` — extract one section of a package README.

### Behavior details

- Cache extraction results in `~/.cache/docsnip/`, keyed by package version.
- `--max-tokens N` caps output; degrade by trimming docstring detail before removing signature/parameter data.
- "Not installed" and "symbol not found" produce short, actionable errors (e.g. suggesting the install command or near-miss symbol names).

## Non-goals

- Fetching documentation from the web or package registries.
- Rendering full API reference docs for a whole package.
- Executing package code to introspect runtime-only attributes.

## Acceptance criteria

- Python: a symbol query against a fixture virtualenv returns the correct signature, parameters, docstring, and `path:line`.
- Node: a query against a fixture `node_modules` prefers `.d.ts` sources and returns typed signatures.
- Nested symbol paths (`module.Class.method`) resolve correctly.
- `--readme --section` returns exactly the requested README section.
- A second identical query hits the cache (verified by test); a package version bump invalidates it.
- Missing package and missing symbol each produce their distinct short error and nonzero exit.
- `--max-tokens` keeps output within budget.
