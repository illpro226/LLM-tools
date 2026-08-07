# 0008: Remove the callgraph/docsnip/factbook scaffold directories

Status: Accepted (2026-08-07)

## Decision

Delete `tools/callgraph/`, `tools/docsnip/`, and `tools/factbook/` from
the repo. This reverses the consequence recorded in 0003 ("the
`tools/factbook/` and `tools/docsnip/` scaffold directories stay as they
are ... they document the specs a revival would start from").

## Why

The repo went public (see the LLM-tools-public-and-docs work, 2026-08-07).
A visitor landing in `tools/` sees 14 directories against a README that
says "eleven tools, all implemented" — three of which are doc-only
scaffolds with no code and no tests. That reads as unfinished or
misleading rather than as a deliberate, recorded deferral. The doc-set
scaffolds were meant to give a revival a starting point, but 0001/0002/
0003 already contain the specs and rationale in full; the directories
added confusion without adding information a revival couldn't get from
the decision records themselves.

## Consequences

- `tools/callgraph/`, `tools/docsnip/`, `tools/factbook/` no longer exist.
- 0001, 0002, and 0003 are unchanged — they remain the historical record
  of why each was deferred/merged, and are still where a revival starts.
- References to these three tools elsewhere in the repo (decision
  records, other tools' PRDs citing them for scope contrast) are left as
  historical text; only current-state claims that depended on the
  directories existing (root `README.md`, `docs/PRDs/README.md`,
  `tools/tool_docs.md`, root `CLAUDE.md`) were updated.
- Revival condition is unchanged from 0003: a new decision record citing
  recorded `docs/known-issues/` evidence. That record should recreate
  the tool's directory from scratch rather than expect scaffold files to
  still be here.
