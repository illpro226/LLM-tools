# `xread --symbol` can't find module-level constants, so the cheapest lookup for "what is this value" falls back to sgrep

**RESOLVED 2026-09-11 (xread v0.4.2).** `parse_python` now collects module-level
`Assign`/`AnnAssign` targets as `constant` symbols, spans covering a multi-line
right-hand side plus an attached comment above. Tuple unpacking binds each
name; locals, class attributes and attribute targets stay excluded. Constants
also appear in `--headings`, which is how the name becomes discoverable in the
first place. Seven tests added on a new `constants.py` fixture.

- **What broke:** during the 2026-09-11 session, `xread
  ~/.claude/hooks/llm-tools-guard.py --symbol _EXEC_QUOTED_RE` returned
  `xread: symbol not found: _EXEC_QUOTED_RE`. The name is a module-level
  regex constant spanning six lines. The fallback was `sgrep` to find the
  line number, then `xread --lines 486-505` guessing a span wide enough to
  catch the whole assignment — two calls and a guess to replace one exact
  lookup.
- **When it happens:** any module-level binding. In this repo that is most
  of the interesting configuration surface: the guard hook's rule regexes
  (`_EXEC_QUOTED_RE`, `SUITE_TOOL_RE`, `BOUNDED_PIPE_RE`, `LOG_COUNT_RE`),
  and every tool's tunables (`DEFAULT_MAX_TOKENS`, `WINDOW`, `PY_EXTS`).
  These are exactly the names an agent arrives with — read off a traceback,
  a grep hit, or another file's reference — and wants the definition of.
- **Why it happened:** `parse_python` walks the AST for `FunctionDef`,
  `AsyncFunctionDef` and `ClassDef` only. An `Assign`/`AnnAssign` at module
  level is never collected, so it is invisible to both `--symbol` and
  `--headings`. The JS/TS scanner does better here by accident — its
  `const NAME = ...` declaration patterns pick up exported constants — so
  the gap is Python-specific and inconsistent across the two parsers.
- **Why `--headings` doesn't cover it:** `--headings` lists what the parser
  found, so a file whose constants are missing from the outline gives no
  hint that `--symbol` would fail on them. The agent learns the name is
  absent only by asking for it.
- **Recommended fix:** collect module-level `Assign`/`AnnAssign` targets as
  symbols of a new kind (`constant`), with the span covering the full
  assignment including a multi-line right-hand side and any attached
  comments, the same way functions already extend upward. Keep them
  top-level only — assignments inside a function body are locals, not
  API, and collecting them would bury the outline in noise. Class-level
  assignments are a judgement call; excluded here for the same reason,
  since a class's fields show up inside its own body already.
