# structo sniffs a one-line JSON array as TOML, and an empty file as JSON

**STATUS: open.** Filed 2026-10-08 from a full-suite review session. Minor:
extensionless files only.

## What broke

```
$ structo arrfile            # contents: ["alpha"]
structo arrfile — format: toml (sniffed)

root: object
  alpha: object  100%
```

A JSON array holding one string (or one number, `[1]`) reads as a TOML
table header named `alpha`. tomllib accepts it, so the "back off to log if
tomllib rejects" guard does not catch it.

An empty or whitespace-only extensionless file reports
`format: json (sniffed)` / `root: empty`. It should say the file is empty.

## Why

`_TOML_TABLE` allows `"` and digits inside the brackets, so `["alpha"]` and
`[1]` are valid table headers. `_looks_toml` runs before the JSON check.
For the empty file, `stripped[:1] in "{["` is `"" in "{["`, which is
`True`: the empty string is a substring of every string.

## What changed

Not fixed. Expected: try `json.loads` on the sniffed head before claiming
TOML, when the first line starts with `[` and parses as JSON. Test
`stripped and stripped[0] in "{["`, and report an empty file as such.
