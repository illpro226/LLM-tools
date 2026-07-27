# codediff

Semantic summary of a git diff: what a change *means*, not its hunks.
Changed files are parsed on both sides with `repoindex`'s pure extraction
library and diffed at the symbol level, classified into **API changes**
(signatures as `old → new`, renames detected), **Behavior changes**
(changed literals/defaults `3 → 5`, conditional and call deltas),
**Removed** (noting deprecation markers), **Tests** (one counted line per
changed test file), and **Mechanical**
(formatting/comment-only, import reshuffles — one line per file), plus a
flat list of explainable **risk flags** (never a graded score — see
DECISIONS.md ADR-003 and `docs/decisions/0002`).

```
codediff                  # working tree vs HEAD
codediff --staged         # index vs HEAD
codediff REF              # working tree vs REF
codediff A..B             # B vs A   (A...B: B vs merge-base)
codediff --json           # structured output for tooling
codediff --max-tokens N   # cap output; mechanical collapses first
```

Risk keywords and the behavior-delta threshold are configurable in
`.codediff.toml` at the repo root:

```toml
[risk]
keywords = ["auth", "billing"]
large_delta = 8
```

Test-coverage flags (changed source whose covering tests didn't change)
query the shared `.repoindex/index.db` when present; without an index the
tool still runs and says what's missing. Deterministic and offline; exit
codes: 0 ok, 2 usage/git error. Requires `git` and the `repoindex`
package importable (sibling checkout works uninstalled).
