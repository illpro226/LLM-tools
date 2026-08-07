# PRDs

Use this folder for product requirement drafts for individual tools or shared repo capabilities.

Recommended structure for each PRD:

- problem statement
- target users or agents
- scope
- non-goals
- acceptance criteria

Keep each PRD focused on one tool or one shared workflow.

## Per-tool PRDs

The canonical PRD for each tool lives next to the tool at `tools/<name>/PRD.md`:

- [codediff](../../tools/codediff/PRD.md) — semantic diff summarizer
- [gitbrief](../../tools/gitbrief/PRD.md) — git state summarizer
- [repoindex](../../tools/repoindex/PRD.md) — shared repo-wide symbol database
- [repomap](../../tools/repomap/PRD.md) — repository skeleton generator
- [runlite](../../tools/runlite/PRD.md) — command output distiller
- [sgrep](../../tools/sgrep/PRD.md) — token-budgeted search condenser
- [structo](../../tools/structo/PRD.md) — big-file shape summarizer
- [tokq](../../tools/tokq/PRD.md) — token cost meter and context linter
- [xread](../../tools/xread/PRD.md) — targeted code excerpt reader

`rq` and `testmap` are archived (docs/decisions/0009); their PRDs moved
with them to [archive/rq/PRD.md](../../archive/rq/PRD.md) and
[archive/testmap/PRD.md](../../archive/testmap/PRD.md).
