# structo --path on a bool leaf prints the type, not the value

**RESOLVED 2026-10-09 (structo v0.7.0).** Bools carry an example value (`root: bool  e.g. true`), at a leaf and on a parent object.

Filed 2026-09-30 from a home-folder session (iLO 4 login triage).

## What broke

Reading one boolean from a Redfish JSON response:

```
$ structo acct2.json --path Oem.Hp.Privileges.LoginPriv
structo acct2.json — format: json (extension), path Oem.Hp.Privileges.LoginPriv

root: bool
```

The value (`true`/`false`) is never shown. String leaves show an `e.g. "..."`
sample (`root: str  e.g. "iLO 4 v2.82"`), so `--path` *looks* like a value
lookup, but for bools it only shows the type. Pointing `--path` at the parent
object gives `LoginPriv: bool  100%` for each key. Again, no values.

The CLAUDE.md guidance says `structo FILE --path a.b` reads "one value", and the
PreToolUse hook blocks `python -c 'json.load(...)'` as the alternative. The
workaround was `curl ... | grep -oE '"LoginPriv":(true|false)'`.

## Why

Unknown. Probably the shape summarizer gives sample values only for strings
(and maybe numbers), and `--path` sends a scalar leaf down the same summarizer
path instead of printing it.

## What changed

Not fixed. Expected: when `--path` resolves to a scalar, print the scalar
itself. Bools in particular need this, because the type alone says nothing.
