# codediff PRD

> Amended by [`docs/decisions/0002`](../../docs/decisions/0002-wave-4-codediff.md)
> and DECISIONS.md ADR-004/ADR-005: no tree-sitter (repoindex's pure
> `extract()` parses both sides), risk is flat explainable flags — the
> `LOW/MED/HIGH` grade below is superseded — and there is no `--llm` flag
> (`--json` is the narrator payload).

## Problem statement

Raw diff hunks are a poor way to understand a change: reviewers and agents think in terms of behavior changes, API surface changes, removals, and risk. `gitbrief` tells you *what files* changed; `codediff` tells you *what the change means* — far more useful per token for review, commit messages, and deciding what to test.

## Target users

- Coding agents reviewing their own or others' changes and deciding what to test.
- Human reviewers wanting a semantic summary before reading hunks.

## Scope

### Inputs

- Default: working tree vs HEAD. Also accept a ref, a range, or `--staged`.

### Analysis (static-first, deterministic)

- Parse before/after versions of each changed file — reuse `repoindex`'s extraction library for the "after" side and its tree-sitter machinery for the "before" side — and diff at the symbol level.
- Classify into sections:
  - **API changes** — added/removed/renamed public symbols, signature changes shown as `old → new`.
  - **Behavior changes** — modified function bodies; detect cheap high-signal patterns: changed literal/default values (`3 → 5`), added/removed conditionals, added/removed calls.
  - **Removed** — deleted symbols, noting deprecation markers.
  - **Mechanical** — formatting-only, comment-only, import reshuffles; collapsed to one line.
- **Risk rating** (LOW/MED/HIGH) from explainable heuristics: sensitive-path keywords (auth, crypto, payment, migration — configurable in `.codediff.toml`), public-API surface touched, size of behavior delta, and whether matching tests changed (query the `tests` table in `.repoindex/index.db` if present). Each contributing reason is printed.

### CLI surface

- `--llm` — optional mode sending the compact symbol-level delta (never the raw diff) to an LLM for a one-paragraph narrative; off by default.
- `--json` — structured output for tooling.
- `--max-tokens N` — cap output; collapse least-severe sections first.
- Languages: Python, JS/TS, Go first.

### Output conventions

- Every finding carries a `path:line` reference.

## Non-goals

- Showing raw hunks (that is `gitbrief`).
- Blocking/gating semantics; risk is advisory.
- Requiring network or an LLM — the core tool is deterministic and offline.

## Acceptance criteria

- Fixture diffs land in the right sections: a signature change under API (with `old → new`), a default-value change under Behavior (`3 → 5`), a deleted deprecated symbol under Removed, and a formatting-only change under Mechanical as one line.
- A rename is reported as a rename, not remove+add.
- Risk is HIGH for a fixture touching an auth path with no test changes, with each reason listed; keywords are configurable via `.codediff.toml`.
- Every finding line includes `path:line`.
- `--json` output round-trips through a parser in tests; `--max-tokens` keeps output within budget.
- With `--llm` unset, no network access occurs.
