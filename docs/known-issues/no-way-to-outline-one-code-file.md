# No tool outlines a single code file

**Date:** 2026-08-06
**Tool:** xread / repomap (a gap between them)

## What I tried

Getting the symbol list of one unfamiliar Python file — the guard hook, at
8,708 tokens, far too big to read whole — before editing it:

```
$ xread llm-tools-guard.py --headings
xread: llm-tools-guard.py: --headings is for markdown files
       (use `repomap` for code outlines)

$ repomap tools/sgrep/sgrep.py
repomap: not a directory: tools/sgrep/sgrep.py
```

Each tool refers the caller to the other. `xread --headings` says to use
`repomap`; `repomap` accepts only directories.

## When it happens

Every time the question is "what's in this file?" for a code file — the
most common orientation question there is, and the exact precondition
`xread --symbol NAME` depends on, since you cannot ask for a symbol whose
name you don't yet know.

## Expected

One of:

- `xread FILE --headings` works on code, listing symbols with their spans
  (it already builds exactly this map internally to serve `--symbol`), or
- `repomap FILE` accepts a file and outlines just it.

The first is the better home: `--headings` already means "show me the
structure of this file", and xread already parses the file. The error
message even implies the capability exists somewhere.

## Workaround

`repomap` the file's *parent directory* — what this session did. It works
but is the wrong shape: it ranks and collapses across siblings, so the file
you care about may be summarized rather than listed in full, and you pay
for every other file in the directory. On a one-file directory it is fine;
in `tools/repoindex/` it is not.

`sgrep "^def |^class " FILE` is the cheaper hack, but it is a regex guess
per language rather than a parse, and it misses methods, decorators and
anything not at column zero.
