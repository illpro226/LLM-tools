# docsnip Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Local installations are the only doc source — Proposed

Context: web docs drift from the installed version; the correct answer is
already on disk.
Decision: resolve exclusively against installed packages (virtualenv /
node_modules); no network, ever.
Consequences: answers are version-accurate by construction; uninstalled
packages are a clean error with an install hint, not a web lookup.

## ADR-002: Static-first extraction, import as last resort — Proposed

Context: importing a package executes its module-level code — a safety and
speed cost.
Decision: parse source statically for signatures/docstrings; import only when
static resolution fails, and never execute beyond import.
Consequences: safe on untrusted packages in the common path; some
dynamically-generated APIs only resolve via the import fallback.

## ADR-003: .d.ts preferred over source for npm — Proposed

Context: type declarations are the densest, most reliable signature source in
the JS ecosystem.
Decision: resolve via package.json `types`/`typings` first; fall back to JSDoc
in source. Parse `.d.ts` with tree-sitter's TypeScript grammar rather than
embedding a TS toolchain.
Consequences: best-quality signatures where types exist; untyped packages get
best-effort JSDoc output.

## ADR-004: Cache keyed by package version — Proposed

Context: extraction is repeated across sessions; package content only changes
on version change.
Decision: `~/.cache/docsnip/` keyed by (ecosystem, package, version, query),
storing the rendered model, not raw source.
Consequences: upgrades invalidate naturally; no TTL logic; cache is safe to
delete at any time.
