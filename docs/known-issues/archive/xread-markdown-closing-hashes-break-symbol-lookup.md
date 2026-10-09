# xread keeps closing `#`s in markdown headings, so `--symbol` misses them

**RESOLVED 2026-10-09 (xread v0.6.0).** The closing `#` run is dropped from the heading name.

Filed 2026-10-08 from a full-suite review session.

## What broke

```markdown
# Title #

## Usage ##
```

```
$ xread doc.md --headings
doc.md:1  # Title #
doc.md:5  ## Usage ##

$ xread doc.md --symbol Usage
xread: symbol not found: Usage        # exit 2
```

The heading's name is `Usage`, and the trailing hashes are optional closing
syntax (CommonMark §4.2). `--symbol "Usage ##"` works, but nobody would
type that.

## Why

`_MD_HEADING` is `^(#{1,6})\s+(.+?)\s*$`, which keeps the closing run.
codediff's `_MD_HEADING_RE` already strips it (`\s*#*\s*$`), so the two
tools disagree about the same file's section names.

## What changed

Not fixed. Expected: strip a trailing `\s+#+` from the heading text, as
codediff does.
