# structo tracebacks on malformed YAML and oversized CSV fields

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

```
$ structo bad.yaml          # "a: [1, 2\nb: : :"
Traceback (most recent call last):
  ...
yaml.parser.ParserError: expected ',' or ']', but got ':'
  in "bad.yaml", line 2, column 2
# exit 1

$ structo big.csv           # one cell of 200,000 chars
Traceback (most recent call last):
  ...
_csv.Error: field larger than field limit (131072)
# exit 1
```

Both exit 1, which is not one of structo's codes (0 ok, 2 error), and both
print a Python traceback instead of a `structo:` line. Malformed XML, by
contrast, already reports `structo: xml parse error: ...` with exit 2.

## Why

`main` catches only `StructoError`. `yaml.parse` raises `yaml.YAMLError`
subclasses, and `csv.reader` raises `csv.Error` (field size limit, and some
malformed quoting). Neither is translated. A file that passes `isfile` but
cannot be opened (locked on Windows, permissions) raises a bare `OSError`
the same way.

## What changed

Not fixed. Expected: wrap `yaml.YAMLError`, `csv.Error` and `OSError` as
`StructoError` (`"%s is not valid yaml: %s"`). For CSV, raise
`csv.field_size_limit` to a sane maximum: a schema summary does not need to
refuse a long cell.
