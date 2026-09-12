# 0010 — No `.env.example`, because nothing reads a `.env`

Status: accepted
Date: 2026-09-11

## Context

The CFS audit (`cfs_check.py --adopt`) reports:

> no `.env.example` at the root or one level down, but the code reads the
> environment - secrets must be TOCH_ placeholders in a tracked example,
> resolved outside the repo

The rule is right for an application. It is wrong here, and the reason is worth
recording rather than re-deriving.

## What the code actually reads

Three variables, across three tools:

| variable | tool | effect |
|---|---|---|
| `SGREP_RG` | `sgrep` | Path to the `rg` binary when it is not on PATH (also `--rg`) |
| `GITBRIEF_NO_CEILING` | `gitbrief` | Lifts the `$HOME` git-discovery ceiling |
| `CODEDIFF_NO_CEILING` | `codediff` | The same, for `codediff` |

All three are behaviour toggles. None is a secret. None has a value that could
be checked in wrongly, because none has a value worth protecting — `SGREP_RG` is
a path on the caller's machine and the other two are booleans.

More to the point: **nothing in this repo loads a `.env` file.** There is no
`dotenv` dependency; the suite is stdlib-only by invariant. A `.env.example` here
would be a file that documents an environment nobody assembles, in a format
nothing consumes.

## Decision

No `.env.example`. The three variables are documented in
`docs/reference/REF-tool-gotchas.md` § Environment variables, next to the
behaviour they change, which is where someone looking for them will be.

## Consequences

- **LLM-tools fails the audit on this, permanently, by choice.** Once the rest of
  the contract landed the finding was promoted from an `--adopt` suggestion to a
  hard DRIFT finding:

  ```
  DRIFT LLM-tools  (1 finding)
          no .env.example at the root or one level down, but the code reads
          the environment
  ```

  Do not add an empty `.env.example` to silence it. A file documenting an
  environment nobody assembles is worse than a finding with a reason attached.
- If a tool ever grows an API key — the MCP adapter in `docs/decisions/0004` is
  the plausible route — this decision is superseded, not edited, and a real
  `.env.example` with `TOCH_` placeholders lands with it.
- Raised upstream as CFS-SPEC DEC-0012: the audit infers "reads the environment"
  from `os.environ` calls, which cannot distinguish a secret from a toggle.
