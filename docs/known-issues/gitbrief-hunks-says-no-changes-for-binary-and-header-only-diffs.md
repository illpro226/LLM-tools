# gitbrief hunks says "no changes" for binary and header-only diffs

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

In a repo whose only change is a modified binary file:

```
$ gitbrief hunks
no changes
```

The same happens for a staged empty new file (`git add empty.txt`) and for a
mode-only change (`chmod +x`). `git diff HEAD` shows all three. `gitbrief`
(the default view) does list them, so the two views contradict each other,
and `hunks` is the one an agent reads before committing.

## Why

`parse_diff` takes a file's path only from its `--- a/` / `+++ b/` lines.
Binary diffs ("Binary files a/x and b/x differ"), empty new files and mode
changes have no such lines. The entry keeps `path: None` and the final
`[f for f in files if f["path"]]` drops it. With nothing left, `view_hunks`
returns `no changes`.

## What changed

Not fixed. Expected: take the path from the `diff --git a/X b/X` header when
there are no `---`/`+++` lines, and render those files as
`path (binary)` / `path (new, empty)` / `path (mode 100644 → 100755)`
rather than dropping them.
