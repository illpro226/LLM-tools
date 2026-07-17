# adoption: agent reverts to Read/Grep/Bash mid-task despite the suite being available and known

**MITIGATED 2026-07-11 (guard hook v2 + DR 0004).** The recommended fix
below shipped: `~/.claude/hooks/llm-tools-guard.py` now denies-and-redirects
shell `grep`/`rg`/`git grep` (→ sgrep), bare `cat`/`Get-Content`/
`Select-String` dumps (→ xread/structo), inline `node -e`/`python -c` JSON
parsing (→ structo), Grep-tool content mode over directories (→ sgrep), and
whole-file Reads above per-kind limits (data 8KB, code/docs 20KB, other
50KB); bounded variants (pipeline filters, heredocs/redirects, offset/limit,
single-file grep, head_limit ≤ 25) pass. A PostToolUse hook adds a
once-per-session nudge on allowed mid-size whole-file Reads. 43-case battery
passed 2026-07-11. For agents without hooks, docs/decisions/0004 accepts a
minimal MCP adapter exposing the core four (xread/sgrep/structo/gitbrief) as
first-class tools — salience at the decision point rather than recall.
Kept open-adjacent rather than RESOLVED until a few real sessions confirm
the deny/allow boundaries don't over-fire.

Original report follows.

**STATUS at filing: open.** Unlike the Codex PATH issue in this same directory, this
was not a visibility problem — the suite was on PATH, the agent (Claude
Code, this session) had already used `xread` and `repomap` successfully
earlier in the same conversation, and the user's own global CLAUDE.md
states the preference explicitly ("Prefer these over built-ins in every
project"). The tools were known and reachable; they just lost out to
`Read`/`Grep`/`Bash` once the agent shifted from exploration into a fast
edit → verify loop.

- **What broke:** across one session (2026-07-11, CortexLink project),
  the agent used `Read`/`Grep`/plain `Bash` (`grep`, `cat`, ad-hoc
  `node -e` JSON filtering) instead of `xread`/`sgrep`/`structo` at least
  three separate times, including twice *immediately after* the agent
  itself acknowledged the lapse and saved a correction to its own memory
  file. The user caught all three instances; the agent did not self-catch
  any of them in the moment.
- **When it happens:** not during initial open-ended exploration — the
  same session used `xread --headings`, `xread --symbol`, and `repomap`
  correctly while first investigating an unfamiliar codebase. The lapse
  was specific to heads-down implementation work: reading a file it
  already knew the location of, searching for a symbol it could name,
  parsing a JSON API response — the moments where the trained-in default
  of `Read`/`Grep` is fastest to reach for and the task pressure to "just
  get this done" is highest.
- **Why it happened (best available explanation):** `Read` and `Grep` are
  far more deeply reinforced defaults from training than `xread`/`sgrep`
  are. In-context instructions (CLAUDE.md loaded every turn) and even a
  self-authored memory file correcting the exact same behavior were not
  sufficient to override that prior reliably — they're available at the
  moment of the decision but nothing forces a check against them before
  each tool call.
- **What actually worked, in the same session, for a comparable problem:**
  this repo already has a PreToolUse hook that blocks raw `git diff`/
  `git log` and redirects to `gitbrief`. The agent used `gitbrief`
  exclusively, without a single lapse, for the entire session — including
  in the same stretches where it reverted to `Read`/`Grep`. The
  difference isn't awareness or preference strength; it's that the git
  path is enforced mechanically and the file-read/search path is not.
- **Corroborating instance (2026-07-11, this repo):** while analyzing this
  very issue file and designing the hook fix, the agent used built-in
  `Glob`/`Read`/`Grep` exclusively — including a `Grep` on a 25-line
  settings.json where `sgrep` was the stated preference (and where the
  proposed hook would have denied the call). The whole-file `Read`s of
  1–3KB issue docs were defensible; the search lapse was not. Confirms
  the pattern survives even maximum topical salience: the suite being the
  literal subject of the conversation did not change tool choice.
- **Recommended fix:** add a PreToolUse hook for `Read` and `Grep` (via
  the `update-config` skill or directly in `.claude/settings.json`)
  analogous to the existing git hook — either block the call outright
  with a message pointing at `xread`/`sgrep`, or auto-rewrite it. Relying
  on repeated in-context instruction or agent self-correction has now
  failed three times in a single session and should not be the primary
  mitigation.

---

**Field report 2026-07-17 (bible-atlas session):** hook boundaries behaved
well overall. Correct denies: raw `git log --oneline -10` (→ gitbrief log),
`cat tokens.css` (→ Read/xread). Borderline over-fires: `cat` on a 2-line
playwright console log and the PostToolUse nudge on a 6.7KB whole-file Read
of a page component that genuinely needed full context before a rewrite —
each cost one extra round trip, no wrong outcome. Adoption itself held:
xread/sgrep/gitbrief/codediff/repomap used throughout a full feature build
without reverting to builtins mid-task.
