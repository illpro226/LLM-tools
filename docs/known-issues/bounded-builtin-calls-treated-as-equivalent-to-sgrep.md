# agent treats a guard-hook-*allowed* bounded Grep/Read call as equivalent to using sgrep/xread, when the output shape is still worse

**STATUS at filing: open.**

- **What broke:** during the same 2026-08-23 session covered in
  [`guard-hook-python-m-json-tool-bypasses-structo-redirect.md`](guard-hook-python-m-json-tool-bypasses-structo-redirect.md),
  the agent hit several guard-hook denials on directory-wide `Grep`-tool
  calls ("Grep in content mode across a directory dumps raw lines. Use
  sgrep..."). Each time, instead of switching to `sgrep`, the agent
  narrowed the *same* `Grep` call — single file, or `head_limit` under the
  hook's threshold — which the hook then allowed. When later asked why it
  hadn't used `sgrep`/`xread` at all that session, the agent's first answer
  was that this was fine: the hook's own bounded-variant carve-out (single-
  file grep, `head_limit ≤ 25`, offset/limit Reads) meant those calls
  weren't the failure mode the hook exists to prevent. The user pushed
  back, correctly: `sgrep --help` describes it as a "ripgrep wrapper that
  condenses results into a ranked, deduplicated digest," with match
  collapsing and a token cap (`--max-tokens`, default 1500) *on by
  default, independent of query size*. A single-file `Grep` call still
  returns one raw line per match with no collapsing or ranking — smaller
  in absolute bytes than an unbounded directory dump, but not the leaner
  output shape `sgrep` exists to produce. The agent had conflated "the
  hook didn't block this" with "this was the efficient choice," which
  are different claims — the carve-out exists for latency/ergonomics on
  genuinely small, precise lookups, not as a signal that `sgrep` would add
  nothing.
- **When it happens:** any bounded/single-file search or read that the
  guard hook's carve-out permits without redirecting. These are exactly
  the calls that never produce a denial message, so there's no prompt-time
  moment that raises the question "would the suite tool still have been
  better here?" — the absence of friction reads as an absence of an
  available choice.
- **Why it happened (best available explanation):** the guard hook's deny
  messages are the *only* mechanism that reliably changes tool choice
  (per the resolved `agent-defaults-to-builtins-mid-task` finding). A
  carve-out, by construction, produces silence instead of a redirect
  message — so for the class of calls it exempts, the mechanism that
  works has nothing to act on, and the agent's own judgment (which that
  same resolved issue found unreliable under task pressure) is what's left
  running the decision.
- **What actually worked, for comparison:** none in this session — this
  pattern wasn't caught by the agent itself, only by the user reading
  `sgrep --help` and comparing it against what the agent had actually
  called.
- **Recommended fix:** the existing PostToolUse "once-per-session nudge on
  allowed mid-size whole-file Reads" (from the resolved
  `agent-defaults-to-builtins-mid-task` fix) is the right shape of
  mechanism for this too — extend an equivalent nudge to `Grep`-tool calls
  that pass the carve-out (single-file content mode, or `head_limit`
  under threshold) pointing at `sgrep`'s collapsing/ranking behavior
  specifically, not just its existence, since "you could have used sgrep"
  is weaker than "sgrep would have deduplicated and ranked these matches
  instead of returning every raw line." Once-per-session keeps it from
  being spam on legitimately trivial one-off lookups where the difference
  is negligible.
