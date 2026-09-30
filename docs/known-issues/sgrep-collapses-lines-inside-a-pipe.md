# sgrep collapses similar lines even when its output is piped, corrupting counts

**STATUS: open.** Filed 2026-09-30 from a bible-atlas session.

## What happened

The guard hook refused `cat LOG | grep PATTERN | awk … | uniq -c` and then
`grep` over the file, and pointed to `sgrep`. The goal was to tally the HTTP
status of every `PATCH /api/v1/sermons/…` line in a `next dev` log, 13 lines in
all. `sgrep` has no `-o`, and when it was used as the first stage of the pipe:

```
$ sgrep -n "PATCH /api/v1/sermons" "$TEMP/ba-dev.log" | sed -E 's/.* ([0-9]{3}) in .*/\1/' | sort | uniq -c
      1 (+6 more similar)
      7 200
      1 == C:/Users/.../ba-dev.log (13 matches) ==
```

Six of the 13 lines were folded into a `(+6 more similar)` marker, and the file
header became a data row, so the count read 7 where it should have read 13.
Nothing in the output flags it as wrong. A reader who does not already know
there were 13 matches takes 7 for the answer.

## Also seen in the same session

The hook let `cat "$TEMP/ba-dev.log" | grep -i -E "error|…" | head` run once,
then refused `cat "$TEMP/ba-dev.log" | grep … | awk … | sort | uniq -c` against
the same file, saying `cat FILE` dumps the whole file. The rule for when a pipe
out of `cat` is acceptable looks inconsistent from the caller's side.

## Expected

When stdout is not a TTY, or when `--no-collapse` is implied by a pipe, sgrep
emits raw `path:line:text` rows with no headers or fold markers, so it can
replace `grep` as a pipe stage. Otherwise, the hook's message should say to use
`--no-collapse` for counting. `-o` (only-matching) would cover the tally case
directly.

## Workaround

`sgrep --no-collapse`, and strip the `==` header line, before piping into
`sort | uniq -c`.
