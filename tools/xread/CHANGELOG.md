# xread Changelog

- 2026-07-17: v0.2.0 — Prisma schema support for `--symbol`: flat block
  scanner for `model|enum|type|view|generator|datasource NAME { ... }`
  with attached `//` comments; strings are stripped before comments so
  braces in defaults and `//` in datasource URLs don't derail spans (fixes
  known-issue `xread-symbol-no-prisma-support`). Query mode: a returned
  markdown region that starts at a heading now pulls in the immediately
  preceding same-level sibling section when it is short (≤ 20 lines) and
  carries a fenced block — fenced payloads are nearly opaque to keyword
  scoring, so the envelope above the section that matched was being
  dropped (fixes known-issue `xread-query-misses-adjacent-code-block`);
  prose siblings still score on their own merits. 35 tests.

- 2026-07-11: v0.1.1 — query mode: blocks are clamped at the next
  top-level symbol so nested markdown sections tile the file instead of
  the H1 span (whole document) competing with — and swallowing — the
  specific subsection a query targets (fixes known-issue
  `xread-query-returns-whole-markdown-file`); scoring now weights by
  whole-word keyword coverage, so a block containing every query word
  outranks one repeating a single common word or matching only inside
  longer words ("building" is not a hit for "build"; substring hits still
  count toward volume, keeping partial-word queries working). No-op for
  code files, whose top-level spans never overlap. 30 tests.
- 2026-07-07: v0.1.0 — initial implementation: symbol/lines+scope/query
  modes for Python and JS/TS, markdown mode (`--headings`, section
  extraction via `--symbol`), region merging with elision markers,
  `--max-tokens` budget; stdlib-only parsers (ADR-004); 27 fixture-based
  tests.
- 2026-07-06: Added initial documentation scaffold.
