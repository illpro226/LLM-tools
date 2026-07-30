# gitbrief hook: denies `git log --oneline -N` for tiny N

**Date:** 2026-07-30
**Tool:** gitbrief PreToolUse hook
**Status:** Open

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
