# 0004: Minimal MCP adapter exposing the core four tools

Status: Accepted (2026-07-11)

## Context

Adoption evidence shows the suite loses to built-in `Read`/`Grep` at the
moment of the tool call even when it is on PATH, known, and explicitly
preferred in instructions. The record:

- `docs/known-issues/agent-defaults-to-builtins-mid-task.md` — three
  lapses in one session (CortexLink, 2026-07-11), two immediately after
  the agent acknowledged the previous one; plus a corroborating instance
  in this repo while the agent was analyzing that very issue file.
- The same evidence shows what works: the PreToolUse guard hook
  (`git diff`/`git log` → gitbrief) had zero lapses in the same session.
  Mechanical presence at the decision point beats session-start prose.

The hook fix (guard v2, 2026-07-11: grep/cat/inline-JSON shell denials,
Grep-tool content-mode denial, tighter Read limits, one-per-session
PostToolUse nudge) covers Claude Code. It covers nothing else: hooks are
a Claude Code feature. Codex and other MCP-speaking agents have only
AGENTS.md prose plus PATH — the exact combination the evidence shows
failing under task pressure.

A Model Context Protocol server changes where the tools live: instead of
bare names an agent must *recall* mid-Bash, they become first-class
entries in the tool list the model sees at every decision point,
structurally adjacent to `Read` and `Grep`. Agents pick from the menu in
front of them far more reliably than they recall instructions about
shell commands.

## Relation to prior decisions

- **0003 (list closed) still holds.** The adapter is not a twelfth tool;
  it is a delivery surface for existing tools, with no logic of its own.
  The bar 0003 sets — revival only via a decision record citing recorded
  known-issue evidence — is met here by the two known-issue files above.
- **The Codex-issue shelving is superseded on its own terms.** The MCP
  adapter idea was shelved in
  `docs/known-issues/archive/codex-ignores-agents-md-tool-section.md` because
  that problem turned out to be PATH visibility, with revival gated on
  "adoption regresses in sessions with a verified PATH". The
  agent-defaults-to-builtins issue is exactly that: a verified-PATH
  session where adoption regressed mid-task.

## Decision

Build a minimal MCP stdio server exposing the **core four** as MCP
tools, and only those:

- `xread` — targeted file excerpts (symbol / query / headings / lines)
- `sgrep` — token-budgeted content search
- `structo` — schema/shape of data files
- `gitbrief` — layered git views

Constraints:

- **Thin passthrough.** Each MCP tool shells out to the existing CLI and
  returns its stdout verbatim. No new logic, no reformatting, no state.
  Behavior differences between the CLI and the MCP surface are bugs.
- **Tight schemas.** Tool descriptions and parameter schemas are written
  for token cost the way the tools' own output is: the four schemas
  together should stay well under ~1k tokens, since they ride in every
  request. The remaining seven tools are deliberately excluded — they
  are either session-rare (`repomap`, `repoindex build`, `codediff`,
  `tokq`) or already index-mediated (`rq`, `testmap`), and their bare
  names remain available; the adapter can add a tool later only if a
  known-issue file records the mid-task lapse pattern for it.
- **Same invariants.** Deterministic plain-text output, `--max-tokens`
  honored, offline, fail with the CLI's own exit text rather than an
  adapter-invented message.
- Lives in `mcp/` at the repo root (it spans tools, so it is not a
  `tools/<name>/` entry), stdlib-plus-nothing if feasible, registered in
  agents' MCP config by absolute path.

## Consequences

- Non-Claude agents with MCP support get decision-point visibility of
  the core four without hooks.
- Claude Code gets belt (hook denials) and suspenders (menu adjacency);
  the hook remains the enforcement layer, the adapter the salience layer.
- Token cost of four schemas per request is accepted; it is bounded by
  the tight-schema constraint and repaid by a single avoided whole-file
  read.
- AGENTS.md and the root CLAUDE.md gain a short note pointing MCP-capable
  agents at the adapter once it ships.
