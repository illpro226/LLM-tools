# Line numbers drift on form feeds and Unicode line separators

**RESOLVED 2026-10-09 (xread v0.6.0, repomap v0.5.0, repoindex v0.1.7, codediff v0.6.1, gitbrief v0.4.1).** Every listed site splits on `\r\n|\r|\n`, each pinned by a form-feed test. The helper is still one copy per tool (single-file tools); the shared-code suggestion stays in STATUS.md Next.

Filed 2026-10-08 from a full-suite review session.
Affects xread (confirmed). The same pattern is in repomap, codediff,
gitbrief `pr`, and repoindex (not separately reproduced).

## What broke

A Python file with a form-feed (`^L`) page break on line 2:

```
import os
^L
def target():
    return 1
```

```
$ xread ff.py --symbol target
== ff.py:3-4 ==

def target():
```

The header correctly says 3-4 (ast's numbering), but the body is off by one.
It prints a blank line and the `def`, and drops `return 1`. A `U+2028`
inside a string literal does the same. Every symbol after the character is
shifted, so `--symbol`, `--lines` and `--scope` all serve the wrong lines.
An agent copying that excerpt into an Edit gets a mismatch.

## Why

`source.splitlines()` also splits on `\f`, `\v`, `\x1c-\x1e`, `\x85`,
`U+2028` and `U+2029`. `ast` line numbers, git hunk headers and every
editor count only `\n` / `\r\n` / `\r`. The tools index one numbering with
the other. Form feeds are a real convention in older Python and GNU-style C
source, and `U+2028` shows up in JS string data.

## What changed

Not fixed. Expected: split with `re.split(r"\r\n|\r|\n", source)` (dropping
a trailing empty element), or `source.split("\n")` after normalizing CRLF,
in xread `load`, repomap `scan`, codediff `analyze_file` / `_mechanical_kind`,
gitbrief `_ts_symbols`, and repoindex `_extract_ts` / `_extract_go`. A shared
helper would stop the copies drifting again.
