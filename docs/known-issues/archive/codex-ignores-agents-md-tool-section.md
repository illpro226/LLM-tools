# adoption: Codex session had no suite on PATH (initially misread as ignoring AGENTS.md)

**RESOLVED (root cause) 2026-07-11:** Codex itself diagnosed it — the
session's environment did not have `bin\` on PATH, so every bare-name
tool call was unresolvable. The user-PATH entry added 2026-07-10 only
reaches shells started after it; confirmed — the Codex window had been
open since before the PATH change. A restart is the entire fix. The original framing of this issue ("Codex ignores the
AGENTS.md tool section") attributed to instruction non-adherence what
was actually an environment gap. The instruction-adherence question is
answered: after a window restart picked up the PATH, Codex saw the
tools and used them for real work — AGENTS.md instructions alone are
sufficient. No MCP adapter needed on current evidence.

- **What broke:** first Codex dogfood session used built-ins throughout;
  zero suite tool invocations.
- **Actual cause:** `bin\` absent from the session PATH. Tools were
  invisible, not declined.
- **Residual instruction finding (weak):** AGENTS.md's fallback line
  ("if a name isn't recognized, call the shim by full path or run
  `python tools\<name>\<name>.py`") was not followed either — but an
  agent fighting PowerShell friction (see session context) may never
  have surfaced the tool names at all. Not strong enough evidence to
  act on.
- **Outcome (2026-07-11):** rerun in a restarted window succeeded —
  Codex resolved the tools by bare name and used them unprompted to do
  work. The MCP-adapter escalation is shelved; it would only revive if
  adoption regresses in sessions with a verified PATH. Lesson for
  future env changes: canary with `command -v xread` before judging
  agent behavior.
