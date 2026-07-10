# Repository Documentation

LLM-tools is a specification-first repository for small CLI utilities that help coding agents spend fewer tokens. The canonical source for the tool suite is [`START.md`](/opt/des_stack/LLM-tools/START.md).

## Current Layout

- `tools/<name>/`: one directory per tool
- `docs/`: repository documentation
- `docs/decisions/`: architecture and scope decisions
- `docs/PRDs/`: product requirement drafts and tool briefs
- `docs/known-issues/`: open limitations, bugs, and follow-ups
- Each `tools/<name>/` directory also carries a standard tool-level doc set:
  `README.md`, `PRD.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`, `STATUS.md`,
  `ROADMAP.md`, `CHANGELOG.md`, `DECISIONS.md`, `TESTING.md`, and
  `CONTRIBUTING.md`.

## Working Rules

- Keep CLI output plain text, deterministic, and citable
- Prefer Python or Go for implementations
- Support `--max-tokens N` or `--max-bytes` where output can grow large
- Add fixture-based tests for parsing, ranking, and fallback behavior

## Where To Start

1. Read [`START.md`](/opt/des_stack/LLM-tools/START.md) for the tool list and shared conventions.
2. Read [`AGENTS.md`](/opt/des_stack/LLM-tools/AGENTS.md) for contributor guidance.
3. Create new work under `tools/<name>/` and document tool-specific behavior alongside the code.
