# 0006: `rq` and `testmap` are retired from default use

Status: Accepted (2026-08-06)

## Decision

`rq` and `testmap` stop being tools an agent is told to reach for. They are
removed from the dogfood guidance and the gotcha table in the root
`CLAUDE.md`, and from the equivalent guidance in `AGENTS.md`.

The code, tests and docs stay in `tools/rq/` and `tools/testmap/`. Both
remain implemented and passing; `python -m pytest` in either directory
still works. This is a retirement from *guidance*, not a deletion.

`repoindex` is explicitly **not** retired. It logs zero direct CLI calls
because it is a library, not a tool an agent invokes: `codediff` reuses its
`extract()` on git blobs, and it owns `.repoindex/index.db`. Zero calls
means "used as intended", not "unused".

## Why

`savings_record.md` measures 1481 logged suite calls across ten projects
over roughly a month. `rq` was called 2 times (last 2026-07-27, ~80 bytes
of output total). `testmap` was called 0 times.

Both were already demoted once, to the "Situational, not default" section
added when 0005 landed, on the theory that they had been mis-framed rather
than unwanted. That section states the precondition for each: for `rq`, a
relationship question spanning more call sites than `sgrep` can settle in
one pass; for `testmap`, a suite slow enough that narrowing beats running
it. Neither trigger has fired since. In practice `sgrep --counts-only`
answers "who calls this?" for less than an index build costs, and every
suite in reach runs in seconds.

The cost of keeping them in the guidance is not zero. `savings_record.md`
already makes the argument this decision acts on: *a tool nobody calls
scores neutral on savings while being the most expensive thing in the
suite — unused surface area that still has to be maintained, documented
and kept in an agent's head.* Two entries in the dogfood list, two rows in
the gotcha table and two blocks of run commands are budget spent on every
session that reads `CLAUDE.md`, in exchange for one call every two weeks.

Keeping the code costs nothing by comparison: the tests are already
written and they run in seconds.

## Consequences

- Root `CLAUDE.md` loses ~30 lines. `AGENTS.md` gets the same treatment.
- An agent that genuinely faces a whole-repo relationship question will
  now reach for `sgrep` and, if that fails, ask. That is the honest
  outcome — it is what was already happening.
- `repoindex`'s own guidance stays intact, including `testmap record`
  coverage rows surviving `update`.
- `savings_record.md` keeps reporting both tools. If their call counts
  ever move without the guidance pushing them, that is exactly the
  evidence this decision asks for.

## Revisit if

`rq` or `testmap` gets called unprompted more than a handful of times in a
month, or the suite starts being used in a repo where the test run is slow
enough that `testmap`'s precondition holds. Either is grounds to move them
back into the situational list. Deleting them needs a further decision,
not this one.
