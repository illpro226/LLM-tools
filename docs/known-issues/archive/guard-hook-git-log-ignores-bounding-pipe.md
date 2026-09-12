# guard hook denies `git log ... | head` though the same bounding pipe is accepted for grep/cat/sed

**FIXED 2026-09-11 (guard hook).** The git branch of `check_shell` now
tests `_output_reaches_context(_own_pipeline(...))` before denying, the
same predicate the grep branch uses, so `git log`/`git diff` whose stdout
is redirected to a file or piped through `head`/`tail`/`wc` is allowed.
Seven cases added to `scripts/test-guard-hook.py`; the differential run
shows five intended DENY -> ALLOW flips and no unintended ones.

- **What broke:** during the 2026-09-11 session, the call
  `git status --short; git log --oneline origin/main..HEAD | head` was
  denied with the standard `gitbrief` redirect. The deny message says
  bounded lookups are allowed — "`git log -1`/`-n 1` or `--oneline` with a
  count of 10 or fewer" — and the call *was* bounded, by `| head`, which
  caps output at 10 lines. The agent had to re-run it as
  `git log --oneline -n 5 …`, which produced the same output. One wasted
  round-trip on a call that was already cheap.
- **Why it happened:** the git branch of `check_shell` scopes a match's
  arguments with `_own_args`, which splits on `SEP_RE` — and `SEP_RE`
  includes a single `|`. So the bounding `| head` is cut off before
  `_log_is_bounded` ever sees it, and a call with no explicit `-n` reads as
  an unbounded dump. The hook already has the right machinery for this and
  uses it one loop later: the grep branch scopes with `_own_pipeline`
  (`PIPE_END_RE`, which deliberately does *not* split on a single `|`) and
  tests `_output_reaches_context`, whose docstring states the principle —
  output that provably cannot land in context costs no tokens. `cat` and
  the `sed`/`head`/`tail`/`awk` range reads get the same carve-out. Only
  the git branch was left out.
- **Why it matters beyond the round-trip:** the rule as enforced was
  stricter than the rule as documented, in both the hook's deny text and
  the global CLAUDE.md ("a search whose stdout goes to a file or through
  `head`/`tail`/`wc`"). A guard whose message describes a carve-out it does
  not actually honor trains the agent to distrust the message, which is the
  one mechanism that reliably changes tool choice
  (`agent-defaults-to-builtins-mid-task`).
- **Fix:** the git branch now checks
  `_output_reaches_context(_own_pipeline(command, m.end()))` before
  denying, exactly as the grep branch does — applied to `log` and `diff`
  alike, since a pipeline whose stdout is redirected to a file or piped
  through `head`/`tail`/`wc` is not a context cost whatever the subcommand.
  `gitbrief` remains the redirect for everything that does reach context.
