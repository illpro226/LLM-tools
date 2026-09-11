# LLM-tools — a token-economy toolkit for coding agents

**What it is.** Nine small, standalone CLI utilities that sit between a coding agent and a
codebase. Each one answers a question an agent would otherwise answer by dumping raw bulk
into its context window — a whole file, a full `rg` result set, an entire `git diff`, a
50k-line build log — and returns a compact, deterministic, `path:line`-anchored summary
instead. Stdlib-only Python, ~6,300 lines across the tools, no runtime dependencies, no
network calls, offline and deterministic by default.

| Tool | Replaces | Answers |
|---|---|---|
| `xread` | `cat FILE` | one function / section / heading set |
| `sgrep` | `rg PATTERN` | ranked, cluster-deduped matches |
| `structo` | reading a JSON/YAML/TOML/JSONL/XML/CSV file | its *shape*, streamed, O(schema) memory |
| `gitbrief` | `git diff` / `git log` | layered status, hunks, log, PR summary |
| `codediff` | reading a diff | what the change *means*: API / behavior / removed / mechanical + risk flags |
| `runlite` | a build or test log | failure-focused report; `trace` distills a stack trace you didn't produce |
| `repomap` | `ls -R` + reading files | tree plus ranked symbol outline |
| `tokq` | guessing | token cost of a file or directory before you read it |
| `repoindex` | re-parsing source | shared symbol/relationship index behind `codediff` |

## Real-world proof of work

The suite is instrumented. A Claude Code hook logs every suite call and, where an honest
baseline exists, measures what the naive alternative would have cost — the whole file for
`xread`/`structo`, a background run of the equivalent raw `git`/`rg` command for
`gitbrief`/`sgrep`/`codediff` (measured for length only, never shown to the model), and for
`runlite` the log size it reports itself. The result, as of **2026-08-25**:

> **~6.71 million tokens saved across 2,443 suite calls** (1,259 of them credited against a
> measured raw equivalent). The tools printed ~873k tokens total; their raw equivalents
> would have printed ~7.19M.

| tool | calls | credited | credited output | raw equivalent | saved | avg saved / credited call |
|---|---:|---:|---:|---:|---:|---:|
| `structo` | 150 | 80 | ~19,355 | ~3,139,790 | **~3,120,435** | ~39,005 |
| `xread` | 497 | 409 | ~227,664 | ~1,867,749 | **~1,640,085** | ~4,010 |
| `gitbrief` | 133 | 98 | ~58,870 | ~1,048,177 | **~989,307** | ~10,095 |
| `codediff` | 100 | 37 | ~24,736 | ~928,703 | **~903,967** | ~24,432 |
| `runlite` | 315 | 86 | ~10,481 | ~50,876 | **~40,394** | ~470 |
| `sgrep` | 1,141 | 549 | ~140,354 | ~157,452 | **~17,099** | ~31 |
| **total** | **2,443** | **1,259** | **~481,459** | **~7,192,748** | **~6,711,288** | **~5,331** |

`repomap` (81 calls), `tokq` (26) and `repoindex` (0) log usage but have no honest raw
baseline, so they are counted and never credited.

**The measurement is deliberately conservative.** A baseline counts only when it answers the
*same question* as the call it's compared against — for `sgrep`, the raw `rg` has to carry
the same `-C`, `-i`, `-t`, `-g` and every path. Calls with no derivable equivalent score
`n/a` rather than a flattering zero, and a raw command that matched nothing is `n/a` too,
because crediting it would score the suite call as pure loss. Figures are tokens estimated
at bytes/3.7. Full method and per-call data: [`savings_record.md`](../savings_record.md),
`.savings/events.jsonl`.

**What the numbers actually taught us.** `sgrep` is the most-called tool in the suite and
saves ~31 tokens a call — near break-even, because `rg` is already terse. `structo` is
called rarely and saves ~39,000 tokens a call, because the thing it replaces is reading a
multi-megabyte JSON file. That asymmetry is only visible with instrumentation, and it's the
reason the record leads with `calls` and `last used`, not `saved`: a tool nobody calls scores
neutral on savings while still costing maintenance, docs, and space in an agent's head. Two
working, tested tools (`rq`, `testmap`) were archived on exactly that evidence rather than
on opinion.

## How it's built

Every tool follows suite-wide invariants: plain text, stable ordering, no color or spinners,
a `path:line` on every claim about code, a `--max-tokens` budget **on by default** that
degrades by summarizing harder rather than truncating mid-thought, and two-valued confidence
(`resolved` | `heuristic`) — never an ordinal grade static analysis can't honestly support.
Breaking one of those needs a decision record, not a PR: nine ADRs in `docs/decisions/`
carry the binding history, including the one that closed the build list and the one that
retired the two unused tools. Each tool ships its own README, STATUS, CHANGELOG, PRD, design
docs, and pytest suite.

Public at `github.com/illpro226/LLM-tools`. 57 commits, in daily use as the working
toolchain for its own development — the savings above were earned building this repo and
others, not on a benchmark.
