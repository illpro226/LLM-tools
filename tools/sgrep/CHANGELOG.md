# sgrep Changelog

- 2026-09-24: v0.5.0 — four fixes found by a suite review, each with a
  regression test that fails on v0.4.1.
  **The budget ladder was quadratic in matching files.** The file-count rung
  stepped down one file per full re-render, so a search matching 3,000
  files took 30 s to fit the default budget and one matching 20,000 took
  7 min 41 s. It is now a binary search (rendered size grows with every
  kept file, so it lands on the same answer — pinned against the old
  linear scan); the 20,000-file search takes 3 s. The counts-row floor now
  keeps a running byte count instead of re-measuring each candidate.
  **A full stderr pipe hung sgrep forever.** stderr was read only after
  stdout hit EOF; rg writes a line per unreadable path, and once that pipe
  filled rg blocked mid-write while sgrep waited on stdout. stderr now
  drains on a thread, and only the first 5 lines are quoted.
  **One bad path discarded every match.** rg exits 2 for any error — a
  mistyped path argument, one unreadable file — even when every other path
  searched fine, and sgrep raised on that exit code. Matches are now
  printed, the error goes to stderr, and the exit stays 2 (grep's
  convention).
  **`--files-only` dropped files silently.** Trimmed to fit the budget it
  printed the first N paths with no marker, so a 3,000-file result read as
  a 315-file one. It now ends with the digest's `(+N more files with M
  matches)` line. Also: `-n` is accepted and ignored (line numbers are
  always shown) instead of costing a round-trip as an argparse error —
  found by typing it from grep habit during the same review. 7 new tests
  (40 total).
- 2026-08-06: v0.4.1 — paths are normalized to forward slashes at ingest.
  `rg` echoes the separator of the path it was given, so on Windows a
  directory search printed `tools/sgrep\sgrep.py` while naming the file
  printed `tools/sgrep/sgrep.py`, and passing both put both forms in one
  output. Nothing broke — either spelling is valid input to `xread` — but
  a `path:line` reference is a stable identifier by INVARIANTS, and two
  references to one file must not compare unequal as strings. Normalizing
  at the parser (not the render sites) also makes the dict key canonical,
  so per-file counts and ranking can't split one file into two entries.
  Same class as archive/tokq-dir-backslash-paths-on-windows.md. 1 new test
  (33 total). Closes
  docs/known-issues/archive/sgrep-mixed-path-separators-on-windows.md.
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
