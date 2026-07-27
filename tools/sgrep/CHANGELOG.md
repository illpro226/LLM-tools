# sgrep Changelog

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
