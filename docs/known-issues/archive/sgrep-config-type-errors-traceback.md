# sgrep: a mistyped .sgrep.toml value tracebacks or is misread

**RESOLVED 2026-10-09 (sgrep v0.7.0).** Weights must be numbers and classes lists of strings; both are exit-2 config errors.

Filed 2026-10-08 from a full-suite review session. Minor.

## What broke

```
# .sgrep.toml
[weights]
src = "high"
```

```
$ sgrep needle
Traceback (most recent call last):
  ...
ValueError: could not convert string to float: 'high'
```

`[classes] generated = "dist/*"` (a string where a list belongs) does not
fail at all. `list("dist/*")` turns it into the six one-character globs
`d`, `i`, `s`, `t`, `/`, `*`, and the `*` matches every path.

## Why

`load_config` validates the class *names* but not the value types:
`float(value)` is not guarded, and `list(...)` accepts any iterable.

## What changed

Not fixed. Expected: raise `SgrepError("config %s: weights.%s must be a
number")` and require `classes.*` to be a list of strings. Both are exit 2
with a `sgrep:` message, like the unknown-class case already is.
