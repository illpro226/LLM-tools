# gitbrief

Layered, token-cheap views of git state. The default view is a one-screen
summary; detail is opt-in and narrow, so "dump the whole diff" never
happens by accident.

```
./gitbrief.py                    branch + drift, status+diffstat table,
                                 last 5 commits
./gitbrief.py hunks [FILE...]    diff hunks at 1 context line (vs HEAD)
./gitbrief.py show FILE          the full diff for exactly one file
./gitbrief.py log [--grep X] [--author X] [-n N]
./gitbrief.py pr BASE            branch summary vs BASE: commits, diffstat,
                                 changed symbols (heuristic; python/js-ts)
```

All modes accept `--max-tokens N` (bytes/4) and degrade by whole levels —
tables collapse to counts, hunks drop context then bodies, lists shorten —
never by truncating mid-thought.

Read-only by construction: subprocess `git` plumbing only
(`--no-optional-locks`, porcelain formats, no libgit binding). Stdlib-only
single file; `python -m pytest` from this directory runs the tests (git
required on PATH). See [`DECISIONS.md`](DECISIONS.md) for the ADRs,
including ADR-005 (stdlib changed-symbol extraction instead of the
optional tree-sitter plan).
