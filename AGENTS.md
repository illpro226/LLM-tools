# Repository Guidelines

## Project Structure & Module Organization
This repository is currently a design/specification workspace. The root `START.md` describes the tool suite and the expected layout for future work.

- `tools/<name>/`: one standalone CLI tool per directory
- `.repoindex/`: shared SQLite index used by relationship-based tools
- `tests/` or tool-local `tests/`: fixture-driven tests for each command
- Generated or cached artifacts should stay out of version control

## Build, Test, and Development Commands
There is no committed build system yet, so commands should be added per tool. Prefer small, explicit entry points such as:

- `python -m pytest`: run Python tests for a tool
- `go test ./...`: run Go tests when a tool is implemented in Go
- `python -m tools.<name>` or `./tools/<name>/<cli>`: run the CLI locally

Document any new tool-specific commands in that tool’s README or usage notes.

## Coding Style & Naming Conventions
Follow the conventions in `START.md`:

- Prefer Python or Go for new tools
- Keep output plain text, deterministic, and stable in ordering
- Support `--max-tokens N` or `--max-bytes` where applicable
- Use lowercase, descriptive tool names like `xread`, `tokq`, and `gitbrief`
- Keep dependencies minimal and startup fast

Use the formatter and linter that match the implementation language (`ruff`/`black` for Python, `gofmt` for Go).

## Testing Guidelines
Use fixture-based tests that exercise real command output. Prefer small, reproducible inputs over large fixtures.

- Name tests after behavior, not implementation details
- Cover cap/trim behavior for token-limited output
- Verify deterministic ordering and stable formatting
- Add regression tests for parsing, ranking, and fallback paths

## Commit & Pull Request Guidelines
No git history is available in this checkout, so there is no repository-specific commit convention to mirror. Use short, imperative commit subjects, for example: `add xread token cap tests`.

Pull requests should include:

- A brief summary of the tool or change
- Commands run for verification
- Notes on any new CLI flags, file locations, or generated artifacts
- Screenshots only if a UI is added later

## Security & Configuration Tips
Do not commit local caches, indexes, or machine-specific paths. If a tool writes `.repoindex/index.db` or similar generated state, keep it ignored and rebuildable.
