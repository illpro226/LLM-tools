# codediff's "not analyzed" share is wrong when the change includes a rename

**STATUS: open.** Filed 2026-10-08 from a full-suite review session.

## What broke

A staged change: `mod.py` renamed to `mod2.py` with +2 lines (a 152-line
file), and `notes.txt` with +2 lines.

```
$ git diff --cached --numstat -M
2	0	mod.py => mod2.py
2	0	notes.txt

$ codediff --staged
...
1 of 2 files, 1% of changed lines not analyzed: notes.txt
```

The true share is 2 of 4 changed lines, 50%. The figure that exists to
state the summary's own incompleteness understates it about fiftyfold.

## Why

`_changed_line_counts` keys numstat rows by `parts[-1]`. Without `-z`, a
rename row's path field is `mod.py => mod2.py` (or `dir/{a => b}.py`), so
nothing matches `entry["path"]` (`mod2.py`). `main` then fills the gap with
`counts.setdefault(path, n)`, where `n` is the *whole file's* line count,
meant for untracked files. The renamed file is counted at 152 changed lines
instead of 2.

## What changed

Not fixed. Expected: `git diff --numstat -z -M`, where a rename row is
`added\tdeleted\t\0old\0new\0`, keyed by the new path. That also fixes
paths containing tabs or quotes. Apply `setdefault` only to untracked
entries.
