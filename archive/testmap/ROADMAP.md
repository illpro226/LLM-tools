# testmap Roadmap

M1–M4 (scaffold, convention/import layers, pytest coverage recording,
hardening) shipped in v0.1.0 — see CHANGELOG.md and DECISIONS.md.

## Next

- `record` for go (`go test -coverprofile`, package-level rows) and js
  (c8/vitest coverage), per ADR-007's deferral.
- Test-node granularity: emit `file::test_name` targets where the index
  or coverage contexts can support it (PRD mentions node lists; v0.1 is
  file-level).
- Watch mode (map on save) if agents want it.
