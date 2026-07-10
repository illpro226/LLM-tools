# runlite Roadmap

## M1 — Scaffold and runner

- CLI with `runlite -- CMD` parsing, subprocess capture, exit/wall-time report.
- Exit-code passthrough; generic fallback extractor.

## M2 — Extractor set

- Extractor registry with detection (command name, then log fingerprint).
- pytest, jest/vitest, go test extractors with canned-log fixtures.
- cargo, tsc, eslint, gcc/clang extractors.

## M3 — References and export

- Nearest `file:line` attachment per problem; context lines.
- `--full-log PATH` raw-log export with printed path.

## M4 — Token budget

- `--max-tokens N`: first failure full, rest one line each; fixture tests
  for the over-budget path.

## Later

- Timeout handling; `--json` report if a consumer appears.
