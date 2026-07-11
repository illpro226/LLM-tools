# adoption: Codex session had no suite on PATH (initially misread as ignoring AGENTS.md)

**RESOLVED (root cause) 2026-07-11:** Codex itself diagnosed it — the
session's environment did not have `bin\` on PATH, so every bare-name
tool call was unresolvable. The user-PATH entry added 2026-07-10 only
reaches shells started after it; Codex inherited a stale or different
environment. The original framing of this issue ("Codex ignores the
AGENTS.md tool section") attributed to instruction non-adherence what
was actually an environment gap. The instruction-adherence question is
back to **untested** — it needs a clean rerun in a session where
`Get-Command xread` (or `command -v xread`) actually resolves.

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
- **Follow-ups:**
  1. Rerun the adoption test with a verified environment (have the
     session run `command -v xread` first as a canary).
  2. Consider pinning PATH in Codex's own config so it can't inherit a
     stale environment.
  3. The MCP-adapter escalation stays on the table but should wait for
     the clean rerun — it may be unnecessary.
