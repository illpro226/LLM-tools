# adoption: Codex ignores the AGENTS.md tool section entirely

**Status: OPEN (2026-07-11).**

- **What breaks:** running Codex on another repo whose AGENTS.md carried
  the LLM-tools section, it used built-ins (whole-file reads, raw
  grep/diff) and never invoked a suite tool. The instruction channel —
  the only channel Codex currently has to the suite — produced zero
  adoption in a real session.
- **When it happens:** any Codex session; there is no hook system to
  enforce redirection the way Claude Code's PreToolUse guard does, so
  a "prefer these tools" section competes with the model's trained
  defaults and loses under task pressure.
- **Expected behavior:** the agent reaches for `xread`/`sgrep`/`gitbrief`
  for the jobs the table maps.
- **Workarounds / candidate fixes, in escalating strength:**
  1. Confirm AGENTS.md was actually loaded (session log) before blaming
     wording; test with the section moved to the top, imperative,
     prohibition-first ("Do NOT read whole files — run `xread`...").
  2. Mirror the section into `~/.codex/AGENTS.md` so it applies globally.
  3. An MCP adapter exposing the high-value tools as native tool schemas
     — tool-list visibility does not depend on instruction adherence.
     This is adoption infrastructure, not a 12th tool, but per 0003 it
     should get its own decision record before being built.
