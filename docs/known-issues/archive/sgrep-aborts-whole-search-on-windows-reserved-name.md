# sgrep: one Windows reserved-name file aborts the whole search

**RESOLVED (sgrep v0.5.0, verified 2026-10-09).** v0.5.0 already kept the matches when rg fails on some paths: they print, rg's error goes to stderr, and the exit is 2. Re-run on a tree holding a real `nul` file: both matching files listed, the `nul` error reported. The session that filed this was likely on an older install.

**Date:** 2026-09-26
**Tool:** sgrep (`--files-only`)

## What I tried

From CFS-SPEC, checking whether any project in the portfolio imports the CFS
tools:

```
$ sgrep "import cfs_|from cfs_" "G:/DataExtremes/Code" --files-only
sgrep: rg failed: rg: G:/DataExtremes/Code\Archive\portal\HomelabHQ_portal_v3\nul: Incorrect function. (os error 1)
```

No results at all - not the matches from the other nineteen projects.

## Why it misleads

A file named `nul` (a Windows reserved device name, presumably created by a
`> nul` redirect run under a POSIX shell) cannot be read. rg reports it as an
error and carries on; sgrep treats rg's non-zero exit as a failure of the whole
search and discards everything rg did find. One unreadable file anywhere under
the path makes a portfolio-wide search return nothing, and the error names the
file rather than saying the search result was thrown away.

## Expected

Report the unreadable path as a warning and still return the matches (rg's
exit code 2 with matches present on stdout means "found, with errors"), or
skip reserved device names (`nul`, `con`, `aux`, `prn`, `com1`...) outright.

## Workaround

Walk the tree in Python with `cfs_check.is_vendored` for exclusions, or point
sgrep at each project directory separately.
