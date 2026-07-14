# guard hook: `2>/dev/null` bypassed the `cat` deny check

**FIXED 2026-07-13.** `check_shell`'s exemption for legitimate `cat file >
out.txt` redirects tested `">" not in command`, which also matches
`2>/dev/null` (stderr suppression only). Any `cat FILE 2>/dev/null` therefore
skipped the deny and dumped the whole file straight into context — exactly
the failure mode `agent-defaults-to-builtins-mid-task.md` describes, except
here the agent *did* reach for `cat` deliberately and the hook silently
failed to catch it rather than the agent choosing not to use the suite.

Caught live 2026-07-13: `cat ~/.claude/settings.json 2>/dev/null` in a Claude
Code session went straight through. The user asked "how come you didn't use
[the suite]" and that question is what surfaced the bug — worth noting the
mechanism (mechanical enforcement) still depends on a human noticing when it
misfires, since fail-open means a hook bug produces no visible signal at all.

**Fix:** replaced the bare `">" not in command` check with
`STDOUT_REDIRECT_RE = re.compile(r"(?<!\d)>")`, i.e. a `>` not immediately
preceded by a digit. `2>/dev/null` no longer exempts; `> out.txt`, `>>
out.txt`, `&>file` still do. Verified with a small harness feeding synthetic
PreToolUse payloads to the script directly (see conversation
2026-07-13) — `cat FILE 2>/dev/null` now denies, `cat FILE > out.txt`,
`cat FILE >> out.txt`, `cat FILE | wc -l`, and `cat FILE 2>/dev/null | wc -l`
still allow.

Same blind spot may exist anywhere else in the guard that checks for a
literal `>`/`<<` substring instead of parsing redirection properly
(PowerShell's `PS_BOUNDED_RE`/`PS_GC_RE` path doesn't have this exact
exemption, so it wasn't affected here, but any future substring-based
redirect check should reuse `STDOUT_REDIRECT_RE` rather than re-inventing the
same shortcut).
