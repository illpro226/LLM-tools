# repomap PRD

## Problem statement

Coding agents orient themselves in an unfamiliar repository by reading dozens of files, burning tens of thousands of tokens before doing any useful work. Most of that content is irrelevant: what the agent actually needs is the shape of the codebase — which files matter, what symbols they define, and how the tree is organized. `repomap` produces that orientation view in ~1–2k tokens.

## Target users

- Coding agents (Claude Code, aider, etc.) at the start of a session or task.
- Humans who want a one-screen overview of a repo they have not seen before.

## Scope

### Core behavior

- Given a directory, print a compact repository map with two layers:
  1. A pruned directory tree that skips vendored/generated directories (`node_modules`, `.git`, `dist`, `build`, `__pycache__`, etc.).
  2. Per source file, a one-line-per-symbol outline of top-level classes and functions with signatures and docstring first-lines.
- Extract symbols with tree-sitter for Python, JS/TS, Go, Rust, and C/C++ at minimum; fall back to regex-based extraction for other languages.
- Rank files by importance — how often their symbols are referenced elsewhere (import graph / reference count) — and emit the most important files first.

### CLI surface

- `repomap [DIR]` — print the map for a directory (default: cwd).
- `--focus PATH` — expand detail around one subtree while keeping the rest compressed.
- `--max-tokens N` — cap output (tokens estimated as bytes/4). Degrade in order: drop low-rank files, then drop signatures, then fall back to tree-only.

### Output conventions

- Plain text, deterministic, stable ordering across runs. No ANSI color.

## Non-goals

- Full symbol cross-referencing or call graphs (that is `repoindex`/`callgraph`).
- Rendering file contents or bodies (that is `xread`).
- IDE-grade semantic accuracy; ranking is heuristic and best-effort.

## Acceptance criteria

- On a fixture repo, output contains the pruned tree and per-file symbol outlines, with vendored directories absent.
- Files appear in importance-ranked order, stable across repeated runs.
- `--max-tokens` produces output within budget and degrades in the specified order (files → signatures → tree-only) rather than truncating mid-symbol.
- `--focus` expands the named subtree and compresses the rest.
- Supported-language fixtures (Python, JS/TS, Go, Rust, C/C++) each produce correct outlines; an unsupported-language file still appears via the regex fallback.
- Tests run against a small fixture repo and pass in CI.
