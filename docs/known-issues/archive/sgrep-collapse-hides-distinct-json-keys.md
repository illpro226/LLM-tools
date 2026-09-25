# sgrep: collapse merges distinct JSON keys into "(+N more similar)", hiding the line that was needed

**RESOLVED 2026-09-24 (sgrep v0.6.0)** Every cluster now gets a
representative, and `--max-tokens` does the size capping. When the budget
does hide distinct lines, the footer says `(+N more, D distinct)` instead of
"similar". The "Why" section below had a wrong guess at the cause; the
actual cause is recorded here.

**Actual cause:** normalization was fine. `normalize()` only collapses
whitespace and digit runs, so the six keys stayed six clusters. The bug was
in `select_matches`: any file with more than 5 matches showed at most
`REPRESENTATIVES = 3` clusters, whatever the budget, and the footer called
everything else "similar". Second repro from the same day, while fixing
this: `sgrep -n 'collapse|similar|def ' sgrep.py` showed 2 of 30 distinct
lines under "(+27 more similar)".

Status: fixed
Fixed: 2026-09-24
Opened: 2026-09-24

## What broke

I searched `~/.claude.json` for the setting that turns Claude in Chrome on:

```
> sgrep -i chrome "$HOME\.claude.json"
== C:/Users/MainUser/.claude.json (6 matches) ==
C:/Users/MainUser/.claude.json:213:     "tengu_chrome_install_upsell": true,
C:/Users/MainUser/.claude.json:472:     "tengu_cowork_chrome_automode_default": true,
C:/Users/MainUser/.claude.json:1105:     "tengu_chrome_auto_enable": true,
(+3 more similar)
```

The three hidden lines were `cachedChromeExtensionInstalled`,
`claudeInChromeDefaultEnabled` (the key the task needed) and
`hasCompletedClaudeInChromeOnboarding`. Those are different keys that happen
to have the same `"key": bool,` shape. With `--no-collapse`, sgrep printed all
6 lines in about the same space. For 3 hidden lines, collapsing saved almost
no tokens and dropped the answer.

The agent didn't know about `--no-collapse`. It hit a guard-hook deny on
`Get-Content | Select-String`, then used `ConvertFrom-Json` in PowerShell to
find the value, which cost 3 extra round-trips.

## Why

Collapse seems to cluster lines by their shape (key/value JSON lines), not by
the words in them. Different key names inside the same shape count as
"near-identical". It also collapses even when the whole result is tiny
(6 matches), where collapsing can't save anything that matters.

## What changed

Not fixed. Options:
- Don't collapse when the uncollapsed output fits inside `--max-tokens`, or
  when there are only a few matches (e.g. 10 or fewer).
- Count differing identifiers/keys as a real difference when clustering.
- Make the `(+N more similar)` line name the flag, e.g.
  `(+3 more similar; --no-collapse to show)`.
