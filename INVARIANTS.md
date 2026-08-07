# Suite Invariants

Rules that hold across every tool. A change that breaks one of these needs a
decision record in `docs/decisions/`, not just a PR.

## Output

- Plain text, deterministic, stable ordering. No ANSI, no spinners, no
  timestamps in normal output.
- Every line that makes a claim about code carries a `path:line` reference,
  so any finding can be followed up with `xread`. Lines that make no claim
  — `sgrep`'s `-C` context lines, which exist only to situate the match
  above them inside a block whose header already names the file — carry a
  bare line number instead. Repeating the path there is not rigor, it is
  the overhead that made narrow `sgrep -C` searches print more than the
  raw dump they replaced.
- Every tool whose output can grow respects `--max-tokens N`, degrading by
  summarizing harder — never by truncating mid-thought.
- **The budget is on by default, and every rung is bounded**
  (docs/decisions/0005). A tool whose purpose is keeping bulk out of a
  context window must not emit bulk unless asked twice: opt-in caps were
  passed on 1.4% of real calls. A ladder must also actually *terminate* in
  something small — a rung that is still O(input), like one line per
  top-level key, means the budget is ignored rather than merely loose.
  `--max-tokens 0` is the documented escape hatch. Modes whose output feeds
  another program (`structo --select`/`--raw`, `--json` payloads) are
  exempt from the default, never from an explicit cap.
- **Degradation is announced.** When a budget removes something the caller
  asked for, the output says so and names `--max-tokens`. Silently serving
  less than was requested is worse than serving nothing: dropped context
  reads as *absent* context, and the caller never thinks to raise the cap.
- **stdout and stderr are UTF-8, pinned at entry** —
  `reconfigure(encoding="utf-8", errors="replace")` on both, never the
  platform default. These tools are the recommended substitute for reading
  files, so their output gets reasoned over and sometimes copied back into
  an edit; a character mangled by a cp1252 console is a silent write
  corruption, not just a bad read. stderr counts: error messages carry the
  same non-ASCII punctuation as normal output and are read by the same
  agent, and pinning must happen before the first error can be printed —
  pinning stdout late, after the error path, protects nothing. Subprocess
  captures of other tools' output pin `encoding="utf-8"` for the same
  reason.

## Semantics

- **Offline and deterministic by default.** Any LLM call is opt-in behind an
  explicit flag and never receives raw source or raw diffs — only the
  compact structured summary the tool already produced.
- **Parse once, query everywhere.** Relationship questions (callers, users,
  impact, coverage) go through `.repoindex/index.db`; relationship tools
  (`rq`, `testmap` lookups, `codediff` if built) never re-parse source.
  Excerpt and orientation tools (`xread`, `sgrep`, `repomap`) may parse
  directly — they must keep working when no index exists.
- **Uncertainty is stored, not hidden — and not inflated.** Confidence is
  two-valued: `resolved` | `heuristic` (tools/repoindex/DECISIONS.md
  ADR-003). Do not introduce ordinal scales (HIGH/MEDIUM/LOW); static
  analysis cannot honestly distinguish them.

## Performance

- Startup under ~100 ms on the no-heavy-deps path; a tool agents hesitate to
  invoke saves nothing.
- `repoindex update` cost scales with change size, not repo size — cheap
  enough that query tools run it implicitly.
- Stream large inputs; never load a file fully into memory when a streaming
  pass suffices.

## Documentation

- Docs obey the suite's own philosophy: every file an agent must load costs
  tokens. Extend an existing doc before creating a new one; keep suite-level
  docs to START.md, AGENTS.md, this file, and `docs/`.
