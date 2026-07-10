# tokq Decisions

ADR log. Entries are Proposed until implementation confirms them.

## ADR-001: Optional tiktoken with a labeled heuristic fallback — Proposed

Context: real tokenization is best, but tokq must run anywhere instantly and
gate scripts without a heavyweight install.
Decision: lazy-import tiktoken (o200k-class encoding) inside the call path;
fall back to bytes/3.7; every report states which method was used, once.
Consequences: estimates are honest about their provenance; the two paths are
both first-class and both tested.

## ADR-002: Sub-100ms fallback startup as a hard budget — Proposed

Context: tokq is meant to be reflexively cheap — anything slow gets skipped by
agents and pre-commit hooks alike.
Decision: the fallback path imports effectively nothing beyond argparse/os;
startup time is an asserted test, not an aspiration.
Consequences: import discipline constrains implementation style; heavy
features must live behind lazy imports.

## ADR-003: Lint rules are data — Proposed

Context: waste patterns (lockfiles, minified, generated) grow over time.
Decision: rules are table rows: pattern/heuristic + threshold + cheaper-tool
suggestion; the engine is generic.
Consequences: adding a rule is a one-line change with a fixture; suggestions
stay consistent with the suite's tool map.

## ADR-004: Nonzero exit as the gating contract — Proposed

Context: the suite wants tokq to gate scripts and hooks.
Decision: `lint --budget N` exits nonzero on any violation; thresholds and
exit semantics are part of the stable interface.
Consequences: CI/hook integration is trivial; changing exit behavior later is
a breaking change and must be treated as such.
