# 0005: Token budgets are on by default in every tool

Status: Accepted (2026-07-31)

## Decision

Every tool that can produce unbounded output ships a non-zero
`--max-tokens` default. `--max-tokens 0` restores the previous unbounded
behaviour, and remains available for the rare caller who wants everything.

| tool | default | note |
|---|---:|---|
| `sgrep` | 1500 | highest-frequency, cheapest per call |
| `xread` | 2000 | |
| `structo` | 2000 | schema output only; `--select`/`--raw` exempt |
| `gitbrief` | 2000 | |
| `repomap` | 3000 | a whole-repo orientation legitimately needs more |
| `codediff` | 3000 | `--json` stays full |

`runlite`, `tokq`, `rq`, `testmap` and `repoindex` keep an unbounded
default: their output is already bounded by construction (a failure
report, a metering table, a query result), and measured per-call output
sits between 40 and 100 tokens.

## Why

The degradation ladders were built, tested, and documented in every tool —
and then almost never ran. Across 661 logged suite calls in the first 18
days of use (`.savings/events.jsonl`), **9 calls passed `--max-tokens`:
1.4%.** Meanwhile 19 calls emitted more than 2000 tokens each, 74,622
tokens in total — roughly 8% of everything the suite printed, produced by
3% of its calls.

An opt-in cap protects only the caller who already suspected the output
would be large. That is precisely the caller who did not need protecting.
The calls that flood a context window are the ones nobody expected to:
`gitbrief hunks` on a working diff that grew, `repomap` on a repo bigger
than the last one, `sgrep -C 12` on a pattern that turned out to be
common. Measured on this repo, the defaults cut `repomap .` from ~15,000
to ~2,900 tokens and `gitbrief hunks` from ~2,900 to ~310, with no flag
passed.

This is what the suite is *for*. A tool whose stated purpose is to keep
raw bulk out of an agent's context, but which emits raw bulk unless asked
twice, is not doing the job — it is offering to.

## Exemptions, and why they are narrow

Machine-readable output is exempt from the *default* only, never from an
explicit `--max-tokens`:

- **`structo --select` / `--raw`** feed `awk`/`sort` and already refuse
  rather than truncate when over budget (ADR-004/005). A default cap would
  turn an ordinary `structo --select … | awk` into an error.
- **`codediff --json`** is the narrator payload; a truncated payload is
  not parseable.

## Consequences

- Degradation must be *visible*. A cap that silently removes what was
  asked for is worse than no cap: dropped context reads as absent context,
  and the caller concludes the surrounding lines do not exist rather than
  that they were trimmed. Every tool already announced most rungs; `sgrep`
  gained an explicit `(context reduced N -> M for --max-tokens N)` line,
  and every degradation note names the flag so the cap can be raised.
- Two latent bugs surfaced while testing the defaults and were fixed:
  `structo`'s ladder bottomed out at one line per top-level key, so a wide
  record ignored *any* budget (a 4000-key object emitted ~12,800 tokens
  against `--max-tokens 200`); and `xread` dropped its sole region
  entirely when no blank line was available to trim at, returning a note
  and nothing else.
- The defaults are calibrated from measured per-call output, at roughly
  the 95th percentile of real use, so ordinary calls are untouched. Each
  tool's suite asserts this directly: a small input must produce
  byte-identical output with and without the default.

## Revisit if

Recorded evidence in `docs/known-issues/` shows a default clipping
answers that mattered — a cap that regularly hides the thing the caller
was looking for is worse than the flood it prevents.
