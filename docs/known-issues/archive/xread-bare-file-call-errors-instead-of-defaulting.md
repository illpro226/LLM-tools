# `xread FILE` with no mode flag errors instead of defaulting to the cheapest useful view

**RESOLVED 2026-09-11 (xread v0.4.1).** A call with no mode flag defaults
to `--headings` and announces it on stderr; mutual exclusion among
explicit modes is unchanged. Four tests added.

- **What broke:** twice in the 2026-09-11 session the agent called
  `xread FILE --max-tokens N` with no mode flag and got
  `error: exactly one of --symbol, --lines, --query, --headings is
  required` — usage text, no content, a wasted round-trip each time. Both
  calls were the *first* look at an unfamiliar file, where the agent had no
  symbol name to ask for yet.
- **Why it happened:** every mode is opt-in and none is the default, so the
  most natural first call a reader makes — name the file, ask to see it —
  is the one call that returns nothing. The root `CLAUDE.md` names
  `--headings` as "the cheap first move on an unfamiliar file", so the
  guidance already identifies what a bare call means; the CLI just doesn't
  implement it.
- **Why the error is the wrong response:** the argument for strictness is
  that a bare `xread FILE` might mean "dump the file", which is the thing
  xread exists to prevent. But `--headings` *is* the bounded answer to
  that request — a structural outline, budgeted like every other mode. So
  the choice is between a round-trip that teaches nothing and a cheap
  correct answer. The deny-shaped response also mimics a guard-hook
  denial without being one, which muddies a signal the suite depends on.
- **Fix:** a call with no mode flag now defaults to `--headings` and says
  so on stderr (`xread: no mode given, showing --headings`), so the
  behavior is discoverable rather than silent. Explicit modes are
  unchanged, and mutual exclusivity among them still holds — the default
  applies only when none was given. `--lines` still requires its range.
