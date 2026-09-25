# sgrep Architecture

Status: implemented (v0.1.0) in `sgrep.py`, matching this design. Density is
measured as matching-line count per file (rg emits one match event per
line); ranking multiplies it by the path-class weight.

## Overview

`sgrep` never matches text itself: it shells out to `rg --json`, parses the event
stream, and post-processes hits into a ranked digest.

```
rg --json PATTERN ──► match events
parse ──► hits[{file, line, text, submatches}]
group by file ──► per-file hit lists + counts
dedupe (normalized text) ──► distinct representatives + "more similar" counts
rank files ──► density × path-class weight
render(budget) ──► file headers + path:line: content
```

## Components

- **Runner** — builds the `rg --json` argv (passing through pattern, paths, and a
  safe subset of rg flags), streams stdout, and handles the missing-binary case
  with a short install hint and nonzero exit.
- **Normalizer/deduper** — normalizes match lines (collapse whitespace, strip
  numbers/ids) to cluster near-identical hits; per file, keeps one representative
  per cluster when count > 5 and records a `(+N more similar)` remainder (or
  `(+N more, D distinct)` when the budget capped distinct clusters away).
- **Ranker** — score = match density × path-class weight. Path classes
  (src > tests > generated/vendored) come from built-in patterns, overridable via
  config. Ties break by path sort for determinism.
- **Renderer** — per-file header with count, then `path:line: content` lines.
  `--files-only` and `--counts-only` short-circuit after grouping.
- **Budget reducer** — `--max-tokens N` reduces in fixed order: context lines →
  matches per file → files shown, re-rendering until within budget.

## Key decisions

- Language: Python; subprocess + JSON parsing only, no regex engine of our own.
- rg's JSON stream is consumed incrementally so huge result sets stay bounded.
- Flag surface is deliberately small; power users can fall back to raw `rg`.

## Dependencies

`ripgrep` binary at runtime; stdlib only in-process.
