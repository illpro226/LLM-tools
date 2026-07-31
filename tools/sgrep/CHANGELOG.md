# sgrep Changelog

- 2026-07-31: v0.2.0 — `--max-tokens` now defaults to 1500 instead of unbounded
  (ADR-005, docs/decisions/0005-budgets-on-by-default.md); `--max-tokens 0`
  restores the old behaviour. Context reduction is announced
  (`(context reduced 3 -> 1 for --max-tokens N)`) so a trimmed excerpt is
  never mistaken for an absent one. 5 new tests (28 total).
  Also: stderr pinned to UTF-8 at entry alongside stdout — error messages
  carry the same non-ASCII punctuation as normal output, and on a cp1252
  console reached the caller as invalid UTF-8 bytes.
- 2026-07-27: v0.1.1 — stdout pinned to UTF-8 (`reconfigure(encoding=
  "utf-8")`) so matched lines round-trip byte-for-byte instead of losing
  non-ASCII characters to a cp1252 console default. 23 tests.
  Closes the sgrep half of
  docs/known-issues/non-ascii-output-mangled-on-windows.md.
- 2026-07-07: v0.1.0 — initial implementation: rg --json wrapper with
  grouped/deduplicated digest, count × path-class ranking with .sgrep.toml
  overrides, --files-only/--counts-only, --max-tokens reduction (context →
  matches per file → files), --rg/SGREP_RG binary resolution; 22 tests
  (canned JSON streams + real-rg end-to-end that skip when absent).
- 2026-07-06: Added initial documentation scaffold.
