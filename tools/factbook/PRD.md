# factbook PRD

## Problem statement

Every new agent session re-derives the same repo knowledge — "build with `make dev`, not npm", "auth logic lives in `pkg/auth`", "tests need Docker running" — at a large hidden token cost. `factbook` is a persistent per-repo store of durable facts with fast keyword recall, so knowledge learned once survives across sessions.

## Target users

- Coding agents persisting and recalling repo gotchas, build knowledge, and architecture notes across sessions.
- Human contributors who read and curate the fact store (it is plain markdown).

## Scope

### Storage model

- Facts live in `.factbook/` in the repo: one markdown file per fact carrying name, tags, body, and created/updated timestamps.
- An `INDEX.md` of one-line summaries, regenerated as facts change.
- Everything is plain markdown — human-editable and git-versionable.

### CLI surface

- `factbook add "fact text" --tags build,ci` — record a fact.
- `factbook find QUERY` — keyword + tag search over names and bodies, ranked; returns one-liners, `--full` to expand.
- `factbook brief` — print the whole INDEX, capped by `--max-tokens N`; designed to be injected at session start.
- `factbook edit NAME` / `factbook rm NAME` — maintain facts.
- `factbook stale` — flag facts referencing files/paths that no longer exist.

## Non-goals

- Automatic fact extraction from code or conversation; facts are added explicitly.
- Cross-repo or global knowledge storage; the store is per-repo.
- Embedding/vector search; recall is keyword and tag based.
- Duplicating what the repo already records (code structure, git history).

## Acceptance criteria

- `add` creates a well-formed fact file with name, tags, timestamps, and updates `INDEX.md`.
- `find` ranks matches over names, bodies, and tags; `--full` expands the fact body.
- `brief` prints the full index and respects `--max-tokens` by trimming lowest-value lines rather than cutting mid-line.
- `rm` and `edit` update both the fact file and the index.
- `stale` flags a fact referencing a deleted fixture path and leaves valid facts unflagged.
- The store round-trips through manual human edits (a hand-edited fact file is still searchable).
- Tests cover add/find/brief/stale flows.
