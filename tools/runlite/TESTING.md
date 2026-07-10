# runlite Testing

Fixture-based, per repo conventions (AGENTS.md). Extractors are pure functions
over text, so the fixture set is canned tool logs — tests never require real
toolchains.

## Fixtures

- `tests/fixtures/logs/` — canned outputs per tool: pytest, jest, vitest,
  go test, cargo, tsc, eslint, gcc, clang; each in passing and failing
  variants with known failure counts and `file:line` references.
- A mixed/unknown-tool log for the generic fallback.

## Test areas

- **Runner** — exit code and wall time reported; runlite's own exit code
  mirrors the wrapped command (verified with true/false-style commands);
  stdout+stderr captured merged.
- **Detection** — extractor chosen by command name; by log fingerprint when
  the command is wrapped (e.g. `make test`); generic fallback otherwise.
- **Extraction** — per fixture: every failure found, message intact, nearest
  `file:line` attached, expected context lines present; passing-variant logs
  produce a short all-green report.
- **Generic fallback** — error/warning/fail pattern lines kept plus the last
  20 lines, and nothing else.
- **Token cap** — over budget: first failure in full, each remaining failure
  exactly one line; within budget at every fixture.
- **Raw-log export** — `--full-log` writes the byte-exact log and prints the
  path.

## Running

`python -m pytest` from `tools/runlite/`.
