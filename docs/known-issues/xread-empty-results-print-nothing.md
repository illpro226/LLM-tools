# xread prints nothing at all for empty results

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

```
$ xread ff.py --query zzzznothere
                                   # no output, exit 0

$ xread nodefs.py --headings       # a script with no def/class
                                   # no output, exit 0

$ xread ff.py --query return --top -1
                                   # no output, exit 0
```

Empty stdout with exit 0 does not tell the caller whether the query missed,
the file has no symbols, or the tool broke. Every other tool in the suite
says so in words: sgrep exits 1, gitbrief prints `no changes`, and runlite
trace prints `no recognized stack trace`.

## Why

`resolve_query` returns `[]` when no block scores, `cmd_headings` returns
`[]` for a file with no symbols, and `main` prints only `if lines:`.
`--top` is not validated: `scored[:-1]` drops the last-ranked block, and
`scored[:0]` drops every block.

## What changed

Not fixed. Expected: `no blocks match "zzzznothere" in ff.py` (exit 1, like
sgrep), `nodefs.py: no symbols (try --lines or --query)`, and reject
`--top < 1` at parse time.
