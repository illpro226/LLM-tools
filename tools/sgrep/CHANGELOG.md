# sgrep Changelog

- 2026-08-06: v0.4.0 — `-C` context lines no longer repeat the file path.
  They print as `  248-  text` under the `== path (N matches) ==` header
  that already names the file; match lines keep the full `path:line:` and
  stay followable with `xread`. This was not cosmetic. `savings_record.md`
  measured **193 of 297 credited calls printing more than the raw `rg`
  they replaced** — sgrep's one near-break-even tool despite being the
  most-called. The repeated prefix was the cause: with `-C 3` there are
  roughly six context lines per match, each paying the full path again,
  while `rg` on a single file prints no path at all. Measured on four
  representative searches, output fell 19,732 → 15,174 bytes (-23%) and
  a `-C 3` search that had been 573 bytes *worse* than `rg` became 1,752
  bytes better. 2 new tests (32 total), one pinning the saving and one
  pinning the invariant it must not break. INVARIANTS.md updated.
- 2026-08-06: v0.3.0 — `--no-collapse` shows every match line instead of one
  representative per near-identical cluster. Collapsing is right for
  orientation and wrong when the task is "edit each one of these 40 sites";
  without a way off it, the only complete list came from `cat FILE | grep`,
  which the guard hook denies. The flag widens the default, it does not
  defeat the budget: `--max-tokens` still caps matches per file, and says so
  (`(--no-collapse capped at N matches/file …)`). 2 new tests (30 total).
  Closes docs/known-issues/archive/guard-hook-cat-pipe-grep-inconsistent.md.
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
