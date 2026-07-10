# factbook Roadmap

## M1 — Scaffold and store

- CLI entry point, test harness with temp `.factbook/` dirs.
- Fact file format + tolerant parser; `add` with slugging, tags, timestamps.
- INDEX.md regeneration on every mutation.

## M2 — Recall

- `find` with field-weighted keyword + tag ranking; `--full` expansion.
- `brief` with `--max-tokens N` trimming rules.

## M3 — Maintenance

- `edit` ($EDITOR round-trip with re-index) and `rm`.
- `stale` path-existence detection over fact bodies.

## M4 — Hardening

- Hand-edited-file round-trip tests; deterministic ordering tests;
  add/find/brief/stale coverage per the PRD.

## Later

- Optional session-start hook snippet for agent configs (CLAUDE.md et al.).
