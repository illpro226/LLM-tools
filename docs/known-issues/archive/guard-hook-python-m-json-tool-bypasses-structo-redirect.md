# guard hook: `python -m json.tool` bypasses the structo redirect, and structo's own shape doesn't obviously fit "diff two whole files" anyway

**STATUS at filing: open. Resolved 2026-09-11 — see the resolution note at the end.**

- **What broke:** during a 2026-08-23 session (des_stack/fixpoint, Claude
  Code), the agent needed to compare two versions of the same JSON file
  (a manifest fetched from a remote host vs. the local copy) to see if the
  content actually differed or only the key ordering/formatting did. It
  first tried `python -c "import json; json.dump(json.load(open(...)), ...,
  indent=2, sort_keys=True)"` for both files, which the guard hook denied
  with the standard structo redirect message. The agent's very next move
  was `python -m json.tool --sort-keys <file>` — a different command,
  **not covered by the hook's block list** — piped to a temp file, then a
  plain `diff -u` between the two normalized outputs. This worked, so the
  agent never actually invoked `structo`.
- **When it happens:** any time the immediate need is "normalize two (or
  more) whole JSON files the same way and diff them," rather than "read
  one value out of one file." `structo FILE --path a.b[0].c` is a clean
  fit for the latter; it's not obvious from the hook's redirect message or
  from `structo --help`-level familiarity that it's *also* the right tool
  for the former, so the agent reached for a stdlib one-liner it already
  knew would produce comparable output instead of pausing to check.
- **Why it happened (best available explanation):** two compounding
  causes, not one:
  1. **Enforcement gap.** The hook's blocklist for ad-hoc JSON parsing
     matches `python -c` (and presumably `node -e`) but not
     `python -m json.tool`, which is a stdlib CLI, not inline code, and
     achieves the same "avoid learning the new tool" outcome. This is the
     same shape as the resolved `agent-defaults-to-builtins-mid-task`
     issue's core finding — mechanical enforcement at the decision point
     is what changes behavior, not agent judgment — except here the
     mechanical enforcement itself has a gap, so the lesson from that
     issue didn't get a chance to apply.
  2. **Ergonomic uncertainty, independent of the gap.** Even granting the
     hook had blocked `python -m json.tool` too, the agent had no local
     evidence that `structo` handles "normalize + diff two files" well —
     every example it could recall from the redirect messages and prior
     `structo` usage in-session was single-value extraction
     (`--path a.b.c`). Closing the enforcement gap alone would likely have
     produced a *different* workaround, not necessarily `structo` use,
     unless the tool's own help text or the hook's redirect message names
     this use case explicitly.
- **What actually worked, for comparison:** `gitbrief hunks <file>` was
  used successfully ~7 times in the same session for the analogous "diff
  two versions of a file" need in the git-history case, with no lapses —
  because the hook blocks the raw `git diff`/`cat` path *and* `gitbrief`'s
  own output format made it obvious it was the right choice for that job.
  The JSON case had the first property partially (one bypass) and not
  the second at all.
- **Recommended fix:**
  1. Extend the guard hook's ad-hoc-JSON-parsing block to also match
     `python -m json.tool` (and `node -e`/equivalents doing the same
     normalize-and-print job), not just inline `-c`/`-e` code, per the
     precedent that a tool nothing enforces loses to the trained-in
     default under task pressure.
  2. Separately from the hook fix, add a "diff two JSON files" example to
     `structo`'s own `--help` output and to the guard hook's redirect
     message specifically for this shape — e.g.
     `structo A.json --diff B.json` or documented guidance to run
     `structo` on each file with a shared normalization flag and diff the
     results — so an agent that does get redirected has an unambiguous
     next step instead of reconstructing one from stdlib knowledge.

---

## Resolution — 2026-09-11: recommendation 1 fixed, recommendation 2 partly

**1. Enforcement gap closed.** `JSON_TOOL_RE` in
`hooks/llm-tools-guard.py` now matches `python -m json.tool` (and the
`python3`/`py` spellings, with intervening flags) and denies it with the
structo redirect. Scoped per match like the other rules, and carved out
when the output is redirected to a file or piped through `head`/`tail`/
`wc` — normalizing *to a file* costs no tokens and is a legitimate move.
Five cases added to `scripts/test-guard-hook.py`.

This was the same enforcement-gap shape as the `sed -n 1,$Np` bypass
filed the same way (see
[`guard-hook-sed-range-read-dumps-whole-file.md`](guard-hook-sed-range-read-dumps-whole-file.md)):
a stdlib CLI reaching a blocked outcome by a route the blocklist did not
enumerate. Both were fixed together.

**2. Ergonomic uncertainty: addressed in the message, not in structo.**
The redirect message now names the two-file recipe explicitly — `structo
A.json` vs `structo B.json` for "same shape?", and `structo F --select
f1,f2 > f.tsv` on each plus a diff of the two files for values — so a
redirected agent has an unambiguous next step instead of reconstructing
one from stdlib knowledge.

A `structo A.json --diff B.json` flag was **not** built. It is a real
feature with its own design questions (what counts as a difference:
schema, values, ordering?) and the evidence for it is one session. The
message-level fix is the cheap half; if the recipe still loses to
`json.tool`-shaped defaults in a later session, file that and the flag
becomes justified.
