# LLM-tools — per-tool reference

Precise, single-file reference for all 11 implemented tools in the suite. For
scope/history see the root `CLAUDE.md`, `START.md`, and each tool's own
`PRD.md`/`STATUS.md`/`DECISIONS.md` (this file summarizes, not replaces them).

All tools: stdlib-only Python CLIs (single file, except `repoindex` which is
a small package), fast startup (~100ms budget), deterministic plain-text
output, no ANSI color/spinners/timestamps, every claim line carries a
`path:line` reference, every tool with growable output supports
`--max-tokens N` and degrades by dropping whole levels of detail (never
mid-statement/mid-thought). Confidence, where reported, is two-valued
(`resolved` | `heuristic`) — never an ordinal scale.

Run each from its own directory (`cd tools/<name>`) as `./<name>.py ...` or
`python <name>.py ...`; shims on PATH also expose bare tool names
(`tokq`, `sgrep`, etc.) per `llm-tools-path-and-guard-hook` memory.

---

## tokq — token cost meter and context linter

**Status:** Implemented v0.1.0.

Measures token cost of files/stdin/directories before they enter context, and
flags context-wasteful content (lockfiles, minified bundles, high-entropy
blobs, oversized files) with a cheaper-tool suggestion.

```
tokq FILE...                 # per-file token estimates and a total
some-cmd | tokq -            # meter stdin
tokq dir PATH [--top N]      # token-weighted tree, heaviest paths first
tokq lint PATH...             # flag context-wasteful content
tokq lint PATH --budget N     # exit 1 if any PATH exceeds N tokens
```

**Flags:** `--tokenizer {auto,tiktoken,heuristic}` (also `TOKQ_TOKENIZER`),
`--max-tokens N`, `lint --threshold N` (big-file cutoff, default 4000
tokens).

**Estimator:** `tiktoken` (o200k_base) when installed, else a bytes/3.7
heuristic; every report states which was used. Binary content is flagged and
size-estimated rather than tokenized.

**Lint suggestions** point at the cheaper tool: `structo` for data files,
`xread` for big sources, `repomap` for directories. `lint --budget N` exits
nonzero when a path exceeds budget, so it can gate scripts/hooks.

**Example:**
```
$ tokq lint package-lock.json bundle.js
# estimator: heuristic (bytes/3.7)
LOCKFILE     package-lock.json  (13 tokens) — generated lockfile; skip it, or `structo` if you need its shape
MINIFIED     bundle.js  (325 tokens) — minified/bundled (max line 1200 chars); skip it: generated, near-zero signal per token
2 findings; total 338 tokens
```

**Known gaps:** no packaging/PATH install story built into the tool itself;
lint rule table could grow.

---

## runlite — command output distiller

**Status:** Implemented v0.1.1.

Runs a build/test/lint command, captures merged stdout+stderr, and prints a
failure-focused report (exit code, wall time, extracted problems with
`file:line`) instead of dumping thousands of passing lines.

```
runlite -- CMD ARGS...              # run and distill
runlite --max-tokens N -- CMD...    # over budget: first problem full, rest one line each
runlite --full-log PATH -- CMD...   # also save the raw log, print its path
```

**Extractors:** pytest, go test, cargo (compile errors + panics), tsc,
eslint, jest/vitest, gcc/clang, and a generic fallback (error/warning/fail
pattern lines + last 20 lines). Detection order: command name → log
fingerprint → generic.

**Exit codes:** passthrough of the wrapped command's exit code; reserved 125
(runlite-internal failure), 127 (command not found). On Windows, argv[0]
resolves through PATHEXT so `.cmd`/`.bat` shims (`npx`, `tsc`) spawn.

**Example:**
```
$ runlite -- pytest -q
# runlite: exit 1 in 0.74s (pytest) 2 problems

FAIL test_add  test_demo.py:5
      def test_add():
  >       assert add(2, 3) == 5
  E       assert -1 == 5
```

**Known gaps:** no timeout handling, no `--json` report.

---

## xread — targeted code excerpt reader

**Status:** Implemented v0.2.0.

Prints just the relevant part of a file — a named symbol's body, a line
range expanded to its enclosing scope, top keyword-scoring blocks, or a
markdown section — instead of a whole-file read.

```
xread FILE --symbol NAME             # function/class/method body; nested
                                      # names like ClassName.method; on .md
                                      # files, a heading's section
xread FILE --lines A-B [--scope]     # line range; --scope expands to the
                                      # enclosing function/class
xread FILE --query "text" [--top N]  # top keyword-scoring blocks
xread FILE.md --headings             # markdown heading outline
```

All modes accept multiple files (grouped in argument order) and
`--max-tokens N` (drops whole low-score blocks, then trims at blank-line
boundaries — never mid-statement).

**Parsers:** Python via stdlib `ast` (exact spans, decorators + attached
comments); JS/TS via a brace-tracking heuristic (declarations must open
their brace on the same line — Allman-style and multi-line arrow params are
missed); markdown via a fence-aware heading scan; Prisma schemas via a flat
block scanner (`model`/`enum`/`type`/`view`/`generator`/`datasource`).

Query mode on markdown pulls in a short (≤ 20 line) preceding same-level
sibling section when the match starts at a heading and the sibling carries
a fenced block — the payload-above-the-match case.

Every excerpt starts with a citable `== path:start-end ==` header;
`… N lines elided …` markers appear between non-adjacent excerpts; overlapping
requests are merged so no line prints twice.

**Example:**
```
$ xread tools/tokq/tokq.py --lines 120-121 --scope
== tools/tokq/tokq.py:120-128 ==
def _shannon_entropy(data):
    if not data:
        return 0.0
    ...
```

**Known gaps:** no tree-sitter upgrade path wired yet (would slot in as an
alternate parser); no packaging/PATH story of its own.

---

## sgrep — token-budgeted search condenser

**Status:** Implemented.

A ripgrep wrapper that turns a large grep dump into a short ranked digest.
Requires the `rg` binary at runtime (PATH, `--rg BIN`, or `SGREP_RG`) —
matching itself is never reimplemented.

```
sgrep PATTERN [PATH...]                       # condensed, ranked digest
sgrep PATTERN --files-only                    # ranked matching-file list (cheapest)
sgrep PATTERN --counts-only                   # ranked list with match counts
sgrep PATTERN --max-tokens N                  # reduce: context lines, then
                                               # matches/file, then files shown
sgrep PATTERN -C 2 -i -F -w -t py -g '*.rs'   # small rg pass-through flag set
```

**Ranking:** matches grouped by file; near-identical hits deduplicated
(whitespace collapsed, digit runs equalized) to one representative per
distinct normalized form, 3 at most, plus a `(+N more similar)` remainder.
Files rank by match count × path class — src before tests before generated.

**Exit codes:** follows grep — 0 matches found, 1 no matches, 2 error.

**Config:** optional `.sgrep.toml` in the working directory (or
`--config PATH`):
```toml
[weights]
tests = 0.8          # src / tests / generated class weights

[classes]
generated = ["*.snap"]   # extra fnmatch patterns per class
```

**Example:**
```
$ sgrep max_tokens tools --max-tokens 150
== tools/xread/xread.py (8 matches) ==
tools/xread/xread.py:397: def apply_budget(regions, sources, max_tokens):
(+7 more similar)
```

---

## repomap — repository skeleton generator

**Status:** Implemented v0.1.0.

A pruned directory tree plus a one-line-per-symbol outline of each source
file's top-level classes/functions, most-referenced files first. Lets an
agent orient itself for ~1–2k tokens instead of reading dozens of files.

```
repomap [DIR]              # map for a directory (default: cwd)
repomap --focus PATH       # expand one subtree, compress the rest
repomap --max-tokens N     # stay under budget (bytes/4); degrades:
                           # collapse deep tree levels → drop low-rank
                           # outlines → drop signatures → tree-only
```

**Tree pruning:** built-in skip list plus a subset of the root `.gitignore`
(nested `.gitignore` files and negation patterns are unsupported).

**Extraction (stdlib only, no tree-sitter — ADR-004):** Python via `ast`;
JS/TS and C/C++ via depth-tracking line scanners (brace must open on the
declaration line); Go and Rust via column-0 declaration patterns (indented/
module-nested items and split Allman-style C prototypes are missed); other
languages via a generic declaration regex. Non-Python extraction is
top-level-only and heuristic by design.

**Ranking:** built-in identifier-occurrence counter only; using
`.repoindex/index.db` instead is deferred until repoindex's schema is pinned
(ADR-005) — the ranker function is the seam where that would slot in.

Every symbol line carries `path:line` so it can be followed up with
`xread PATH --symbol NAME`.

---

## gitbrief — git state summarizer

**Status:** Implemented v0.1.0.

Layered, token-cheap views of git state; the default is a one-screen
summary, detail is opt-in and narrow so "dump the whole diff" never happens
by accident. Read-only by construction — subprocess `git` plumbing only
(`--no-optional-locks`, porcelain formats, rename detection off so a rename
reads as delete+add, no libgit binding).

```
gitbrief                        # branch + drift, status+diffstat table, last 5 commits
gitbrief hunks [FILE...]        # diff hunks at 1 context line (vs HEAD)
gitbrief show FILE              # full diff for exactly one file (byte-identical
                                 # to `git diff HEAD -- FILE`)
gitbrief log [--grep X] [--author X] [-n N]
gitbrief pr BASE                 # branch summary vs BASE: commits, diffstat,
                                 # changed symbols (heuristic; python/js-ts)
```

All modes accept `--max-tokens N` (bytes/4) and degrade by whole levels:
tables collapse to counts, hunks drop context then bodies, lists shorten.

`pr`'s changed-symbol list comes from stdlib extraction of before/after
blobs — Python via `ast`, JS/TS via a brace scanner — classified
+added/~modified/-removed by diff-range intersection (ADR-005, supersedes an
earlier optional-tree-sitter plan); other languages are listed in a "not
analyzed" note.

**Known gaps:** untracked files have no `show` view (use `xread` instead);
rename detection intentionally off; symbol analysis limited to Python and
JS/TS top-level declarations.

---

## structo — big-file shape summarizer

**Status:** Implemented v0.2.0.

Prints the schema and shape of a data file — keys, types, optionality, array
lengths, column stats, log templates, a couple of samples — instead of its
content. Formats: JSON, JSONL, YAML (PyYAML — the one optional dependency;
clear error if absent), CSV, TSV, XML, generic log; detected by extension
else content sniffing, and the header states which.

```
structo FILE                     # summarize (format auto-detected)
structo FILE --path a.b[0].c     # zoom into a JSON/YAML subtree (a leading
                                  # [N] picks JSONL record N)
structo FILE --raw --path ...    # print the exact value at --path
                                  # (strings verbatim, else JSON)
structo FILE --sample N          # array elements aggregated (default 10)
structo FILE --max-tokens N      # cap output; samples go first, top-level
                                  # structure never does
```

**Streaming (ADR-001):** JSON via an incremental event tokenizer (never
`json.load`s a whole file), JSONL per record, YAML via the PyYAML event API,
CSV per row, logs per line, XML via `iterparse` with element clearing.
Memory is O(schema + samples) — test-enforced with tracemalloc on a
generated ~25 MB JSONL file (peak < 15 MB asserted).

**JSON/YAML/JSONL:** merged schema with types, optionality percentages (key
presence / parent instances), exact array-length stats; array *elements*
beyond `--sample N` are not aggregated and carry a `~` marker (ADR-003 —
sampling is first-N, deterministic, no RNG). One or two example values per
scalar.

**CSV/TSV:** per-column type, null rate, min/max (numeric or lexicographic;
omitted for booleans), bounded-cardinality counter (`~` past 256), exactly 3
sample rows.

**Logs:** timestamp format detection (iso-8601/syslog/clf/epoch), exact line
count, top message templates (numbers/hex/uuids/quoted strings normalized),
first/last lines with `path:line` refs.

**`--raw`:** prints the exact value at `--path` instead of a schema
(strings verbatim; everything else JSON). Still streaming — JSONL parses one
line, JSON uses a full-fidelity tokenizer that materializes only the target
subtree. With `--max-tokens` it refuses (exit 2) rather than truncate — an
exact value can't be summarized (ADR-004).

**Exit codes:** unmatched `--path` or out-of-range JSONL record index → 2;
`--raw --max-tokens` refusal → 2.

**Known gaps:** XML has no `--path` zoom; no Parquet/compressed inputs; YAML
support requires PyYAML.

---

## repoindex — shared repo-wide symbol database

**Status:** Implemented. Package at `tools/repoindex/repoindex/` plus the
`repoindex.py` entry point (not a single file, unlike the rest of the
suite).

Maintains one incremental, stdlib-parser-built SQLite database at
`.repoindex/index.db` holding symbols and every cheap-to-extract
relationship, so `rq`, `testmap`, and `codediff` become SQL queries (or
pure-function reuse, for `codediff`) over one parse instead of each
re-parsing the repo independently.

```
repoindex build              # full index
repoindex update              # incremental: re-extract only changed files
                              # (mtime, then hash), in one transaction
repoindex status              # freshness + per-language file/symbol counts
repoindex sql "SELECT ..."     # read-only escape hatch, column-aligned output
```

**Schema (one SQLite file — joins across relationships are the point):**

| table | contents |
|---|---|
| `files` | path, language, mtime, content hash |
| `symbols` | qualified name, kind (func/class/method/const/type), file, line span, visibility/exported |
| `refs` | from-location → to-symbol, kind (`call`/`read`/`write`/`type-use`), confidence (`resolved`/`heuristic`) |
| `imports` | file → module/symbol, alias, line |
| `inherits` | child symbol → parent symbol |
| `implements` | symbol → interface/protocol symbol |
| `tests` | test symbol/file → covered file/symbol, source (`convention`/`import`/`coverage`) |

**Extraction:** stdlib parsers only (ADR-007, same precedent as
`xread`/`repomap`/`gitbrief`) — Python via `ast` (exact spans), JS/TS and Go
via heuristic line/brace scanners. References are resolved via imports plus
scope-aware name matching; unresolved/dynamic edges are stored with
`confidence=heuristic` rather than dropped. `repoindex.extract` ships as an
importable, pure, filesystem-free library so `codediff` can parse before/
after git-blob content with the same machinery.

`update` re-extracts only files whose mtime (then hash) changed and
reconstructs unchanged files from the DB so repo-wide passes still see
everything — all inside one transaction. `.repoindex/` is added to a
generated `.gitignore` entry and never committed.

**Non-goals:** answering user-facing questions itself (that's `rq`); full
type inference/IDE-grade resolution; indexing vendored/generated
directories.

---

## rq — query pack over the index

**Status:** Implemented.

Answers relationship questions about a codebase from the shared
`.repoindex/index.db` — never parses source itself (ADR-002: data gaps are
repoindex bugs, not rq's). Runs `repoindex update` before every query unless
skipped.

```
rq whouses SYMBOL                  # inbound refs, grouped per matched symbol
rq implements INTERFACE             # implementations, subclasses nested beneath
rq inherits BASE                    # subclass tree
rq impact SYMBOL [--depth N]        # blast radius + covering tests (default depth 3)
rq publicapi [PATH]                 # exported symbols, optionally under PATH
rq deadcode [--include-exported]    # symbols with zero inbound refs
rq findcycles                       # import cycles between files, smallest first
rq untested                         # exported symbols with no covering test
```

**Shared flags** (accepted before or after the subcommand; post-subcommand
value wins if given both places): `--root DIR`, `--json`, `--max-tokens N`
(leaf lists collapse to `(+N more)` counts), `--no-update` (skip the
automatic `repoindex update`), `--repoindex CMD` (freshness-guard binary;
also env `RQ_REPOINDEX`; defaults to PATH, then the sibling
`tools/repoindex/repoindex.py`).

`SYMBOL` accepts a full qualname (`py/shapes.py::Rectangle`), a local name
(`Rectangle`), or a member name (`area`); matching is case-sensitive (SQLite
`LIKE` is case-insensitive, so rq uses `substr()` suffix matching instead).

`impact` answers via a per-level SQL BFS, because the innermost-enclosing-
symbol join can't live in a recursive CTE (ADR-003). `deadcode` is
conservative by default — exported/dunder/test-file/heuristically-referenced
symbols excluded, with a caveat that heuristic refs could hide real callers
(ADR-004). `publicapi` prints no signatures because the index stores none
(ADR-006).

**Exit codes:** 0 success, 1 symbol not found, 2 no index and `repoindex`
unavailable.

---

## testmap — change-to-test scoper

**Status:** Implemented.

Maps changed files to the tests that likely cover them, so an agent runs a
handful of tests instead of the whole suite. Pairs with `runlite`: scope
first, distill second. Reads `.repoindex/index.db` — never parses source
itself, and runs `repoindex update` first like `rq`.

```
testmap [FILES...]                  # map changed files (default: git diff
                                     # --name-only HEAD + untracked) to
                                     # covering tests
testmap record -- pytest [ARGS]     # run the suite under coverage.py and
                                     # write exact file->test rows into the
                                     # shared index
```

**Output:** one target per line, tagged by the layer that selected it, most
trusted wins when several layers agree:
- `(coverage)` — recorded fact from `testmap record`
- `(changed-test)` — a changed test file selects itself
- `(convention)` — name-pair heuristic (`foo.py` / `test_foo.py`)
- `(import depth N)` — reverse BFS over the import graph, N hops

Followed by a ready-to-run command per detected framework (`pytest a b`,
`npx vitest run a b`/`npx jest`, `go test ./pkg`). Best-effort, never a
completeness claim: when nothing maps, the full-suite command is printed as
fallback, and indexed changed files with no mapped tests are noted
individually.

**Flags:** `--depth N` (max transitive import depth, default 2), `--root
DIR`, `--json`, `--max-tokens N` (target list collapses to `(+N more)`; run
commands are never dropped), `--no-update`, `--repoindex CMD` (also env
`TESTMAP_REPOINDEX`).

`record` currently supports pytest only (needs `coverage.py`); it replaces
prior coverage rows only for the test files seen in that run, and passes the
test command's exit code through.

**Exit codes:** 0 mapped (possibly to nothing), 1 changed files
undeterminable (not a git work tree and no explicit file list given), 2 no
index / record prerequisites missing.

---

## codediff — semantic diff summarizer

**Status:** Implemented.

Summarizes what a git diff *means*, not its hunks. Changed files are parsed
on both sides with `repoindex`'s pure `extract()` library and diffed at the
symbol level (git blob vs. worktree/index content — reuses repoindex per its
ADR-006 plan).

```
codediff                  # working tree vs HEAD
codediff --staged          # index vs HEAD
codediff REF               # working tree vs REF
codediff A..B               # B vs A   (A...B: B vs merge-base)
codediff --json             # structured output for tooling
codediff --max-tokens N     # cap output; mechanical collapses first,
                             # then behavior detail, then per-section counts
```

**Classification:**
- **API** — signatures as `old → new`; renames paired by exact normalized-
  body equality, not a fuzzy threshold (ADR-004)
- **Behavior** — literal/default changes (`3 → 5`), conditional and call
  deltas
- **Removed** — deprecation markers noted
- **Mechanical** — formatting/comment-only via Python AST-dump equality,
  import reshuffles; one line per file

**Risk** is a flat list of explainable flags — never a graded score
(DECISIONS.md ADR-003, root `docs/decisions/0002`): sensitive-path keywords
and the behavior-delta threshold from `.codediff.toml`, public-API surface
changes, stale or missing test coverage (via the shared `tests` table after
an implicit `repoindex update`).

**Config** (`.codediff.toml` at repo root):
```toml
[risk]
keywords = ["auth", "billing"]
large_delta = 8
```

Flags to control the repoindex binary/library used for the coverage check:
`--repoindex`, `--repoindex-lib`, env `CODEDIFF_REPOINDEX_BIN` /
`CODEDIFF_REPOINDEX`. There is no `--llm` flag; `--json` is the compact
narrator payload (ADR-005).

**Requires:** `git` on PATH and the `repoindex` package importable (a
sibling checkout works uninstalled).

**Exit codes:** 0 ok, 2 usage/git error.

---

## Deferred / merged (not built)

- **`factbook`**, **`docsnip`** — deferred indefinitely per
  `docs/decisions/0003`; revivable only via a new decision record citing
  recorded `docs/known-issues/` evidence. Never implemented; their scaffold
  directories were removed (`docs/decisions/0008`) — the specs live on in
  0001/0003 if revival ever needs a starting point.
- **`callgraph`** — merged into `rq` before implementation; no standalone
  binary, no directory.
- **MCP stdio adapter** (`mcp/`) — accepted in principle
  (`docs/decisions/0004`) to expose xread/sgrep/structo/gitbrief as MCP
  tools, but not yet built.
