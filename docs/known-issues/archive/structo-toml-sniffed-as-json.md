# structo sniffs .toml as JSON and returns useless output

**Date:** 2026-08-21
**Tool:** structo
**Resolved:** 2026-08-22 in structo v0.6.0 (ADR-008) — TOML is a supported
format: extension `.toml` or a first-line sniff, parsed with `tomllib`, and
`--path`/`--raw`/`--select` work on it. A sniffed file `tomllib` rejects
falls back to the log summary; a named `.toml` that fails exits 2 with the
parse error instead of guessing.

## What happened

`structo G:/DataExtremes/Code/TOCH_SS/pyproject.toml` reported `format: json (sniffed)`
and emitted a meaningless shape summary:

```
root: int|array|str|float x29  len 1..5  e.g. -, n
  items: int|str|float  e.g. -s, te
```

It appears to have parsed the file as a character/line soup rather than TOML. The
`e.g.` samples (`-s`, `te`) look like fragments of `[project.scripts]` text, not values.

## Expected

TOML is a structured config format squarely in structo's stated remit
("JSON/YAML/JSONL/XML" per CLAUDE.md — TOML is either missing or misdetected).
Expected a table/key summary, and `--path project.scripts` to work.

## Workaround used

Fell back to `sgrep "scripts|toch =|console" pyproject.toml` to locate the
`[project.scripts]` entry point. Worked fine, but a bounded Read would have been
equally good — structo added nothing here.

## Suggested fix

Extension-based detection for `.toml` before content sniffing, and either TOML
support via `tomllib` (stdlib since 3.11) or an explicit "unsupported format"
error instead of a bogus JSON parse. Silently producing confident-looking garbage
is worse than failing.

## Resolution note

The report's guess about the garbage output was wrong in one detail: that
`pyproject.toml` has no `[project.scripts]` table at all (`sgrep scripts`
finds nothing in it). The `-s`/`te` samples were fragments of unrelated
text — which is the point of the bug: the JSON tokenizer is lenient enough
to invent a plausible shape from any character soup, so its output gave no
signal that it had misread the file.
