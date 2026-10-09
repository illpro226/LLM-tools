# runlite trace does not recognize Python exception groups

**RESOLVED 2026-10-09 (runlite v0.6.0).** The border is stripped and each sub-exception becomes an `in group` section; nested groups and never-raised members are handled. Pinned by a real Python 3.14 fixture.

Filed 2026-10-08 from a full-suite review session.

## What broke

The traceback of a real `raise ExceptionGroup("batch", [ValueError(...),
KeyError(...)])` under Python 3.11+:

```
$ python eg.py 2>&1 | runlite trace
# runlite trace: no recognized stack trace [input 566 B]
# exit 1
```

Exception groups are what `asyncio.TaskGroup` and `trio`/`anyio` raise, so
this is the shape of most modern async failures.

## Why

Exception-group tracebacks are drawn with a box border. The header is
`  + Exception Group Traceback (most recent call last):` and every frame
line starts with `  | `. `_PY_START` requires `Traceback (most recent call
last):` at column 0, and `_PY_FRAME` requires the line to start with
whitespace and then `File`, so neither matches anything.

## What changed

Not fixed. Expected: strip the `+`/`|` border prefix before parsing, treat
`Exception Group Traceback` as a trace start, and render the
`+---- N ----` sub-exceptions as sections (kind `"in group"`).
