# factbook Testing

Fixture-based, per repo conventions (AGENTS.md). Every test runs against a
temp directory with its own `.factbook/`; nothing touches a real store.

## Fixtures

- Test helper creating temp repos with a working tree (for stale detection)
  and a scripted set of facts with known names, tags, and timestamps.
- A hand-written fact file missing optional front-matter fields, for the
  tolerant-parser round-trip.

## Test areas

- **add** — fact file created with slugged name, tags, created/updated
  timestamps; INDEX.md regenerated with the new one-liner; duplicate names
  handled predictably.
- **find** — field-weighted ranking (name > tags > body) verified with facts
  crafted to hit each field; tag filtering; `--full` expands bodies; empty
  result is a clean no-match message.
- **brief** — full INDEX printed; under `--max-tokens`, lowest-ranked lines
  trimmed whole (never mid-line), output within budget at descending caps.
- **edit / rm** — `$EDITOR` round-trip (stubbed editor) bumps `updated` and
  re-indexes; `rm` removes both fact file and index line.
- **stale** — a fact referencing a deleted fixture path is flagged; facts
  referencing live paths are not; nothing is auto-deleted.
- **Human edits** — the tolerant-parser fixture is searchable and indexable;
  INDEX.md regeneration preserves it.
- **Determinism** — index and find output ordering stable across runs.

## Running

`python -m pytest` from `tools/factbook/`.
