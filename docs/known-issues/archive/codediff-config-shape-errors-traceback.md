# codediff: a mis-shaped .codediff.toml tracebacks

**RESOLVED 2026-10-09 (codediff v0.6.0).** A non-table `risk` is an exit-2 error; `sqlite3.Error` in `risk_flags` becomes a note.

Filed 2026-10-08 from a full-suite review session. Minor.

## What broke

```
# .codediff.toml
risk = 5
```

```
$ codediff
Traceback (most recent call last):
  ...
AttributeError: 'int' object has no attribute 'get'
# exit 1
```

## Why

`load_config` catches TOML syntax errors but assumes `risk` is a table:
`data.get("risk", {}).get(...)`. Nearby, an index with an older or broken
schema makes the `SELECT ... FROM tests` in `risk_flags` raise
`sqlite3.Error`, which is not caught either.

## What changed

Not fixed. Expected: `CodediffError(".codediff.toml: [risk] must be a
table")` and exit 2. Catch `sqlite3.Error` in `risk_flags` and turn it into
a note (`test-coverage flags unavailable: <error>`), the same way a missing
index already is.
