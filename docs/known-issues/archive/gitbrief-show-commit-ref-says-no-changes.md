# gitbrief: `show <commit>` reports "No changes" instead of rejecting the argument

**RESOLVED 2026-10-09 (gitbrief v0.4.0).** `show COMMIT` now prints that commit's hunks against its first parent, on any branch, and a name that is neither a file nor a commit exits 2.

**Date:** 2026-09-25
**Tool:** gitbrief (`show`)

## What I tried

In the des_stack repo, wanting the change a specific commit made:

```
$ gitbrief show 9a4af06
No changes in 9a4af06
```

`9a4af06` changed six files (`codediff 9a4af06~1..9a4af06` listed them).

## Why it misleads

`show` takes a FILE, not a commit, so the argument was read as a path that
does not exist. The message reads as a true statement about the commit ("this
commit changed nothing"), which is the opposite of the truth. A reader who
trusts it moves on with a wrong fact.

## Expected

Either accept a commit ref (`show REF` → that commit's per-file summary), or
fail loudly: `gitbrief show: no such file '9a4af06' (to summarise a commit, use
codediff REF~1..REF)`.

## Workaround

`codediff REF~1..REF` for a commit's semantic summary.
