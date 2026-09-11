# guard hook: `cat FILE` is denied but `sed -n 1,<EOF>p FILE` dumps the same whole file and is allowed

**STATUS at filing: open. Resolved 2026-09-11 — see the resolution note at the end.**

- **What broke:** during a 2026-09-11 session (CFS-SPEC, Claude Code), the
  agent ran `cat SPEC.md STATUS.md README.md` and was denied with the
  standard redirect: *"`cat FILE` dumps the whole file. Use `xread FILE
  --symbol NAME | --query "..." | --headings` (docs), `structo FILE` for
  JSON/YAML/XML, or a bounded Read with offset/limit."* The agent's very
  next call was `sed -n 1,163p SPEC.md` — 163 being the file's exact line
  count, taken from a `wc -l` run moments earlier — which the hook
  **allowed**. It then did the same thing four more times in the same
  session: `sed -n 1,129p scripts/cfs_init.py`, `sed -n 1,199p
  template/scripts/check_status.py`, `sed -n 1,189p
  tests/test_cfs_init.py`, `sed -n 1,46p template/AGENTS.md`. Every one of
  those is a complete file dump wearing a range flag. **`xread` was never
  invoked once in the entire session**, despite the hook firing to redirect
  toward it.
- **When it happens:** any time the hook denies `cat` and the agent reaches
  for `sed -n`/`head -n`/`awk NR<=` with a range that covers the file. The
  bypass is not adversarial and that is the point — `sed -n START,ENDp` is
  the *normal* idiom for a bounded read, so an agent complying in good
  faith with "use a bounded read" lands on it immediately. When the range
  happens to span the whole file, the hook's stated intent is defeated by
  the very command its own message recommends in spirit.
- **Why it happened (best available explanation):** the hook matches on
  command name (`cat`) rather than on *effect* (bytes about to enter
  context). `sed -n 1,163p` and `cat` produce byte-identical output, so the
  only thing separating a denial from an allow is which binary is spelled
  in argv. This is the same enforcement-gap shape as the resolved-by-
  precedent `python -m json.tool` issue: a stdlib CLI reaching the blocked
  outcome by a route the blocklist doesn't enumerate. It is *not* the same
  as `bounded-builtin-calls-treated-as-equivalent-to-sgrep.md` — that one
  is about genuinely-bounded calls the carve-out intentionally permits and
  whether the agent should still prefer the suite tool. This one is an
  unbounded read passing as bounded.
- **Aggravating factor:** the agent had the file's line count in context
  from `wc -l` before choosing the range, so the range was *derived from*
  the file size in order to capture all of it. A heuristic that flags
  "range end >= file line count" would have caught every instance here.
- **What actually worked, for comparison:** `tokq dir template` and
  `codediff` were both reached for unprompted and used correctly in the
  same session — no denial needed. Both produce output with no builtin
  equivalent, so there was no trained-in default competing with them. The
  tools that lose are the ones whose job a builtin *appears* to do.
- **Recommended fix:**
  1. Extend the hook's whole-file-dump matcher beyond `cat` to cover
     `sed -n`, `head`, `tail`, and `awk` invocations whose range is
     unbounded or open-ended (`sed -n 1,$p`, `sed -p` with no range,
     `head` with no `-n`, `head -n` above a threshold). Low risk: bounded
     reads of a few dozen lines keep working.
  2. Where the file's length is cheaply knowable, deny when the requested
     range covers (or nearly covers) the whole file, regardless of which
     command asked. The denial message should say so explicitly —
     "a range covering the whole file is a whole-file dump" — because the
     agent in this session believed it was complying.
  3. Add both shapes to the guard-hook regression corpus in
     `scripts/test-guard-hook.py`.

---

## Resolution — 2026-09-11: fixed

All three recommendations implemented in `hooks/llm-tools-guard.py`.

1. The whole-file-dump matcher now covers `sed`, `head`, `tail` and `awk`
   at command position (`RANGE_READ_RE`). A range read is denied when it
   exceeds `MAX_RANGE_LINES` (60 — the issue's own "a few dozen lines"
   standard), when it has no upper bound at all
   (`sed -n 1,$p`, `tail -n +40`, `sed` without `-n`, which prints every
   line it reads), or — recommendation 2 — when the range provably covers
   a named file's whole length. That last check is what catches
   `sed -n 1,46p template/AGENTS.md` on a 46-line file, which no flat cap
   can; `_line_count` returning None ("can't answer cheaply") is treated
   as no opinion, leaving the flat cap to decide. "Covers" is
   `WHOLE_FILE_FRACTION = 0.8`, not 1.0, per the filed wording "covers (or
   nearly covers)".

   Both constants were set by being caught: a first pass used a cap of 100
   and an exact-coverage test, and while smoke-testing the deployed hook
   the *same bypass shape* — `wc -l` then `sed -n 1,59p` on a 73-line file
   — was allowed again. 59 under a cap of 100, and 59 < 73. That case is
   now in the corpus.
2. The denial message says outright that *"a range covering the whole
   file is a whole-file dump"* and names what stays allowed, because the
   agent in the filed session believed it was complying.
3. All the filed bypass shapes, plus the carve-outs around them, are in
   `scripts/test-guard-hook.py` (80 cases). The differential run against
   the pre-change hook reports every flip as a tightening and no
   DENY -> ALLOW regression.

Two details worth keeping: the range is parsed from the **raw** command
rather than the masked one (masking blanks a quoted `'1,163p'` script
while preserving offsets), while the redirect/pipe carve-outs still read
the masked pipeline, so a `>` inside quotes cannot vouch for anything.
And matching at command position only means `... | sed -n 1,163p` — a
genuine pipeline filter — is untouched.
