# gitbrief show says "no changes" for a path that does not exist

**RESOLVED 2026-10-09 (gitbrief v0.4.0).** A name that is neither a file nor a commit exits 2.

Filed 2026-10-08 from a full-suite review session. Minor.
Related: `gitbrief-show-commit-ref-says-no-changes.md` (same fallthrough,
different input).

## What broke

```
$ gitbrief show nosuchfile.py
no changes in nosuchfile.py        # exit 0
```

A typo in the path, or a path relative to the wrong directory, reads as
"this file is unchanged", which is a definite and wrong claim.

## Why

`view_show` checks for an empty diff and then for an untracked path. Every
other empty-diff case falls through to `no changes in X`, including a path
that is neither tracked nor present.

## What changed

Not fixed. Expected: when the path is not in `git ls-files` and not on
disk, raise `GitbriefError("%s: no such file in the repo or working
tree")` and exit 2.
