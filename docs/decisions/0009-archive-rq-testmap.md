# 0009: `rq` and `testmap` are archived, not just retired

Status: Accepted (2026-08-07)

## Decision

`tools/rq/` and `tools/testmap/` move to `archive/rq/` and
`archive/testmap/`. All wiring that made them reachable as suite tools is
removed: the `bin/rq`, `bin/rq.cmd`, `bin/testmap`, `bin/testmap.cmd`
shims; their entries in the guard hook's `SUITE_TOOLS` tuple
(`~/.claude/hooks/llm-tools-guard.py`); and current-state claims in root
`README.md`, `docs/PRDs/README.md`, and `tools/tool_docs.md`.

This is the "further decision" that 0006 said deletion would require.
Code and tests are preserved under `archive/` rather than deleted outright
— `python -m pytest` still runs there — but neither tool is installed,
documented as available, or logged going forward.

## Why

0006 (2026-08-06) retired both from guidance on one month of evidence: `rq`
called twice, `testmap` never. `savings_record.md` as of this decision
still shows the same counts a day later — no unprompted calls arrived in
the interim, and 0006's own revisit condition ("called unprompted more
than a handful of times in a month") did not fire. Keeping working, tested
code on disk that nothing points to has an ongoing cost 0006 already
named: unused surface area still has to be maintained, documented, and
kept in an agent's head. With the retirement holding up and no new signal
favoring either tool, the further decision 0006 deferred is made here.

`repoindex` is unaffected — it remains the library `codediff` calls
directly, not a retired CLI, per 0006's own carve-out.

## Consequences

- `tools/rq/`, `tools/testmap/` no longer exist; `archive/rq/`,
  `archive/testmap/` hold the same code and tests, unmaintained.
- `bin/` no longer ships `rq`/`testmap` shims. Calling either name is a
  plain "command not found," not a guard-hook denial.
- The guard hook stops tracking calls to either name; `savings_record.md`
  keeps its historical rows for them (2 and 0 calls respectively) as of
  this decision, but neither can accrue further logged calls.
- `START.md`'s bootstrap prompts for `testmap` (#9) and `rq` (#14), and
  historical decision records (0001, 0004, 0005, 0006), are left as
  written — same precedent as 0008 for `docsnip`/`factbook`: only
  current-state claims get updated, not the historical trail.
- `INVARIANTS.md`'s relationship-tool clause and root `CLAUDE.md`'s
  gotcha table lose their `rq`/`testmap` references, since neither is a
  live relationship tool anymore; `repoindex`'s "preserves `testmap
  record` coverage rows" note stays, since that schema behavior is
  `repoindex`'s own and doesn't depend on `testmap` existing as a caller.

## Revisit if

A revival needs a new decision record citing recorded
`docs/known-issues/` evidence, same bar as 0003/0008 set for
`docsnip`/`factbook`. That record should restore from `archive/` rather
than starting over, since the code and tests are kept intentionally.
