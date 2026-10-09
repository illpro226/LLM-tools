# codediff reports JS string changes after `//` as formatting/comment-only

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

```diff
-export const API = "https://api.prod.example.com/v1";
+export const API = "https://evil.example.net/v1";
```

```
$ codediff
codediff: working tree vs HEAD (1 file)

Mechanical
  formatting/comment-only  api.js:1

Risk flags: none
```

An endpoint swap is filed under Mechanical, with no Behavior entry and no
risk flag. That is the exact change a pre-commit summary exists to surface.
It also applies to every non-Python language that goes through this path
(JS/TS, Go): any string containing `//` (URLs, protocol-relative paths,
regexes), and any string containing `/*`.

## Why

`_mechanical_kind` decides "comment-only" for non-Python languages with
`re.sub(r"//[^\n]*|/\*.*?\*/", "", src)`. That regex knows nothing about
string literals, so it deletes everything from the `//` in `"https://` to
the end of the line, on both sides. The two stripped sources compare equal.

## What changed

Not fixed. Expected: strip comments with a string-aware scanner. The suite
has four already, e.g. `_strip_js_noise` in repoindex. Or compare the
extracted refs/literals before declaring a file mechanical. Until then,
"formatting/comment-only" on a JS/TS/Go file is not trustworthy.
