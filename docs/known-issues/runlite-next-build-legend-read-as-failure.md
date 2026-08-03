# runlite: Next.js build legend reported as a test failure

**Date:** 2026-08-02
**Tool:** runlite
**Status:** Open

## What I tried

```
runlite -- npm run build
```

on a Next.js 15 app (`next build`). Output, on three separate fully successful
builds:

```
# runlite: exit 0 in 26.13s (jest/vitest) 1 problem

FAIL (SSG)      prerendered as static HTML (uses generateStaticParams)
  ƒ  (Dynamic)  server-rendered on demand
```

Two things are wrong. The extractor picked is `jest/vitest` for a command that
runs no test framework, and the "1 problem / FAIL" it reports is the route-type
legend `next build` prints at the end of every build:

```
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand
```

The `●` bullet appears to be matched as a failure marker and rewritten to
`FAIL`. Nothing failed; the build exited 0.

## Expected

`exit 0` and a summary that says the build succeeded, with the route table
either summarized or omitted. At minimum, a non-empty "problems" list should
never be produced from a run that exited 0 with no matching framework — the two
signals contradict each other, and the exit code is the reliable one.

## Impact / workaround

Actively misleading rather than merely unhelpful: the headline says a build
passed and the body says `FAIL`, and the natural reading of a runlite summary
is that the body is the detail. I only trusted the build because I had the exit
code on the same line. In a longer session this is exactly the shape of thing
that gets reported to a user as "the build is failing".

Workaround: read `exit N` and ignore the rest for `next build`, or run
`npm run build` unwrapped and tail it.

Fix suggestions, in order of value:

1. Never emit `FAIL`-prefixed problems when the wrapped command exited 0 —
   whatever the extractor found, the run succeeded.
2. Do not select the jest/vitest extractor for `next build` / `npm run build`;
   detect it as a build and summarize the route table (route count, first-load
   JS) rather than pattern-matching it for failures.
3. If the bullet-to-`FAIL` mapping is a general rule, restrict it to line
   starts followed by a test-name shape, not to any `●`/`○`/`ƒ` glyph.
