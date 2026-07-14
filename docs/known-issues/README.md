# Known Issues

Track open limitations, bugs, and implementation caveats here.

Use one file per issue with:

- what breaks or is incomplete
- when it happens
- the expected behavior
- a workaround, if one exists

Prefer concise entries that can be turned into tasks later.

## Resolving an issue

When a fix ships, don't delete the file — annotate it in place, then move it
to `archive/`:

1. Add a status line at the top: `**RESOLVED <date> (<tool> v<version>)**`
   (or `FIXED <date>` for infra/hook issues) plus a one- or two-sentence
   summary of the fix. Leave the original repro/impact below it as a record.
2. `git mv docs/known-issues/<file>.md docs/known-issues/archive/<file>.md`.
3. Fix any cross-links to the old path (decision records, CHANGELOGs) so
   citations still resolve.

This directory (`docs/known-issues/`, unqualified) is a live index of what's
currently broken — it should only ever contain open issues, so searching it
doesn't turn up noise from things already fixed. `archive/` keeps the record
for anyone tracing why a decision or fix happened, without polluting the
open list. A `MITIGATED` issue (a real fix shipped but the underlying risk
isn't fully closed out) stays in the open list, not the archive, until it's
confirmed resolved.
