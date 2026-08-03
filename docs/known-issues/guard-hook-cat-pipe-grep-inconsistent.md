# guard hook: `cat FILE | grep` allowed once, denied the next time

**Date:** 2026-08-02
**Tool:** LLM-tools guard hook (`cat` rule)
**Status:** Open

## What I tried

I needed a list of line numbers matching a pattern across a few source files —
`sgrep` collapses repeated similar matches ("(+38 more similar)"), and the Grep
tool refuses content mode over a directory, so the piped form was the way to get
a complete list.

This ran fine:

```
cat prisma/schema.prisma | grep -n "^model \|^  archived "
```

Immediately afterwards, this was denied:

```
cat src/lib/search.ts | grep -n "archived"; echo ---; cat src/lib/related.ts | grep -n "archived"
```

> `cat FILE` dumps the whole file. Use `xread FILE --symbol NAME | --query
> "…"` … or a bounded Read with offset/limit.

Both commands pipe every `cat` straight into `grep`; nothing in either would
print a whole file. The difference between them is the number of `cat`
invocations and the `;` separators, so the rule looks like it matches a single
`cat FILE` occurrence and is defeated (or confused) by a second one on the same
line — permissive in the wrong direction on the first form, restrictive on the
second.

## Expected

One consistent verdict. The reason the rule exists — a whole file landing in
context — is absent in both cases, so the honest answer for `cat F | grep …` is
allow. Whatever the ruling, it should not depend on how many files are on the
line.

## Impact / workaround

One round trip each time, plus the guessing about which shape will pass. The
reliable fallbacks are the Grep tool against a single file path (content mode
is permitted there) or `sgrep` with a narrower pattern; both work, and the Grep
tool is the better habit.

Worth noting the pressure that produced the `cat | grep` in the first place:
`sgrep` deliberately collapses similar matches, which is right for orientation
and wrong when the task is "edit every one of these 40 sites" and I need the
full list. A `--no-collapse` or `--all` flag on `sgrep` would remove the reason
to reach for `cat` at all.
