# xread: --symbol unsupported for .prisma files

**RESOLVED 2026-07-17 (xread v0.2.0).** Added a flat block scanner for
`model|enum|type|view|generator|datasource NAME { ... }` with attached
`//` comments; strings are stripped before comments so braces in defaults
and `//` in datasource URLs don't derail spans.

**STATUS at filing: open.**

- **What broke:** `xread schema.prisma --symbol Verse` exits 2 with
  "unsupported file type for --symbol". Prisma schemas are block-structured
  (`model X { ... }`, `enum Y { ... }`) — exactly the shape symbol extraction
  is for, and a common target in Next.js/Prisma projects.
- **Session:** 2026-07-17, bible-atlas (Scripture reader build). Wanted the
  `Verse` and `Book` models out of a 600-line schema.
- **Fallback used:** bounded `Read` with offset/limit after locating the model
  with `sgrep "model Verse"` — two calls plus manual range guessing instead of
  one.
- **Suggested fix:** add a `.prisma` handler to xread's symbol extractor;
  a brace-matched `model|enum|generator|datasource NAME { ... }` grammar is
  enough. `--query` already returns prisma text fine, so this is only the
  symbol path.
