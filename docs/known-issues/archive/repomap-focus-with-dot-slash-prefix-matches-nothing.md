# repomap --focus ./PATH silently focuses on nothing

**RESOLVED 2026-10-09 (repomap v0.5.0).** The focus path is normalized with `posixpath.normpath`.

Filed 2026-10-08 from a full-suite review session.

## What broke

```
$ repomap --focus pkg
pkg/m0.py  [refs 0]
  pkg/m0.py:1 def f0()
...

$ repomap --focus ./pkg
pkg/m0.py  [refs 0]  (1 symbol)
pkg/m1.py  [refs 0]  (1 symbol)
...
(4 files outside --focus ./pkg collapsed to one line; ...)
```

With the leading `./` (and `.\pkg` from PowerShell tab-completion, which
becomes `./pkg` too), every file counts as outside the focus. The focused
files get only the one-line summary, and the note blames `--focus` for it.

## Why

`main` normalizes the focus with `.replace("\\", "/").strip("/")`, which
keeps `./`. The existence check passes (`os.path.join(".", "./pkg")`
exists), but `_in_focus` compares against walker paths like `pkg/m0.py`,
which never start with `./pkg/`.

## What changed

Not fixed. Expected: normalize with `os.path.normpath` before converting to
`/`, so `./pkg`, `pkg/` and `.\pkg` all become `pkg`. A focus that matches
no scanned file should also say so, instead of collapsing everything.
