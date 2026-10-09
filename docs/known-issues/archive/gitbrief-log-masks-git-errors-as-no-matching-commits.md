# gitbrief log masks git errors as "no matching commits"

**RESOLVED 2026-10-09 (gitbrief v0.4.0).** 128 is accepted only on an unborn branch. Note: `--grep "("` is valid in git's default basic regex, so the test uses `--author "["`; the original repro likely ran under an extended `grep.patternType`.

Filed 2026-10-08 from a full-suite review session.

## What broke

```
$ gitbrief log --grep "("
no matching commits          # exit 0

$ gitbrief log --author "["
no matching commits          # exit 0
```

git rejects both patterns (`fatal: ... invalid regex`, exit 128). The caller
gets exit 0 and a definite "nothing matched", when the search never ran.

## Why

`gather_commits` calls `_git(..., ok_codes=(0, 128))` so that a repo with no
commits yet yields an empty list. But 128 is git's generic fatal exit code,
so every other fatal error (bad regex, bad revision range) is accepted as
an empty result too.

## What changed

Not fixed. Expected: accept 128 only when there is no HEAD (`_head_exists()`
is already there). Otherwise raise `GitbriefError` with git's first stderr
line, which is what every other `_git` call does.
