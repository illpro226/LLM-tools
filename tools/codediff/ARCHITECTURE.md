# codediff Architecture

Status: planned — no implementation exists yet. This describes the intended design.

## Overview

`codediff` diffs at the symbol level, not the line level: parse before/after
versions of each changed file with `repoindex`'s extraction machinery, align
symbols, classify the deltas, and score risk. The raw hunk diff is only used to
detect which files changed and to catch formatting-only cases cheaply.

```
git (working tree vs HEAD | ref | range | --staged) ──► changed files + blobs
repoindex.extract(before), repoindex.extract(after) ──► symbol tables
align + diff symbols ──► deltas
classify ──► {API, Behavior, Removed, Tests, Mechanical}
risk(deltas, config, tests table) ──► LOW/MED/HIGH + reasons
render | --json | --llm(narrative over compact delta)
```

## Components

- **Diff source** — `git diff --name-status` for the file set; `git show` /
  worktree reads for before/after contents. Ranges, refs, and `--staged` map to
  the same interface.
- **Extraction** — imports `repoindex.extract` as a library; the same
  tree-sitter machinery parses the "before" blob (from git) and "after" file.
  No second parser is ever written here.
- **Symbol aligner** — matches before/after symbols by qualified name; unmatched
  pairs with high body similarity become *renames* rather than remove+add.
- **Classifier** —
  - *API*: added/removed/renamed public symbols; signature changes rendered
    `old → new`.
  - *Behavior*: changed bodies, with cheap pattern detectors — literal/default
    value changes (`3 → 5`), added/removed conditionals, added/removed calls.
  - *Removed*: deleted symbols, noting deprecation markers found on the before
    side.
  - *Tests*: files matching test conventions get one counted line
    (`+29 tests, +1 helper`) instead of per-symbol entries, and never
    contribute to the API/Behavior sections or the risk flags — see ADR-006.
  - *Mechanical*: formatting-only / comment-only / import reshuffles, detected
    by comparing normalized token streams; collapsed to one line.
- **Risk scorer** — explainable additive heuristics: sensitive-path keywords
  (auth, crypto, payment, migration — overridable in `.codediff.toml`), public
  API surface touched, behavior-delta size, and whether covering tests changed
  (join against `.repoindex/index.db` `tests` when present). Output always lists
  the contributing reasons.
- **Renderers** — sectioned text (every finding with `path:line`), `--json`
  mirror of the model, and `--llm` which sends only the compact symbol-level
  delta (never raw hunks) for a one-paragraph narrative; off by default.
- **Budget** — `--max-tokens N` collapses Mechanical first, then Behavior
  detail, never the Risk block.

## Key decisions

- Language: Python; hard dependency on `repoindex.extract` is deliberate —
  one extraction implementation for the whole suite.
- Deterministic and offline by default; the LLM path is strictly additive.
- Risk is advisory and explainable — no opaque scores.

## Dependencies

`repoindex` (library + index), `git` at runtime; `tree-sitter` transitively.
