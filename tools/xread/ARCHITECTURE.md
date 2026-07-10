# xread Architecture

Status: implemented (v0.1.0) in `xread.py`. The pipeline below matches the
implementation; one planned choice changed: parsing is stdlib-based, not
tree-sitter (see ADR-004 in DECISIONS.md), and a markdown mode was added per
repo ADR-0001 (headings as a symbol kind: `--headings` outline plus
heading-based section extraction through `--symbol`).

## Overview

Three modes share one pipeline: resolve a set of *regions* in each file, then hand
them to a common renderer that merges overlaps, adds citable headers, inserts
elision markers, and enforces the token cap.

```
mode (symbol | lines+scope | query) ──► regions[{file, start, end, score}]
merge(regions) ──► non-overlapping, ordered regions
render(regions, budget) ──► headers + bodies + elision markers
```

## Components

- **Symbol resolver** (`--symbol`) — parses the file with tree-sitter, builds a
  qualified-name table (handling nesting like `ClassName.method`), and returns the
  full span of the matching definition including decorators/comments attached above.
- **Scope expander** (`--lines --scope`) — finds the smallest enclosing
  function/class node containing the requested range and widens the region to it;
  without `--scope` the raw range is used.
- **Query scorer** (`--query`) — splits the file into blocks (top-level definitions,
  else fixed-size windows for non-code files), scores blocks by keyword hits with
  simple TF weighting, returns the top blocks by score.
- **Region merger** — sorts regions, merges adjacent/overlapping ones so output
  never duplicates lines.
- **Renderer** — per excerpt: `path:startline-endline` header, body, and
  `… N lines elided …` between non-adjacent excerpts. Multi-file invocations
  render file groups in argument order.
- **Budget enforcement** — `--max-tokens N` (bytes/4): drops lowest-score query
  blocks first, then trims the largest excerpt from the bottom at block boundaries;
  never cuts mid-statement.

## Key decisions

- Language: Python, stdlib only. Python files parse via `ast` (exact spans);
  JS/TS via a brace-tracking line scanner (heuristic — declarations must
  open their brace on the same line); markdown via fence-aware heading scan.
  See ADR-004 for why tree-sitter was dropped.
- Blocks, not lines, are the unit of trimming — output stays syntactically whole.
- Parsing is per-invocation and stateless; no index dependency.

## Dependencies

Stdlib only.
