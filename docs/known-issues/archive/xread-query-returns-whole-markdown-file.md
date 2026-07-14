# xread: `--query` on a markdown heading phrase returns the whole file

**RESOLVED 2026-07-11 (xread v0.1.1):** query blocks are clamped at the
next top-level symbol, so markdown sections tile the file and the H1's
whole-document span no longer competes with the subsection a query is
aimed at. Scoring also gained whole-word keyword-coverage weighting
(`building` no longer counts as a hit for `build`), which the START.md
reproduction needed to rank the right section first, not merely avoid
the whole file. `xread START.md --query "Suggested build order" --top 1`
now returns exactly START.md:180-189.

**What breaks:** `xread START.md --query "Suggested build order"` printed
`== START.md:1-189 ==` — the entire ~5k-token file — instead of the ~15-line
`## Suggested build order` section (START.md:180). The tool's purpose
(targeted excerpt instead of a whole-file read) was defeated exactly when it
mattered: the follow-up to a `--headings` call, drilling into one section.

**When it happens:** querying a phrase that appears in a section nested
under a document-spanning H1. Likely mechanism: markdown blocks are
heading-delimited sections, the H1's section spans the whole document, it
contains the query phrase too, and it outscores (or ties and outranks) the
small H2 section that is the right answer. Found 2026-07-10 dogfooding
against this repo's own START.md.

**Expected:** the most specific matching section should win — score leaf
sections first, or exclude a parent section's body when a child section
also matches. A `--query` result should approach the size of the relevant
section, not the file; degrading to whole-file output should never happen
while a smaller matching block exists.

**Workaround:** use `--headings` to get the section's line number, then
`--lines A-B`. That is two invocations and requires guessing the section
end line.
