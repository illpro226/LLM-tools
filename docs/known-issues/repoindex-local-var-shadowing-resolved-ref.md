# repoindex: local variable shadowing produces a false `resolved` ref

**RESOLVED 2026-07-10 (repoindex v0.1.2), for Python:** the extractor now
records calls through names bound in the enclosing function (assignments,
parameters, nested defs, `except`/`nonlocal` bindings) as `<dynamic>`, so
the resolve pass keeps them heuristic instead of binding them to an
unrelated repo-wide symbol; the repomap.py:461 phantom ref is gone.
Residual: the JS/TS and Go heuristic extractors don't track locals, so the
same class of phantom ref remains possible in those languages.

**What breaks:** a call through a local variable that shares a name with a
repo-wide symbol is recorded as a `resolved` ref to that unrelated symbol.
Found via dogfooding: `tools/repomap/repomap.py:461` calls `extract(source,
lines)` where `extract` is a local variable assigned at
`tools/repomap/repomap.py:445` (`extract = extractor_for(ext)`). repoindex
records this as a ref to `tools/repoindex/repoindex/extract.py::extract`
with `confidence=resolved` — repomap never imports repoindex at all.

**When it happens:** whenever a function-local assignment shadows a name
that the repo-wide resolution pass can bind to a symbol elsewhere in the
repo. Surfaces in `rq whouses` / `rq impact` as phantom callers.

**Expected:** local assignments should shadow: either no ref, or at most a
`heuristic` one. Marking it `resolved` violates INVARIANTS.md ("uncertainty
is stored, not hidden — and not inflated").

**Workaround:** treat cross-tool `resolved` refs with suspicion when the
referencing file has no matching import (`rq` output shows the file; check
its imports). Fix belongs in repoindex's resolve pass (per rq ADR-002).
