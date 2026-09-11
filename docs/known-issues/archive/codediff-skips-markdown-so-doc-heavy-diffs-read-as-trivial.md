# codediff: markdown files are counted but never analyzed, so a doc-heavy change summarizes as smaller than it is

**STATUS at filing: open. Resolved 2026-09-11 — see the resolution note at the end.**

- **What broke:** during a 2026-09-11 session (CFS-SPEC, Claude Code),
  `codediff` was run before a commit touching six files. Output header:
  `codediff: working tree vs HEAD (6 files)`, followed by API changes,
  behavior changes, and a test count for the two `.py` files — then a
  single line: `(4 files not analyzed: AGENTS.md, CHANGELOG.md, SPEC.md,
  STATUS.md)`. CFS-SPEC is a *specification* repo: the substantive half of
  that commit was a corrected rule in `SPEC.md` (a stated ceiling of "nine
  top-level entries" that contradicted its own layout listing thirteen) and
  a new gotcha in `AGENTS.md`. `codediff`'s summary conveyed none of it —
  read alone, the change looks like a 1-conditional tweak to `build()` plus
  two tests, when it is equally a change to the project's governing rules.
- **When it happens:** any repo where markdown is the artifact rather than
  the commentary — spec repos, docs sites, ADR-heavy projects, prompt/skill
  libraries, this repo's own `docs/known-issues/`. Also any ordinary code
  commit that changes a README contract or a CHANGELOG entry alongside the
  code, which is most commits in a project with `--strict`-style
  "docs are part of the diff" rules.
- **Why it happened (best available explanation):** `codediff` is built
  around a language-aware notion of change — symbols added/removed, call
  graph deltas, risk flags — and markdown has no such structure to parse,
  so it is correctly excluded from *that* analysis. The gap is that the
  exclusion is silent-by-summary: the file count in the header (`6 files`)
  promises coverage the body does not deliver, and the "not analyzed" line
  reads as a footnote rather than as "40% of this change is unsummarized."
  An agent using `codediff` as its pre-commit review — which is what the
  global instruction directs — gets a confident, incomplete picture and no
  prompt to look further.
- **What actually worked, for comparison:** nothing automated; the missing
  half was known only because the agent had made the doc edits itself
  minutes earlier. On a resumed session or a review of someone else's
  branch, it would have been invisible.
- **Recommended fix (either is useful; the first is cheap):**
  1. Make the omission louder and proportional: report unanalyzed files by
     share of the diff (`4 of 6 files / 61% of changed lines not analyzed`)
     rather than as a trailing parenthetical, so the summary states its own
     incompleteness.
  2. Add a markdown-aware pass — it does not need semantics, just
     structure: which `##` headings were added, removed, or had their body
     changed, plus a flag for edits inside fenced code blocks (commands in
     a README/AGENTS.md commands block are executable content and the
     highest-value markdown change to surface). Heading-level deltas would
     have rendered this commit as `~ SPEC.md: Layout (body changed)` and
     `+ AGENTS.md: Gotchas (+1 bullet)`, which is exactly the missing half.

---

## Resolution — 2026-09-11: fixed, both recommendations

Shipped in codediff v0.4.0 (ADR-009, `tools/codediff/DECISIONS.md`).

**1. The omission is proportional.** The trailing parenthetical is gone.
What remains unanalyzed is now stated as a share of the whole change —
`4 of 6 files, 61% of changed lines not analyzed` — computed from git's
own numstat, with untracked files filled in from their own line counts so
the denominator is honest. `--json` carries the same figures as
`unanalyzed_share`, so the narrator gets the incompleteness as a number
rather than as a list it has to weigh.

**2. Markdown gets a structural pass.** New `Doc changes` section: which
sections were added or removed, whose body moved (with a `+N`/`-N` line
delta), and — called out by name — whose fenced code changed, since a
command in a README or AGENTS.md block is executable content. A wholly
new or deleted document collapses to one line rather than enumerating
every heading, for the reason ADR-006 gives about new test files
(`archive/codediff-enumerates-every-new-test.md`).

Verified by dogfooding on this repo's own doc-heavy working tree: the
same change that previously reported *18 files not analyzed* now reports
1 (a `.toml` fixture), with 22 doc findings including
`~ structo (fenced code changed, body +2 lines)` on
`tools/structo/README.md`. 11 new tests, 49 total.
