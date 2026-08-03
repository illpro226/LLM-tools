# gitbrief hook: denies `git log --oneline -N` for tiny N

**FIXED 2026-08-02 (guard hook `~/.claude/hooks/llm-tools-guard.py`)**

Both halves are addressed. The `git log` carve-out now allows any invocation
bounded small by construction — `-1`/`-n 1` as before, plus `--oneline` with
an explicit count of 10 or fewer; bare `git log --oneline` and counted-but-
unformatted `git log -5` stay denied, since neither is bounded cheap. Count
flags are now read from the `git log` sub-command's own arguments rather than
from anywhere in the command string, so a later `head -1` no longer whitelists
an unbounded log. Separately, every shell deny on a compound command now says
outright that nothing in the call ran and that any chained commit/push/build
did not happen, ending the silent-no-op failure mode below.

**Date:** 2026-07-30
**Tool:** gitbrief PreToolUse hook
**Status:** Fixed

## What I tried

Orienting at the start of a session, as the first command in the repo:

```
git log --oneline -5 && ls
```

Denied:

> Raw `git log` output is token-heavy. Use the LLM-tools suite instead:
> `gitbrief hunks [FILE...]` or `gitbrief pr BASE` for diffs, `gitbrief log`
> for history, `gitbrief show FILE` for one file's diff.
> (`git log -1 ...` is allowed for plumbing lookups.)

## Expected

`--oneline -5` is five lines of `<sha> <subject>` — roughly 40 tokens, and
bounded by construction. The rule exists to stop unbounded `git log` dumps
(full messages, diffs, hundreds of commits), which this is not. The carve-out
already recognises the principle by allowing `git log -1`; the cost difference
between `-1` and `-5` is four lines.

Worth noting the denial was also redundant in context: the session's git status
preamble already listed the five most recent commits, so the right answer was
"you already have this", not "use gitbrief".

## Impact / workaround

`gitbrief log` does the job and is the better habit for real history reading,
so the cost is one round trip, not a blocked task. Filing as recorded friction.

A narrow fix would be to extend the existing `-1` carve-out to `--oneline`
with an explicit small `-N` (say N ≤ 10), which stays bounded and cannot be
widened into a dump — `git log --oneline` with *no* count should stay denied,
since that is unbounded and is the actual failure mode the rule targets.

## 2026-07-31: the denial takes the whole compound command with it

Hit a sharper version of this while committing. The command was:

```
git add CLAUDE.md && git commit -q -F - <<'EOF' ... EOF
git push -q origin main && git log --oneline -3
```

The trailing `git log --oneline -3` tripped the rule, and the hook denies
the **entire Bash call** — so the add, the commit and the push never ran
either. The failure is silent in the sense that matters: the denial message
talks only about `git log`, so the obvious reading is "the log part was
refused", not "none of your work happened". It is easy to move on believing
a commit exists when it does not.

This raises the priority of the carve-out above, but the deeper point is
separate from the `-N` question: a *deny* verdict on a compound command is
all-or-nothing, and the message should say so. Either the reason line should
name the consequence ("denied — no part of this command ran; the match was
`git log --oneline -3`"), or the guidance should be to run the flagged
sub-command separately. Cheap to fix in the message text, and it removes a
class of silent no-ops that has now bitten once.

Workaround in the meantime: never chain a possibly-denied read command onto
a state-changing one. Commit and push on their own line, orient separately.
