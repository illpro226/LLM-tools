# gitbrief show <sha> reports "No changes" for a real commit

**RESOLVED 2026-10-09 (gitbrief v0.4.0).** `show COMMIT` now prints that commit's hunks against its first parent, on any branch, and a name that is neither a file nor a commit exits 2.

Seen 2026-09-26 in `G:\DataExtremes\Code\TOCH_SS`, checked out on `main`.

`gitbrief show 5cafd23` printed `No changes in 5cafd23`. That commit is the
tip of the unmerged branch `fix/sac-safe-launcher` and changes three files
(`bin/toch` +5, `bin/toch.cmd` +1, `pyproject.toml` -3), per
`git show --stat fix/sac-safe-launcher`.

Guess: `show` diffs against the working tree or only handles commits reachable
from HEAD, rather than diffing the commit against its parent.

Workaround used: `git show --stat --format='%h %s' <ref>` plus
`git show <ref>:<path>` for file contents.
