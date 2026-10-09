# gitbrief pr reports "commits (1000)" for any branch with more

**STATUS: open.** Filed 2026-10-08 from a full-suite review session. Minor.

## What broke

On a branch 1,100 commits ahead of its base:

```
$ gitbrief pr BASE
pr vs BASE (merge-base 1a2b3c4)

commits (1000):
...
```

The heading states a count, and the count is wrong. The `(… N more)` line
under the list is computed from the same capped list, so nothing in the
output reveals that 100 commits are missing.

## Why

`view_pr` calls `gather_commits(1000, rev_range=...)`, which passes
`-n 1000` to `git log`. `len(commits)` is then used as the total.

## What changed

Not fixed. Expected: take the real total from
`git rev-list --count MERGE_BASE..HEAD` and keep `-n` only as a cap on the
listed lines (`commits (1100, first 1000 listed)`).
