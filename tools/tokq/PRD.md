# tokq PRD

## Problem statement

Neither agents nor humans can see the token cost of content before it enters context, so waste (lockfiles, minified bundles, 2 MB JSON dumps) goes unnoticed until the budget is gone. `tokq` measures the token cost of anything — files, command output, directories — and flags waste. It is the feedback signal every other tool in this suite optimizes against, and the suggested first build.

## Target users

- Coding agents deciding whether to read something and which tool to read it with.
- Humans auditing what is expensive in a repo, and scripts gating context budgets.

## Scope

### CLI surface

- `tokq FILE...` — per-file token estimates and a total.
- `some-cmd | tokq -` — meter stdin.
- `tokq dir PATH` — a token-weighted tree (like `du` but tokens), heaviest paths first.
- `tokq lint PATH...` — flag context-wasteful content:
  - files over a size threshold;
  - lockfiles, minified, and generated files (by name patterns plus long-line/entropy heuristics);
  - suggest the cheaper tool from this suite (`structo` for data files, `xread` for big sources, `repomap` for directories).
- `--budget N` — `lint` exits nonzero when something exceeds the budget, so it can gate scripts.

### Tokenization

- Use a real tokenizer when available (`tiktoken` with an o200k-class encoding); fall back to a bytes/3.7 heuristic. Output notes which method was used.
- Startup stays under 100 ms in the fallback path.

## Non-goals

- Reducing or transforming content (the other tools do that; `tokq` only measures and points).
- Exact billing-grade token counts for every model; estimates are labeled as such.
- Watching or continuous monitoring; `tokq` is a one-shot CLI.

## Acceptance criteria

- File, stdin, and directory modes each report estimates plus a total, with the tokenizer/heuristic used noted in output.
- With `tiktoken` absent, the fallback engages and startup is measured under 100 ms.
- `dir` orders entries heaviest-first, deterministically.
- `lint` flags an oversized file, a lockfile by name, and a minified fixture by line-length/entropy, each with the correct cheaper-tool suggestion.
- `lint --budget N` exits nonzero when exceeded and zero otherwise.
- Tests cover estimates, thresholds, suggestions, and exit codes.
