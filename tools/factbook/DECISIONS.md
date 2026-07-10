# factbook Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Plain markdown files over a database — Proposed

Context: the store's value depends on humans editing it and git versioning it;
fact counts per repo are small (tens to low hundreds).
Decision: one markdown file per fact with light front-matter; no SQLite, no
binary state; linear-scan search.
Consequences: human/git workflows are first-class; search performance is a
non-problem at realistic scale; the parser must tolerate hand-written files.

## ADR-002: INDEX.md is derived state, regenerated on every mutation — Proposed

Context: a hand-maintained index drifts; a stale index silently corrupts
`brief`, the highest-value command.
Decision: every CLI mutation rewrites INDEX.md from the fact files; the index
is never edited directly.
Consequences: index can always be rebuilt; hand edits to INDEX.md are
overwritten by design (documented behavior).

## ADR-003: Keyword + tag search, no embeddings — Proposed

Context: recall must be fast, offline, dependency-free, and explainable.
Decision: field-weighted keyword matching (name > tags > body); no vector
search.
Consequences: zero infrastructure; recall quality depends on fact naming and
tagging discipline, which `find`'s ranking rewards.

## ADR-004: stale is advisory only — Proposed

Context: path references rot, but auto-deleting knowledge is worse than
flagging it.
Decision: `stale` reports facts whose referenced paths no longer exist;
removal stays a human/agent choice via `rm`.
Consequences: the store never loses data without an explicit command.
