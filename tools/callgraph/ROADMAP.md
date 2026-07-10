# callgraph Roadmap

Depends on `repoindex` M1–M2 (schema + extraction) being usable first.

## M1 — Scaffold and depth-1 queries

- CLI entry point; shared fixture repo with known call relationships.
- Resolver (qualified + bare names, disambiguation list).
- Definition + direct callees + callers at depth 1, `path:line` everywhere.

## M2 — Traversal

- `--depth N`, `--callers`/`--callees` direction control.
- Cycle detection with `(cycle)` marker; per-node dedup; fixture cycle test.

## M3 — Index integration polish

- Freshness guard invoking `repoindex update` automatically.
- Heuristic-edge `?` marking from the confidence column.

## M4 — Token budget

- `--max-tokens N`: depth reduction, then sibling collapse to counts;
  deterministic-ordering tests.

## Later

- `--json` output; edge filtering by confidence.
