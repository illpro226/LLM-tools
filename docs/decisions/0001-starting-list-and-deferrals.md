# 0001: Starting list is 10 tools; callgraph merges into rq; three tools deferred

Status: Accepted (2026-07-07)

## Decision

The starting list is finalized at 10 tools, built in waves:

- **Wave 1 (everyday workhorses):** `tokq` (done), `runlite`, `xread`, `sgrep`
- **Wave 2 (orientation):** `repomap`, `gitbrief`, `structo`
- **Wave 3 (index + queries):** `repoindex`, `rq`, `testmap`

Changes from the original 14-tool START.md list:

- **`callgraph` is not a separate tool.** Its own spec calls it "a pure query
  layer over the shared index — do not parse source yourself"; that is the
  definition of `rq` subcommands. Ship as `rq calls` / `rq callers`.
- **`xread` gains a markdown mode** (`--headings` outline, heading-based
  section extraction). Long prose files (READMEs, RFCs, runbooks, private
  infra docs not covered by any docs MCP) are a top token sink with no other
  tool covering them; markdown headings are just another symbol kind.
- **`codediff` deferred.** Highest build cost, and its payoff is mostly human
  review quality, not agent token savings. Its cheap 20% — risk
  classification from repoindex tables — may ship early as `rq risk` if
  pre-commit risk flagging is needed (DEMB/FixPoint use case). Its interface
  requirements on `repoindex.extract` are already pinned
  (tools/repoindex/DECISIONS.md ADR-006) so deferral cannot force a refactor.
- **`factbook` deferred.** Duplicates agent-native memory (CLAUDE.md,
  Claude Code auto-memory) for the primary target agent. Revisit for
  cross-project infra facts or memory-less agents.
- **`docsnip` deferred.** Its actual scope (installed-package signatures) is
  increasingly covered by docs MCP channels. Note: it would NOT cover private
  infra docs either — that gap is served by `sgrep` + `xread` markdown mode
  over local docs directories.

## Rationale

Ranked by where agent tokens actually go: (1) build/test output → runlite,
(2) whole-file reads → xread, (3) exploratory grep loops → sgrep/rq,
(4) repo orientation → repomap, (5) catting data files → structo. Every kept
tool addresses a top-5 sink; every cut tool duplicated agent-native
capability or optimized for humans.

## Consequences

- Deferred is not deleted: a deferred tool's requirements on shared
  infrastructure (schema, extract library) must be pinned before that
  infrastructure is built. See ADR-006 in tools/repoindex/DECISIONS.md.
- The agent-instructions snippet (CLAUDE.md guidance to prefer these tools
  over cat/grep/raw test runs) is a first-class deliverable once Wave 1
  lands — adoption, not capability, determines actual savings.
