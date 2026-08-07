# tokq

Token cost meter and context linter: measures the token cost of files, stdin,
and directories before they enter an agent's context, and flags waste
(lockfiles, minified bundles, high-entropy blobs, oversized files) with a
cheaper-tool suggestion from this suite.

Single-file Python CLI, stdlib only; uses `tiktoken` (o200k_base) when
installed and falls back to a bytes/3.7 heuristic otherwise. Every report
states which method was used.

## Usage

```
tokq FILE...                 # per-file token estimates and a total
some-cmd | tokq -            # meter stdin
tokq dir PATH [--top N]      # token-weighted tree, heaviest paths first
tokq lint PATH...            # flag context-wasteful content
tokq lint PATH --budget N    # exit 1 if any PATH exceeds N tokens
```

Shared flags: `--tokenizer {auto,tiktoken,heuristic}` (also via
`TOKQ_TOKENIZER`), `--max-tokens N` to cap tokq's own output,
`lint --threshold N` for the "big file" cutoff (default 4000 tokens).

### Examples

```
$ tokq src/main.py
# estimator: heuristic (bytes/3.7)
619  src/main.py
619  total (1 file)

$ tokq lint package-lock.json bundle.js
# estimator: heuristic (bytes/3.7)
LOCKFILE     package-lock.json  (13 tokens) — generated lockfile; skip it, or `structo` if you need its shape
MINIFIED     bundle.js  (325 tokens) — minified/bundled (max line 1200 chars); skip it: generated, near-zero signal per token
2 findings; total 338 tokens
```

Lint suggestions point to the cheaper tool: `structo` for data files, `xread`
for big sources, `repomap` for directories. `lint --budget N` exits nonzero
when a path exceeds the budget so scripts and hooks can gate on it.

## Development

```
python -m pytest        # from tools/tokq/
```

See [`START.md`](../../START.md) for suite-wide conventions.
