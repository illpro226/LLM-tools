# xread --symbol cannot find a TypeScript `export const`, so the 2026-09-11 constants fix stops at Python

**RESOLVED 2026-10-09 (xread v0.6.0).** Module-level `const`/`let`/`var` are `constant` symbols spanning their initializer; all four shapes below resolve (fixture `module_consts.ts`).

Filed 2026-10-06 from a bible-atlas session.

## What happened

`archive/xread-symbol-misses-module-level-constants.md` was resolved for Python
only (`parse_python` collects `Assign`/`AnnAssign`). In a Next.js codebase most
of the names an agent arrives with are module-level `const` bindings, and none
of them resolve:

```
$ xread src/lib/dashboard.ts --symbol getVerseOfTheDay
xread: symbol not found: getVerseOfTheDay
$ xread src/lib/entities.ts --symbol LIST_CONFIG
xread: symbol not found: LIST_CONFIG
$ xread src/lib/dashboard.ts --symbol ROTATION
xread: symbol not found: ROTATION
$ xread src/lib/stripe.ts --symbol GRANTING_STATUSES
xread: symbol not found: GRANTING_STATUSES
```

The four shapes, all at module level, all exported:

- `export const getVerseOfTheDay = cache(async (): Promise<…> => { … })` — a
  function in all but syntax; React's `cache()` and Next's route helpers make
  this common.
- `export const LIST_CONFIG: Record<EntityTypeSlug, { … }> = { … }` — typed
  object literal.
- `const ROTATION: [book: string, chapter: number, verse: number][] = [ … ]` —
  multi-line array literal under a doc comment.
- `export const GRANTING_STATUSES: ReadonlySet<string> = new Set([…])`.

`export function` and `export async function` resolve fine in the same files.

## Cost

Each miss fell back to `sgrep` for the line number and a bounded `Read` around
it — two calls and a guessed span instead of one exact lookup, the same cost
the Python fix removed.

## Expected

The TypeScript/JavaScript parser collects module-level `const`/`let`/`var`
declarators (with or without `export`, with or without a type annotation) as
`constant` symbols, spanning the whole initializer plus an attached doc
comment, as the Python parser now does.
