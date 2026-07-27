# repomap Architecture

Status: implemented (v0.1.0) as a single stdlib-only file, `repomap.py`.

## Overview

`repomap` is a pipeline: walk → extract → rank → render → reduce. Each stage is a
pure function over the previous stage's data, so the token-budget reducer can
re-run the render stage with progressively cheaper settings.

```
scan(dir) ──► tree + source files (with symbols and identifier sets)
rank(files) ──► ordered by reference count, ties by path
_render(ctx, stage, k, depth) ──► text lines
build_output(ctx) ──► re-render at lower detail until within budget
```

## Components

- **Walker / tree pruner** (`scan`) — walks the directory applying a built-in
  skip list (`node_modules`, `dist`, `build`, `target`, `__pycache__`, …), a
  skip of dot-directories (except `.github`), and a simple subset of the root
  `.gitignore` (names, globs, `dir/` patterns; no negation, no nested files).
  Produces both the nested tree and the source-file records in one pass.
- **Symbol extractors** — one per language family, chosen by extension in
  `extractor_for` (see DECISIONS.md ADR-004 for why not tree-sitter): Python
  via stdlib `ast`; JS/TS and C/C++ via depth-tracking line scanners over
  string/comment-stripped code; Go and Rust via column-0 declaration
  patterns; a generic declaration regex for everything else. Each yields
  top-level symbols only: kind, name, line, cleaned one-line signature, and
  docstring/comment first line.
- **Ranker** (`rank`) — scores each file by how often its stem and top-level
  symbol names occur as identifiers in the repo's other source files
  (stem hit = 2, each symbol name = 1). Deterministic: ties break by path.
  This function is the seam where `.repoindex/index.db`-backed scoring will
  slot in once repoindex pins its schema (ADR-005).
- **Renderer** (`_render`) — header, pruned tree, then per-file outline
  blocks in rank order. Detail per file is `full` (signature + doc line) or
  `names` (kind + name), or `summary` (the header line alone, with a symbol
  count). `--focus PATH` puts the subtree's files first at full detail, drops
  every other file to `summary`, and collapses unrelated tree branches below
  depth 2 — it narrows, it does not merely rank (ADR-006). Runs of three or
  more `test_*` functions collapse to one counted line in any mode.
- **Budget reducer** (`build_output`) — estimates tokens as bytes/4 and
  degrades in whole levels, never mid-entry: first collapses deep tree
  levels until the tree costs at most half the budget, then binary-searches
  the number of full-detail outlines kept (floor 5), then names-only
  outlines (floor 1), then tree-only with shrinking depth. Every reduction
  is announced in a trailing note.

## Key decisions

- Language: Python, stdlib only (ADR-004; supersedes the tree-sitter plan).
- Standalone-first: no index required; index-backed ranking deferred (ADR-005).
- Deterministic output: rank ties break by path sort so runs are stable.

## Dependencies

Stdlib only.
