# codediff: untracked paths with spaces arrive quoted and go unanalyzed

**RESOLVED 2026-10-09 (codediff v0.6.0).** `status` and `diff --name-status` run with `-z`.

Filed 2026-10-08 from a full-suite review session.

## What broke

An untracked `my file.py` containing `def hello()`:

```
$ codediff
codediff: working tree vs HEAD (1 file)

1 of 1 file not analyzed: "my file.py"

Risk flags: none
```

The path keeps its quotes, the `.py` extension is read as `.py"`, so
language detection fails and the new function is never reported. Reading
the worktree file under the quoted name would fail too. `gitbrief` on the
same repo shows the path correctly (`? my file.py  +2 -0`).

## Why

`changed_files` lists untracked files with `git status --porcelain=v1` and
takes `line[3:]` as the path. Short-format status C-quotes paths that
contain a space (and `core.quotepath=false` only covers bytes above 0x80).
Tracked paths come from `diff --name-status`, which does not quote spaces,
so only additions are affected. Tab, newline, `"` and `\` in a path are
quoted in both outputs.

## What changed

Not fixed. Expected: use `-z` for both the `status` and `diff --name-status`
calls and split on NUL. That removes quoting entirely, as gitbrief's
porcelain-v2 parse effectively does for the space case.
