# tokq Architecture

Status: planned — no implementation exists yet. This describes the intended design.

## Overview

`tokq` has one estimation core and three thin fronts (files/stdin, dir tree,
lint). The hard constraint is startup: under 100 ms in the fallback path, which
drives the lazy-import design.

```
estimator (tiktoken if importable, else bytes/3.7) ──► tokens(content)
  ├─► meter front:  tokq FILE... | tokq -
  ├─► tree front:   tokq dir PATH   (du-style, heaviest first)
  └─► lint front:   tokq lint PATH... [--budget N]
```

## Components

- **Estimator** — tries `tiktoken` (o200k-class encoding) via lazy import inside
  the call path; on ImportError uses bytes/3.7. Every report states which method
  was used. Binary-ish content (NUL bytes, high non-text ratio) is flagged and
  estimated by size only.
- **Meter front** — per-file estimates plus a total; `-` meters stdin as one
  stream.
- **Tree front** — walks a directory (same skip list conventions as the rest of
  the suite), aggregates tokens per subtree, prints heaviest-first with
  cumulative percentages, like `du` for tokens.
- **Lint rules** — a rule list evaluated per path:
  - size threshold exceeded;
  - lockfile / minified / generated detection by name patterns
    (`package-lock.json`, `*.min.js`, `dist/`, …) and content heuristics
    (long-line ratio, entropy);
  - each finding carries the cheaper-tool suggestion: `structo` for data files,
    `xread` for big sources, `repomap` for directories.
- **Budget gate** — `lint --budget N` exits nonzero when any path exceeds the
  budget, so scripts and hooks can gate on it.

## Key decisions

- Language: Python with aggressively lazy imports; the fallback path imports
  effectively nothing beyond argparse and os.
- Estimates are labeled, never silently mixed: a run states tokenizer vs
  heuristic once in the header.
- Rules are data (pattern + threshold + suggestion), so adding one is a table row.

## Dependencies

Optional `tiktoken`; stdlib otherwise.
