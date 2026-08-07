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

runlite trace [FILE]                   # distill a stack trace (stdin if no FILE)
runlite trace --all-frames FILE        # keep library frames too
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

## `runlite trace`

The same job for a trace runlite did not produce — one that arrived from a
log file, CI, a running service, or a paste:

```
runlite trace app.log
kubectl logs pod-xyz | runlite trace
```

Python, Java/JVM, Node, Go and Rust. The output is the exception plus the
frames that are your code; runs of library frames collapse to one line:

```
# runlite trace: python, 1 trace, 8 frames → 4 shown (innermost first) [input 1017 B]

ValueError: invalid literal: 'abc'
  /app/parser.py:42  in parse_int
  /app/service.py:27  in handle
  … 4 site-packages frames
  /app/main.py:11  in main
during handling of  KeyError: 'user_id'
  /app/store.py:9  in lookup
```

Frames always read innermost-first and chained exceptions always
propagated-first, whatever order the language prints them in — so you read
five languages the same way. Frame 0 is *not* kept just for being frame 0:
in Rust and Go it is always unwind machinery. `--all-frames` turns
collapsing off.

Exit codes here are `trace`'s own, since it wraps nothing: 0 distilled a
trace, 1 the input held none (said out loud, never silently), 125 internal.

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
