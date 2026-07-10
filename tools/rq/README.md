# rq

`rq` ("repo query") answers relationship questions about a codebase from the
shared `.repoindex/index.db` — it never parses source itself. Every claim
line carries a `path:line` reference; confidence is two-valued
(`resolved` | `heuristic`). See [`START.md`](/opt/des_stack/LLM-tools/START.md)
and [`PRD.md`](PRD.md).

```
rq whouses SYMBOL          # inbound refs, grouped per matched symbol
rq implements INTERFACE    # implementations, subclasses nested beneath
rq inherits BASE           # subclass tree
rq impact SYMBOL [--depth N]   # blast radius + covering tests (default 3)
rq publicapi [PATH]        # exported symbols, optionally under PATH
rq deadcode [--include-exported]   # symbols with zero inbound refs
rq findcycles              # import cycles between files, smallest first
rq untested                # exported symbols with no covering test
```

Shared flags: `--root DIR` (repo root), `--json`, `--max-tokens N`
(leaf lists collapse to `(+N more)` counts), `--no-update` (skip the
automatic `repoindex update`), `--repoindex CMD` (freshness-guard binary;
also `RQ_REPOINDEX`; defaults to PATH, then the sibling
`tools/repoindex/repoindex.py`). They are accepted both before and after
the subcommand (`rq --no-update whouses X` == `rq whouses X --no-update`);
if given in both positions, the post-subcommand value wins.

SYMBOL accepts a full qualname (`py/shapes.py::Rectangle`), a local name
(`Rectangle`), or a member name (`area`); matching is case-sensitive.
Exit codes: 0 success, 1 symbol not found, 2 no index and `repoindex`
unavailable.
