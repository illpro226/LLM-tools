# sgrep context lines repeated the file path, costing more than raw rg

**RESOLVED 2026-08-06 (sgrep v0.4.0).** `-C` context lines now carry a bare
right-aligned line number instead of the full path, under a block header
that already names the file; match lines keep `path:line:`. Measured -23%
output on context searches. INVARIANTS.md amended to say the `path:line`
rule covers lines that make a claim, which a context line does not.

**Date:** 2026-08-06
**Tool:** sgrep

## What happened

`savings_record.md` showed `sgrep` as the most-called tool in the suite
(677 calls) and very nearly the least profitable: ~42 tokens saved per
credited call, ~12k total, against `xread`'s ~4,035/call.

Breaking the credited rows down by sign explained it. Of 297 credited
calls, **193 printed more bytes than the raw `rg` they replaced** — 79,108
bytes of loss, offset by 124,176 bytes across the 104 wins. The tool that
exists to replace grep dumps was, on most individual calls, a grep dump
with overhead.

The overhead was the `path:` prefix on every context line. With `-C 3` a
block has roughly six context lines per match, each paying the file path
again, inside a `== path (N matches) ==` header that had just named the
file. `rg` searching a single file prints no path at all, so the whole
prefix was pure loss there.

Worst measured losses (from `.savings/events.jsonl`):

```
-10286   "EntityHeader" src -C 4 --max-tokens 3000
 -8616   'queryRaw|executeRaw|Prisma\.raw' src/lib -C 6
 -4855   -i "mizpah" . -C 1
```

## Why it survived so long

The per-line `path:line` reference is an INVARIANTS.md rule, so it read as
non-negotiable. But the rule says *every line that makes a claim about
code* — and a context line makes no claim. It is there to situate the
match above it. The invariant was being applied past its own scope.

## Fix

Context lines print as a bare right-aligned line number (`  248-  text`).
Match lines keep the full `path:line:` and stay followable with `xread`,
so the invariant holds where it actually applies. INVARIANTS.md now says
this outright rather than leaving it to be re-derived.

Measured on four representative searches: 19,732 → 15,174 bytes (-23%). A
`-C 3` search across `tools/` that had been 573 bytes worse than `rg`
became 1,752 bytes better. Single-file searches remain slightly behind raw
`rg` (-156 bytes on one case) because the block header and the match-line
path have no `rg` equivalent; that residual is the invariant's real price
and is left alone.

Two tests pin both halves: `test_context_lines_carry_no_path_prefix` and
`test_match_lines_still_carry_path_and_line`.
