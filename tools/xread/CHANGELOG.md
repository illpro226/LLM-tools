# xread Changelog

- 2026-08-06: v0.4.0 - `--headings` outlines code files, not just markdown.
  It prints one line per symbol with its kind and span
  (`sgrep.py:217  function render [217-265]`), nesting carried by
  indentation rather than a repeated qualified name. This closed a gap
  between two tools that each deflected to the other: `xread --headings`
  said "use repomap for code outlines" and `repomap` accepts only
  directories, so there was no way to ask "what's in this file?" for a
  code file - which is the precondition for `--symbol`, since you can't
  name a symbol you haven't seen yet. The workaround was to `repomap` the
  parent directory, which ranks and collapses across siblings and charges
  for every other file in it. The span is what makes the listing
  actionable: it says what a follow-up `--symbol` will cost before you
  spend it. A file xread has no parser for still exits 2, now naming the
  languages it does parse. 3 new tests (41 total), one asserting every
  name the outline prints resolves as a `--symbol` argument. Closes
  docs/known-issues/archive/no-way-to-outline-one-code-file.md.

- 2026-07-31: v0.3.0 — `--max-tokens` now defaults to 2000 instead of unbounded
  (ADR-005, docs/decisions/0005-budgets-on-by-default.md); `--max-tokens 0`
  restores the old behaviour. Fixed: a sole region with no blank line to
  trim at was dropped whole, returning only a `(dropped for --max-tokens)`
  note; it now halves toward its head until it fits. 4 new tests
  (39 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
- 2026-07-27: v0.2.1 — stdout pinned to UTF-8 so excerpted source keeps its
  non-ASCII characters on Windows (same fix as sgrep/repomap/gitbrief).
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
