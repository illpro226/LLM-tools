# LLM-tools

LLM-tools is a toolkit of small, composable CLI utilities designed to reduce token waste during coding tasks. The repository is currently a specification and scaffold workspace: the main source of truth is [`START.md`](/opt/des_stack/LLM-tools/START.md), which describes each planned tool and the shared conventions.

## What Belongs Here

- `tools/<name>/`: one standalone CLI tool per directory
- `.repoindex/`: shared SQLite index for relationship-aware tooling
- `tests/` or tool-local `tests/`: fixture-based tests
- Generated caches, build outputs, and indexes should stay untracked

Suite-wide rules that every tool must hold are in [`INVARIANTS.md`](/opt/des_stack/LLM-tools/INVARIANTS.md); cross-tool scope and architecture decisions are recorded in [`docs/decisions/`](/opt/des_stack/LLM-tools/docs/decisions/).

## Shared Conventions

- Prefer Python or Go for new tools
- Keep output plain text, deterministic, and stable in ordering
- Support `--max-tokens N` or `--max-bytes` where applicable
- Use concise, lowercase tool names such as `xread`, `tokq`, and `gitbrief`
- Keep dependencies minimal and startup fast

## Working Locally

There is no single project-wide build script yet. Add commands per tool and document them close to the implementation. Typical examples:

- `python -m pytest`
- `go test ./...`
- `python -m tools.<name>`
- `./tools/<name>/<cli>`

## Contributor Notes

If you are adding or changing a tool, keep the interface citable and agent-friendly:

- Prefer compact, structured text output over verbose logs
- Preserve stable ordering for repeated runs
- Add tests for token limits, fallback behavior, and edge cases
- Do not commit machine-specific paths or generated indexes

See [`AGENTS.md`](/opt/des_stack/LLM-tools/AGENTS.md) for contributor guidance and review expectations.

## Tool Docs

Each `tools/<name>/` directory now contains a standard documentation set:
`README.md`, `PRD.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `STATUS.md`,
`ROADMAP.md`, `CHANGELOG.md`, `DECISIONS.md`, `TESTING.md`, and
`CONTRIBUTING.md`.
