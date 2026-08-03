# gitbrief hook: denies `git diff --stat` / `--numstat`

**Date:** 2026-08-02
**Tool:** gitbrief PreToolUse hook
**Status:** Open

## What I tried

Mid-task, wanting to know only how large an accidental reformat was before
deciding whether to revert it (`prisma format` had realigned a 700-line schema):

```
git diff --stat prisma/schema.prisma
git diff --numstat prisma/schema.prisma
```

Both denied:

> Raw `git diff` output is token-heavy. Use the LLM-tools suite instead:
> `gitbrief hunks [FILE...]` or `gitbrief pr BASE` for diffs … (Bounded
> `git log` is allowed for plumbing lookups: `-1`/`-n 1`, or `--oneline` with
> an explicit count of 10 or fewer.)

## Expected

`--stat` and `--numstat` are summary formats, not diff output. For one path
`--numstat` is exactly one line — `<added> <removed> <path>` — and for a whole
working tree it is one line per file. Neither can print a hunk. They are the
same class of bounded-by-construction plumbing the `git log -1` carve-out
already recognises, and cheaper than most of what the suite returns.

The distinction the rule is defending is "does this print patch text", and
these two flags provably do not.

## Impact / workaround

`gitbrief hunks` answers a superset of the question (it prints per-file
`(N hunks, +A -B)` headers), so nothing was blocked — cost is a round trip and
a larger response than the question needed. In this instance I gave up on
measuring and just reverted the file blind, which was the right call anyway.

Narrow fix: allow `git diff` when the argument list contains `--stat`,
`--numstat`, `--shortstat`, or `--name-only`/`--name-status`, none of which can
emit patch text. Read the flags from the `git diff` sub-command's own arguments,
as the `git log` carve-out now does, so a later pipe cannot whitelist a raw
diff.
