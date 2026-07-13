# structo: no way to address a JSONL record by index via --path

**Date:** 2026-07-12
**Tool:** structo
**Status:** Resolved 2026-07-12 in structo v0.2.0 (ADR-004). A leading
`[N]` in `--path` now selects JSONL record N (`--path "[742].message.content"`
works), and `--raw` prints the exact value at `--path` — strings verbatim,
everything else as JSON — so extraction no longer needs a hand-written
script.

## What I tried

Extracting one record (and a subfield of it) from a Claude Code session transcript (`*.jsonl`, 743 lines):

```
structo file.jsonl --path "[742].message.content"
structo file.jsonl --path "[745]"
```

Both fail with `structo: --path not found in <file>`.

## Expected

Some syntax to zoom into record N of a JSONL file, e.g. `--path "[742]"` or a `--line N` flag, then continue with the normal `A.B[0].C` path inside that record.

## Impact / workaround

Had to fall back to a Python script to pull tool_use inputs out of a transcript (recovering a lost file write). Also note: structo prints schema/shape only — there's no mode to print the raw *value* at a path, which is what recovery/extraction tasks need. A `--raw`/`--value` flag would make it usable for "give me this one string field" without hand-written scripts.
