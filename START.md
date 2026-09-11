# LLM-tools — START

A toolkit of small, composable CLI tools that help coding agents (Claude Code, aider, etc.) spend fewer tokens per task. The common theme: **never put raw, bulky content into an agent's context when a compressed, targeted view will do.**

> **Historical build brief.** The 14 tools listed here were the original
> plan; the build list it describes is superseded by
> [`docs/decisions/0001`](docs/decisions/0001-starting-list-and-deferrals.md) and closed by
> [`0003`](docs/decisions/0003-close-the-list.md). What actually exists:
> nine tools live (`tokq`, `runlite`, `xread`, `sgrep`, `repomap`,
> `gitbrief`, `structo`, `repoindex`, `codediff`), `rq` and `testmap`
> archived (0009), `callgraph` folded into `repoindex`, and
> `factbook`/`docsnip` deferred indefinitely. Read this file for the
> original intent behind a tool, not for the suite's current shape —
> `CLAUDE.md` and each tool's `STATUS.md` are the authority there.

Each tool below has a brief description and a bootstrapping prompt you can paste into a coding agent to start building it. Suggested conventions for the whole suite:

- One directory per tool (`tools/<name>/`), each a standalone CLI installable on PATH.
- Plain-text, deterministic output designed to be *read by an LLM* — compact, stable ordering, no ANSI color, no spinners.
- Every tool supports a `--max-tokens N` (or `--max-bytes`) cap and degrades gracefully by summarizing harder rather than truncating mid-thought.
- Prefer Python or Go, minimal dependencies, fast startup.
- Tools that need symbol/relationship data share one repo-wide index at `.repoindex/index.db` (see tool #13, `repoindex`) instead of each building their own — parse once, query everywhere.

---

## 1. `repomap` — Repository skeleton generator

Produces a compressed map of a codebase: directory tree plus a symbol outline (classes, functions, signatures, docstring first-lines) per file, ranked by importance (import graph / reference count). Lets an agent orient itself in a repo for ~1–2k tokens instead of reading dozens of files.

**Bootstrap prompt:**
> Build a CLI tool called `repomap` in `tools/repomap/`. Given a directory, it prints a compact repository map: (1) a pruned directory tree that skips vendored/generated dirs (node_modules, .git, dist, build, __pycache__, etc.), and (2) for each source file, a one-line-per-symbol outline of top-level classes/functions with their signatures, extracted with tree-sitter (support Python, JS/TS, Go, Rust, C/C++ at minimum; fall back to regex for others). Rank files by how often their symbols are referenced elsewhere and emit the most important files first. Support `--max-tokens N` (estimate tokens as bytes/4) that shrinks output by dropping low-rank files, then dropping signatures, then dropping to tree-only. Include `--focus PATH` to expand detail around one subtree. Add tests against a small fixture repo.

## 2. `xread` — Targeted code excerpt reader

Reads *just the relevant parts* of a file instead of the whole thing: a named function/class body, a line range with syntactic expansion to enclosing scope, or the N most relevant blocks for a keyword query. The single biggest token sink for agents is whole-file reads; this replaces most of them.

**Bootstrap prompt:**
> Build a CLI tool called `xread` in `tools/xread/`. Modes: `xread FILE --symbol name` prints the full body of a named function/class/method (tree-sitter based, resolve nested names like `ClassName.method`); `xread FILE --lines 120-140 --scope` expands the range to the enclosing function/class so the agent sees complete context; `xread FILE --query "text"` scores blocks by keyword match and prints the top blocks. Always print a one-line header per excerpt with `path:startline-endline` so results are citable, and an elision marker (`… 240 lines elided …`) between excerpts. Support `--max-tokens N`. Support reading multiple files in one invocation. Write tests covering Python and TypeScript fixtures.

## 3. `sgrep` — Token-budgeted search condenser

A ripgrep wrapper that post-processes results for LLM consumption: deduplicates near-identical hits, collapses runs of matches in the same file, groups by file, ranks by relevance, and hard-caps total output. Turns a 3,000-line grep dump into a 60-line ranked digest.

**Bootstrap prompt:**
> Build a CLI tool called `sgrep` in `tools/sgrep/` that shells out to ripgrep (`rg --json`) and condenses the results for an LLM. Features: group matches by file with a per-file match count; when a file has >5 matches, show the 3 most distinct ones (dedupe by normalized line content) plus a `(+12 more similar)` note; rank files by match density and path heuristics (prefer src over tests over generated files, configurable); global `--max-tokens N` cap that reduces context lines, then matches per file, then files shown, in that order. Output format: `path:line: content` lines under a file header. Include `--files-only` and `--counts-only` cheaper modes. Test against a fixture tree; also handle the no-ripgrep-installed case with a clear error.

## 4. `runlite` — Command output distiller

Runs a shell command (build, test suite, linter) and returns only what matters: exit status, extracted errors/failures with a few lines of context, and counts — not 5,000 lines of passing-test noise. Agents re-run builds constantly; this is one of the highest-leverage savings.

**Bootstrap prompt:**
> Build a CLI tool called `runlite` in `tools/runlite/` that executes a command (`runlite -- pytest -x`), captures stdout+stderr, and prints a distilled report: exit code, wall time, then extracted problems. Ship built-in extractors (regex/heuristic based) for pytest, jest/vitest, go test, cargo, tsc, eslint, gcc/clang, and a generic fallback that keeps lines matching error/warning/fail patterns plus the last 20 lines. For each failure, include the failure message and nearest file:line reference. Cap output with `--max-tokens N`; when over budget, keep the first failure in full and summarize the rest as one line each. Add `--full-log PATH` to also save the raw log to a file (in a scratch dir) and print its path so the agent can drill in with `xread` if needed. Include tests using canned tool outputs as fixtures.

## 5. `structo` — Big-file shape summarizer

For large JSON/YAML/CSV/JSONL/log files: prints the *schema and shape* (keys, types, nesting, row counts, value distributions, a couple of sample records) instead of the content. Agents frequently `cat` a 2 MB JSON just to learn its structure.

**Bootstrap prompt:**
> Build a CLI tool called `structo` in `tools/structo/`. Given a data file, detect its format (JSON, JSONL, YAML, CSV/TSV, XML, generic log) and print a compact structural summary: for JSON/YAML, an inferred schema with types, optionality percentages, and array lengths, sampling large arrays instead of walking them fully; for CSV, columns with inferred types, null rates, min/max/cardinality, and 3 sample rows; for logs, detected timestamp format, line count, top repeated message templates (cluster by stripping numbers/ids), and first/last lines. Support `--path a.b[0].c` to zoom into a JSON subtree and `--sample N` to control sample size. Stream — never load files fully into memory. Support `--max-tokens N`. Add tests with fixture files of each format.

## 6. `gitbrief` — Git state summarizer

Compact, layered views of git state: a one-screen status+diffstat overview by default, hunk headers on request, full hunks only for named files. Replaces the `git diff` firehose that agents habitually dump into context.

**Bootstrap prompt:**
> Build a CLI tool called `gitbrief` in `tools/gitbrief/`. Default output: current branch, upstream drift (ahead/behind), a merged status+diffstat table (staged/unstaged/untracked, +/- line counts per file), and the last 5 commits as one-liners. `gitbrief hunks [FILE...]` shows diff hunk headers with 1 context line each; `gitbrief show FILE` shows the full diff for one file; `gitbrief log --grep/--author/-n` gives condensed history; `gitbrief pr BASE` summarizes the whole branch vs a base (diffstat + commit list + changed-symbol list using tree-sitter if available). All modes respect `--max-tokens N`. Pure `git` plumbing subprocess calls, no libgit dependency. Test inside a temp repo created by the test suite.

## 7. `factbook` — Persistent per-repo knowledge cache

A store of durable facts an agent learns about a repo ("build with make dev, not npm", "auth logic lives in pkg/auth", "tests need Docker running"), with fast keyword recall. Stops agents from re-deriving the same architecture and gotchas every session — re-exploration is a huge hidden token cost.

**Bootstrap prompt:**
> Build a CLI tool called `factbook` in `tools/factbook/` that manages a per-repo knowledge store in `.factbook/` (one markdown file per fact with name, tags, body, created/updated timestamps, plus an INDEX.md of one-liners). Commands: `factbook add "fact text" --tags build,ci`, `factbook find QUERY` (keyword + tag search over names/bodies, ranked, returns one-liners with `--full` to expand), `factbook brief` (prints the whole INDEX, capped by `--max-tokens N` — designed to be injected at session start), `factbook edit NAME`, `factbook rm NAME`, and `factbook stale` (flags facts referencing files/paths that no longer exist). Keep everything plain markdown so humans can edit it and git can version it. Write tests for add/find/brief/stale.

## 8. `docsnip` — Dependency doc/signature extractor

Answers "what's the signature and behavior of X from library Y" from locally installed packages — extracting just the relevant docstring/type signature/README section — instead of the agent web-searching or reading entire vendored sources.

**Bootstrap prompt:**
> Build a CLI tool called `docsnip` in `tools/docsnip/`. Given a symbol query like `docsnip requests.Session.request` or `docsnip --npm express Router`, locate the installed package (Python: importlib + inspect to get the real signature and docstring without executing arbitrary code where possible; Node: resolve via node_modules and extract from .d.ts files preferentially), and print: full signature, parameter list with types, the docstring/JSDoc, and where it's defined (path:line). Add `docsnip --readme PACKAGE --section usage` to extract one section of a package README. Cache extraction results in `~/.cache/docsnip/` keyed by package version. Support `--max-tokens N`. Handle "not installed" and "symbol not found" with short actionable errors. Tests against a fixture virtualenv/node_modules.

## 9. `testmap` — Change-to-test scoper

Maps changed files to the minimal set of tests that exercise them, so agents run (and read output from) 12 tests instead of 1,200. Pairs with `runlite`: scope first, distill second.

**Bootstrap prompt:**
> Build a CLI tool called `testmap` in `tools/testmap/`. Given a set of changed files (default: `git diff --name-only HEAD` plus untracked), find the tests likely to cover them using layered heuristics: (1) naming conventions (`foo.py` → `test_foo.py`, `foo.ts` → `foo.test.ts`/`foo.spec.ts`), (2) static import analysis — parse test files (tree-sitter or language-native AST) and match imports against changed modules, transitively up to depth `--depth N` (default 2), (3) optional recorded coverage map (`testmap record -- pytest` runs the suite under coverage and writes file→tests rows into the shared `.repoindex/index.db` `tests` table with source=coverage, for exact lookups later — see tool #13). Output: the test file/node list, one per line, plus a ready-to-run command for the detected framework (`pytest a b`, `npx vitest run a b`, `go test ./pkg/...`). Support Python, JS/TS, Go first. Tests against a fixture repo with known import relationships.

## 10. `tokq` — Token cost meter and context linter

Measures the token cost of anything before it enters context — files, command output, directories — and flags waste (huge files, lockfiles, minified bundles, binary-ish content). Gives both agents and humans the feedback signal every other tool here optimizes against.

**Bootstrap prompt:**
> Build a CLI tool called `tokq` in `tools/tokq/`. Core: `tokq FILE...` prints per-file token estimates and a total; `some-cmd | tokq -` meters stdin; `tokq dir PATH` prints a token-weighted tree (like du but tokens) with the heaviest paths first. Use a real tokenizer if available (`tiktoken` with an o200k-class encoding) and fall back to a bytes/3.7 heuristic, noting which was used. Add `tokq lint PATH...` which flags context-wasteful content: files over a threshold, lockfiles/minified/generated files (by name patterns and long-line/entropy heuristics), and suggests the cheaper tool from this suite (`structo` for data files, `xread` for big sources, `repomap` for directories). Exit nonzero from lint when something exceeds `--budget N` so it can gate scripts. Keep startup under 100ms in the fallback path. Include tests.

## 11. `callgraph` — Dependency and call-relationship explorer

Answers "what does X call, and what calls X" in one shot — callees, callers, and an optional depth-limited tree. Agents waste enormous context discovering relationships manually: grep for a name, read three files, grep again. This collapses that whole loop into one cheap, citable query.

Example:

```
$ callgraph auth.login
auth.login()  # src/auth/core.py:42
  calls:
    validate_credentials()   src/auth/core.py:88
    get_user()               src/db/users.py:31
    issue_token()            src/auth/tokens.py:12
  called by:
    api/login.py:27
    cli/auth.py:105
    tests/test_login.py:14

$ callgraph auth.login --depth 2 --callers
api/login.py:27
  -> auth.login()
     -> validate_credentials()
     -> db.lookup_user()
```

**Bootstrap prompt:**
> Build a CLI tool called `callgraph` in `tools/callgraph/`. Given a symbol (`callgraph auth.login`, resolving dotted/qualified names and bare names with a disambiguation list if multiple match), print: where it's defined (path:line), its direct callees with locations, and its callers with locations. Support `--depth N` to expand the tree in either direction (`--callers` / `--callees`, default both at depth 1) with cycle detection (`(cycle)` marker) and per-node dedup. Implementation: this is a pure query layer over the shared `.repoindex/index.db` built by `repoindex` (tool #13) — walk the `refs` table (kind=call) joined against `symbols`; do not parse source yourself. If the index is missing or stale, run `repoindex update` automatically first. Surface the index's confidence column: mark dynamic/duck-typed call edges with `?`. Every line must carry a `path:line` reference so an agent can jump straight to `xread`. Support `--max-tokens N` (shrink by reducing depth, then collapsing sibling lists to counts). Tests against a fixture repo with known call relationships, including a cycle and an ambiguous name.

## 12. `codediff` — Semantic diff summarizer

Explains a diff at the level agents (and reviewers) actually think: behavior changes, API surface changes, removals, and a risk assessment — instead of raw hunks. `gitbrief` tells you *what files* changed; `codediff` tells you *what the change means*. Far more useful per token than hunks for review, commit messages, and deciding what to test.

Example:

```
$ codediff HEAD~1
Behavior changes
  ✓ login() now validates MFA                    src/auth/core.py:42
  ✓ retry count increased 3 → 5                  src/http/client.py:17
  ✓ timeout default 30 → 60                      src/http/client.py:19

API changes
  + LoginOptions.retry_limit                     src/auth/options.py:8

Removed
  - validate_token()  (was deprecated)           src/auth/legacy.py

Risk: HIGH
  - touches authentication path
  - touches public API
  - no matching tests changed
```

**Bootstrap prompt:**
> Build a CLI tool called `codediff` in `tools/codediff/` that summarizes a git diff semantically (default: working tree vs HEAD; also accept a ref, range, or `--staged`). Static-analysis first: parse before/after versions of each changed file (reuse `repoindex`'s extraction library for the "after" side and its tree-sitter machinery for the "before" side) and diff at the symbol level to classify changes into sections — **API changes** (added/removed/renamed public symbols, signature changes with old → new), **Behavior changes** (modified function bodies: report the function, and detect cheap high-signal patterns like changed literal/default values `3 → 5`, added/removed conditionals, added/removed calls), **Removed** (deleted symbols, noting deprecation markers), and **Mechanical** (formatting-only, comment-only, import reshuffles — collapsed to one line). Then compute a **Risk** rating (LOW/MED/HIGH) from explainable heuristics: sensitive-path keywords (auth, crypto, payment, migration — configurable in `.codediff.toml`), public-API surface touched, size of behavior delta, and whether test files changed alongside the source they cover (query the `tests` table in `.repoindex/index.db` if present). Every finding carries a `path:line` reference. Add optional `--llm` mode that sends the compact symbol-level delta (never the raw diff) to an LLM for a one-paragraph narrative, off by default so the core tool stays deterministic and offline. Support Python, JS/TS, Go first, `--max-tokens N`, and a `--json` output for tooling. Tests: fixture repos with crafted diffs covering each section, including a rename, a default-value change, and a formatting-only change that must land in Mechanical.

## 13. `repoindex` — Shared repo-wide symbol database

The foundation the relationship tools stand on: one incremental, tree-sitter-built SQLite database at `.repoindex/index.db` holding symbols and *every* cheap-to-extract relationship — not just calls. Parse the repo once; `callgraph`, `codediff`, `testmap`, `repomap`, and the whole query pack (#14) become SQL queries over the same index instead of five tools each re-parsing the tree.

Schema (tables, one SQLite file — joins across relationships are the whole point):

| table | contents |
|---|---|
| `files` | path, language, mtime, content hash |
| `symbols` | qualified name, kind (func/class/method/const/type), file, line span, visibility/exported |
| `refs` | from-location → to-symbol, kind (`call`, `read`, `write`, `type-use`), confidence |
| `imports` | file → module/symbol, alias, line |
| `inherits` | child symbol → parent symbol |
| `implements` | symbol → interface/protocol symbol |
| `tests` | test symbol/file → covered file/symbol, source (`convention`, `import`, `coverage`) |

**Bootstrap prompt:**
> Build a CLI tool called `repoindex` in `tools/repoindex/` that maintains a repo-wide code intelligence database in `.repoindex/index.db` (single SQLite file). Commands: `repoindex build` (full index), `repoindex update` (incremental — re-extract only files whose mtime/hash changed, in one transaction; fast enough to run implicitly before every query), `repoindex status` (freshness, per-language file/symbol counts), and `repoindex sql "SELECT ..."` (read-only raw query escape hatch, column-aligned output). Extract with tree-sitter into these tables: `files` (path, lang, mtime, hash), `symbols` (qualname, kind, file, line span, exported/visibility), `refs` (from location → to symbol, kind: call/read/write/type-use, confidence: resolved/heuristic), `imports`, `inherits`, `implements`, and `tests` (test → target mappings from naming conventions and imports, with a `source` column so `testmap` can later add coverage-recorded rows). Resolve references via imports plus scope-aware name matching; store unresolved/dynamic edges with confidence=heuristic rather than dropping them. Ship the extraction logic as an importable library (`repoindex.extract`) so `codediff` can parse before/after file versions with the same machinery. Support Python, JS/TS, Go first; design the extractor interface so adding a language is one file. Add `.repoindex/` to a generated `.gitignore` entry. Tests: fixture repo verifying each table's rows, plus an incremental-update test proving an untouched file is not re-parsed.

## 14. `rq` — Query pack over the index

Once the index exists, a family of high-value questions becomes almost free — each is a SQL query plus formatting. Ship them as subcommands of one thin CLI (`rq`, "repo query") so adding the next one is ~20 lines.

```
rq whouses LoginManager     # every reference to a symbol, grouped by kind (call/read/type-use)
rq implements AuthBackend   # all implementations of an interface/protocol
rq inherits BaseModel       # subclass tree
rq impact LoginManager      # blast radius: transitive dependents + the tests that cover them
rq publicapi [PKG]          # exported surface: symbols visible outside the package
rq deadcode                 # exported-or-not symbols with zero inbound refs (with confidence caveats)
rq findcycles               # import/call cycles between modules
rq untested                 # public symbols with no row in the tests table
```

**Bootstrap prompt:**
> Build a CLI tool called `rq` in `tools/rq/` — a subcommand-per-question query layer over `.repoindex/index.db` (auto-run `repoindex update` first). Implement: `whouses SYMBOL` (all inbound refs grouped by kind, each with path:line), `implements INTERFACE` and `inherits BASE` (from the implements/inherits tables, as an indented tree), `impact SYMBOL` (transitive closure over inbound refs + inherits, capped by `--depth`, ending with the covering tests from the tests table — this is the "what breaks if I change this" tool), `publicapi [PATH]` (exported symbols with signatures), `deadcode` (symbols with zero inbound refs, clearly flagging that heuristic/dynamic refs lower confidence, `--include-exported` off by default), `findcycles` (SCCs over the module import graph, smallest cycles first), and `untested` (public symbols with no tests-table coverage). Shared plumbing: every subcommand takes `--max-tokens N` (collapse leaf lists to counts first) and `--json`; every output line carries path:line. Keep each subcommand a small function returning rows from one or two SQL queries — the point of this tool is that the marginal question costs ~20 lines. Tests per subcommand against the same fixture repo `repoindex` uses, including a known cycle and a known-dead symbol.

---

## Suggested build order

1. **`tokq`** first — it's small and lets you measure the savings of everything else.
2. **`runlite`**, **`sgrep`**, **`xread`** — the everyday workhorses; biggest immediate savings.
3. **`repomap`**, **`gitbrief`**, **`structo`** — orientation tools.
4. **`repoindex`** — the shared symbol database; the foundation everything relationship-shaped queries.
5. **`callgraph`**, **`rq`** — thin query layers over the index; high leverage, low cost once #4 exists.
6. **`testmap`**, **`docsnip`**, **`factbook`**, **`codediff`** — deeper integrations that compound over time (`testmap` writes coverage rows into the index's `tests` table; `codediff` reuses `repoindex`'s extraction library and the `tests` table).

Once two or three tools exist, add a top-level `README.md` documenting the shared conventions (`--max-tokens`, output style) and a snippet for agents' project instructions (e.g. CLAUDE.md) telling them to prefer these tools over `cat`, raw `grep`, and raw test runs.
