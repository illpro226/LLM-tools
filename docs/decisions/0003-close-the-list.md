# 0003: The suite is complete at 11 tools; factbook and docsnip stay deferred indefinitely

Status: Accepted (2026-07-11)

## Decision

With Waves 1–4 shipped and witnessed and all known issues resolved, the
build list is closed. `factbook` and `docsnip` remain deferred with no
planned wave. There is no Wave 5.

Neither tool clears the bar the eleven built tools did — filling a hole
nothing else covers:

- **factbook.** Its 0001 revisit trigger ("memory-less agents") technically
  fired with the agent-agnostic pivot (AGENTS.md rewrite, bin/ shims), but
  the need was solved another way: the AGENTS.md convention itself. aider,
  codex-style CLIs, and Cursor all read a repo instruction file at session
  start — that *is* the per-repo fact store factbook's spec describes
  (plain markdown, human-editable, git-versioned). What factbook adds on
  top (keyword search, token-capped brief) buys almost nothing at
  realistic fact-store sizes, where the whole file gets injected anyway.
  `stale` detection is the only novel feature, and it is a small script,
  not a tool.
- **docsnip.** One argument survives scrutiny — version-exactness: docs
  MCP channels report what a library's docs say, while docsnip would
  inspect what the *installed* version actually accepts, offline and
  deterministically, including private packages no docs channel knows
  about. But the gap is narrow and has a workable manual path: Python
  `inspect` one-liners and `xread` over `.d.ts` files. 0001's core
  rationale (docs MCP coverage) has strengthened since deferral, not
  weakened.

## Revival condition

Deferred is still not deleted (0001). Either tool comes back only if
dogfooding surfaces a concrete, recurring pain, recorded in
`docs/known-issues/` as it accumulates:

- **docsnip:** repeatedly getting burned by version drift between docs-MCP
  answers and installed-package behavior.
- **factbook:** actually running a memory-less agent on these repos and
  hitting a fact-recall gap AGENTS.md doesn't cover.

Revival needs a new decision record citing those recorded instances — the
same evidence standard 0002 set.

## Consequences

- Effort shifts from building to hardening and adoption: dogfood friction
  fixes, sgrep's missing-`rg` situation, cross-project rollout.
- The `tools/factbook/` and `tools/docsnip/` scaffold directories stay as
  they are (standard doc set, "Scaffold only" STATUS.md) — they document
  the specs a revival would start from.
- START.md's 14-tool list and build order remain historical: 0001 cut it
  to 10 plus merged callgraph, 0002 added codediff, 0003 closes it at 11.
