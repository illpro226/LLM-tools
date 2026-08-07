# runlite

Command output distiller: runs a build/test/lint command, captures
stdout+stderr merged, and prints a failure-focused report — exit code, wall
time, and extracted problems with `file:line` references — instead of
thousands of lines of passing noise.

Single-file Python CLI, stdlib only. Extractors are pure functions over the
captured text; detection tries the command name first, then log fingerprints,
then a generic fallback. runlite exits with the wrapped command's exit code
so it composes in scripts (its own failures use 125, command-not-found 127).

## Usage

```
runlite -- CMD ARGS...                 # run and distill
runlite --max-tokens N -- CMD...       # over budget: first problem full,
                                       # remaining problems one line each
runlite --full-log PATH -- CMD...      # also save the raw log, print its path
```

Built-in extractors: pytest, jest/vitest, go test, cargo, tsc, eslint,
gcc/clang, next build. Unknown tools get the generic fallback: lines
matching error/warning/fail patterns plus the last 20 lines of output.

A run that exited 0 never reports failure-shaped findings — the exit code
is the reliable signal, and the report says which extractor misfired
rather than dropping them silently.

The header's `[log N B]` is the exact size of the log the report replaced,
so you can tell a summary of 400 KB from a summary of 900 B. Use
`--full-log PATH` when you want the bytes themselves.

### Example

```
$ runlite -- pytest -q
# runlite: exit 1 in 0.74s (pytest) 2 problems [log 41208 B]

FAIL test_add  test_demo.py:5
      def test_add():
  >       assert add(2, 3) == 5
  E       assert -1 == 5

  test_demo.py:5: AssertionError

FAIL test_add_negative  test_demo.py:8
  ...
```

Every problem carries the nearest `file:line` so a finding can be followed up
with `xread`. `--full-log` preserves the complete raw log as the escape hatch
when the heuristic extraction misses something.

## Development

```
python -m pytest        # from tools/runlite/
```

Tests run against canned tool logs in `tests/fixtures/logs/` — no real
toolchains needed. See the repo root `START.md` for suite-wide conventions.
