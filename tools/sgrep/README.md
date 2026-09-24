# sgrep

Token-budgeted search condenser: a ripgrep wrapper that turns a 3,000-line
grep dump into a short ranked digest. Matches are grouped by file,
near-identical hits are deduplicated, and files rank by match count × path
class — src before tests before generated.

Single-file Python CLI, stdlib in-process; requires the `rg` binary at
runtime (PATH, `--rg BIN`, or `SGREP_RG`). Matching is never reimplemented.

## Usage

```
sgrep PATTERN [PATH...]           # condensed, ranked digest
sgrep PATTERN --files-only        # ranked matching-file list (cheapest)
sgrep PATTERN --counts-only       # ranked list with match counts
sgrep PATTERN --no-collapse       # every match line, not one per cluster
                                  # (for "edit each of these" work)
sgrep PATTERN --max-tokens N      # reduce: context lines, then matches
                                  # per file, then files shown
sgrep PATTERN -C 2 -i -F -w -t py -g '*.rs'   # small rg pass-through set
```

Exit codes follow grep: 0 matches, 1 none, 2 error. When rg fails on some
paths (unreadable file, mistyped path) but matched in others, the matches
are still printed and the error goes to stderr with exit 2.

### Example

```
$ sgrep max_tokens tools --max-tokens 150
== tools/xread/xread.py (8 matches) ==
tools/xread/xread.py:397: def apply_budget(regions, sources, max_tokens):
(+7 more similar)

== tools/tokq/tokq.py (7 matches) ==
tools/tokq/tokq.py:244:     _emit(lines, args.max_tokens)
(+6 more similar)
...
```

With `-C N`, match lines keep the full `path:line:` prefix and context
lines carry a bare right-aligned line number instead:

```
$ sgrep "def apply_budget" tools/sgrep -C 2
== tools/sgrep/sgrep.py (1 match) ==
260-
261-
tools/sgrep/sgrep.py:262: def apply_budget(ranked, files, args):
263-     """ADR-003: reduce context, then matches per file, then files shown."""
264-     ctx = args.context
```

The block header already names the file, and a context line makes no claim
of its own — repeating the path on each one was most of sgrep's per-line
overhead against a raw `rg` dump.

A file with more than 5 matching lines shows one representative per
distinct normalized form (whitespace collapsed, digit runs equalized), 3 at
most, plus a `(+N more similar)` remainder — the loss is visible and
recoverable via raw `rg`.

## Configuration

Optional `.sgrep.toml` in the working directory (or `--config PATH`):

```toml
[weights]
tests = 0.8          # src / tests / generated class weights

[classes]
generated = ["*.snap"]   # extra fnmatch patterns per class
```

## Development

```
python -m pytest        # from tools/sgrep/
```

Parser, dedupe, ranking, and budget tests run against canned `rg --json`
streams in `tests/fixtures/rg-output/` and never need ripgrep; the
end-to-end tests use a real `rg` and skip with a notice when it is not
installed. See the repo root `START.md` for suite-wide conventions.
