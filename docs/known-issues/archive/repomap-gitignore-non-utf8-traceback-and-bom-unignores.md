# repomap: a non-UTF-8 .gitignore tracebacks; a BOM'd one un-ignores its first rule

**RESOLVED 2026-10-09 (repomap v0.5.0).** Read as `utf-8-sig` with `errors=replace`. repoindex's `load_gitignore` is fixed separately.

Filed 2026-10-08 from a full-suite review session.

## What broke

A `.gitignore` with one latin-1 byte in a comment (`# café build output`):

```
$ repomap
Traceback (most recent call last):
  ...
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 5
# exit 1
```

A `.gitignore` saved with a UTF-8 BOM (Notepad, PowerShell 5 `Out-File`)
whose first line is `secret.py`:

```
$ repomap
...
  secret.py
secret.py  [refs 0]
  secret.py:1 def s()
```

The first rule is silently dropped, and the file it was meant to hide is
outlined.

## Why

`_load_gitignore` opens with `encoding="utf-8"` and catches only `OSError`.
A decode error is a `ValueError`. A BOM survives as `U+FEFF` at the start
of the first pattern, so that pattern never matches. The rest of the suite
reads with `utf-8-sig` for exactly this reason (structo `TEXT_ENCODING`).
repoindex's `load_gitignore` should be checked for the same pattern.

## What changed

Not fixed. Expected: `open(..., encoding="utf-8-sig", errors="replace")`.
