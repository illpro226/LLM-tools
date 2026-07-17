# xread: --query matches a heading but omits the code block under it

**RESOLVED 2026-07-17 (xread v0.2.0).** A returned markdown region that
starts at a heading now extends back over the immediately preceding
same-level sibling section when it is short (≤ 20 lines) and carries a
fenced block — the suggested fix, gated on the fence so plain prose
siblings still score on their own merits.

**STATUS at filing: open (minor).**

- **What broke:** in a spec markdown (`PHASE_13_API.md`), `--query "error
  envelope error codes NOT_FOUND"` and `--query '### Error'` both returned the
  "### Error Codes" table but not the "### Error" section directly above it,
  whose fenced JSON block (the error envelope shape) was the actual target.
  The JSON contains none of the query terms except inside the fence, and the
  section heading itself apparently scored below its sibling.
- **Session:** 2026-07-17, bible-atlas. Needed the error envelope JSON to
  implement an API route faithfully.
- **Fallback used:** `sed -n '65,78p'` after the second miss showed the block
  sat just above a returned match — the returned line ranges made the gap
  findable, which is a partial win.
- **Suggested fix:** when a matched region starts at a heading, include the
  immediately preceding sibling section if it shares the parent heading and is
  short (< ~20 lines); or weight fenced-code content into section scoring.
