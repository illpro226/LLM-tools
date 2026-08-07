Potential additions to LLM-tools

===============================



1\. configo (Configuration summarizer)

\-------------------------------------

Problem:

&#x20;   Agents repeatedly read large configuration files to answer simple

&#x20;   questions.



Replaces:

&#x20;   cat package.json

&#x20;   cat pyproject.toml

&#x20;   cat docker-compose.yml

&#x20;   cat tsconfig.json

&#x20;   cat vite.config.ts

&#x20;   cat nginx.conf

&#x20;   ...



Output:

&#x20;   - Frameworks

&#x20;   - Build system

&#x20;   - Test runner

&#x20;   - Entry points

&#x20;   - Aliases

&#x20;   - Important enabled/disabled options

&#x20;   - Relevant paths



Justification:

&#x20;   Configuration files are usually high-noise.

&#x20;   Most keys are irrelevant to the task.

&#x20;   One concise summary could replace hundreds or thousands of tokens.



ROI:

&#x20;   HIGH





2\. buildmap

\-----------

Problem:

&#x20;   Agents waste commands figuring out how a project is built.



Replaces:

&#x20;   ls

&#x20;   cat Makefile

&#x20;   cat package.json

&#x20;   cat pyproject.toml

&#x20;   cat Cargo.toml

&#x20;   README searching



Output:

&#x20;   Build commands

&#x20;   Test commands

&#x20;   Lint commands

&#x20;   Formatting commands

&#x20;   Generated artifacts

&#x20;   Required tools



Justification:

&#x20;   This information is repeatedly rediscovered during sessions.



ROI:

&#x20;   HIGH





3\. depbrief

\-----------

Problem:

&#x20;   Dependency manifests contain enormous amounts of version noise.



Replaces:

&#x20;   Reading package.json

&#x20;   requirements.txt

&#x20;   Cargo.toml

&#x20;   go.mod



Output:

&#x20;   Runtime frameworks

&#x20;   Test frameworks

&#x20;   AI libraries

&#x20;   Databases

&#x20;   Logging

&#x20;   HTTP

&#x20;   Build tooling



Justification:

&#x20;   LLMs almost never care that requests==2.32.1.

&#x20;   They care that Requests is used.



ROI:

&#x20;   HIGH





4\. docbrief

\-----------

Problem:

&#x20;   READMEs often contain thousands of tokens.



Output:

&#x20;   Purpose

&#x20;   Install

&#x20;   Quick start

&#x20;   CLI

&#x20;   Architecture

&#x20;   Limitations

&#x20;   Related docs



Justification:

&#x20;   Documentation is often consumed for navigation rather than details.



ROI:

&#x20;   MEDIUM-HIGH





5\. envbrief

\-----------

Problem:

&#x20;   Environment inspection requires multiple commands.



Replaces:

&#x20;   pwd

&#x20;   which python

&#x20;   python --version

&#x20;   node --version

&#x20;   git status

&#x20;   git branch

&#x20;   ls



Output:

&#x20;   Current repo

&#x20;   Branch

&#x20;   Dirty state

&#x20;   Language

&#x20;   Package manager

&#x20;   Virtual environment

&#x20;   Current directory



Justification:

&#x20;   Eliminates orientation noise.



ROI:

&#x20;   MEDIUM





6\. decisionmap

\--------------

Problem:

&#x20;   Long conversations contain design decisions buried in discussion.



Output:

&#x20;   Confirmed decisions

&#x20;   Assumptions

&#x20;   Open questions

&#x20;   Rejected approaches



Justification:

&#x20;   Greatly reduces conversation rereads.



ROI:

&#x20;   HIGH



Notes:

&#x20;   Probably outside current repository-focused scope.





7\. stacktrace

\-------------

Problem:

&#x20;   Stack traces contain repeated frames and library noise.



Replaces:

&#x20;   Raw Python traceback

&#x20;   Java exception

&#x20;   Node stack

&#x20;   Rust panic

&#x20;   Go panic



Output:

&#x20;   Root exception

&#x20;   First project frame

&#x20;   Relevant frames only

&#x20;   Probable cause



Justification:

&#x20;   Most stack traces are 80% framework noise.



ROI:

&#x20;   HIGH





8\. apiwalk

\----------

Problem:

&#x20;   Agents read many source files just to understand an API surface.



Output:

&#x20;   Public classes

&#x20;   Public functions

&#x20;   Parameters

&#x20;   Return types

&#x20;   Short descriptions

&#x20;   Source locations



Justification:

&#x20;   Faster than xread when exploring an unfamiliar library.



ROI:

&#x20;   MEDIUM



Notes:

&#x20;   Could overlap too much with repoindex + xread.





9\. promptlint

\-------------

Problem:

&#x20;   Prompt files accumulate duplication, contradictions, and token waste.



Output:

&#x20;   Duplicate instructions

&#x20;   Contradictions

&#x20;   Repeated constraints

&#x20;   Estimated token cost

&#x20;   Simplification suggestions



Justification:

&#x20;   Directly aligns with signal-to-noise philosophy.



ROI:

&#x20;   HIGH





\------------------------------------

Ideas I would NOT build

\------------------------------------



❌ Better ls

❌ Better cat

❌ Better grep implementation

❌ General-purpose shell wrapper

❌ AI-generated summaries

❌ Natural-language code explanation tool

❌ Agent framework

❌ Tool orchestration engine



Reason:

Each either duplicates existing UNIX tools, introduces nondeterminism,

or increases maintenance cost without enough measurable token savings.

---

# Verdict (2026-08-07) — reviewed, not built

Origin: this list was generated by ChatGPT without access to the repo's
usage history. It ranks ideas by savings-per-call. The binding constraint
here is trigger frequency: `rq` and `testmap` were retired (0006) and
archived (0009) after a month produced 2 calls and 0 calls, despite both
working as specified. The ROI labels above are self-assigned with no usage
data behind them — the exact trap 0006 documented.

The build list is closed at 11 tools (0003). Anything below would need a
new decision record superseding it.

| # | idea | verdict | why |
|---|---|---|---|
| 7 | stacktrace | **keep, as `runlite trace`** | Only genuinely new capability. `runlite` helps only when you wrapped the command; traces also arrive from log files, CI, services, pastes — a distinct trigger. But the extractors already exist (`tools/runlite/runlite.py:149-367`), so it is a stdin/file mode on `runlite`, not a 12th directory. Drop "probable cause": that is inference, which this list's own no-build section rejects. |
| 2 | buildmap | no — docs problem | Build/test/lint commands really are rediscovered every session, but the fix is stating them once in `CLAUDE.md`, which is in context for free. A CLI that re-derives per session what a static file can assert is strictly worse. |
| 1 | configo | no — maintenance sink | "Important enabled/disabled options" is a hand-curated opinion per format, and nginx.conf / tsconfig / vite.config.ts / docker-compose share no parser. `structo` already covers the JSON/YAML ones for shape. Failure mode is `rq`'s: an agent that doesn't trust a lossy config summary reads the file anyway, paying twice. |
| 3 | depbrief | no — mostly already free | `structo package.json --path dependencies` lists them today at zero new code. The delta is category labels ("AI libraries", "logging"), requiring a package→category map that goes stale permanently. |
| 4 | docbrief | no — duplicates shipped behavior | `xread FILE --headings` outlines a README; `--query` pulls the section. |
| 9 | promptlint | no — same charter as `tokq lint` | `tools/tokq/PRD.md:14-24` is already "flag context-wasteful content." Contradiction detection is either shallow string matching (near-worthless) or an LLM call (on this list's own no-build section). If wanted: a near-duplicate-block rule inside `tokq lint`. |
| 5 | envbrief | no — premise off | Those seven commands emit ~200 tokens total. The win is round-trips, not context. A shell function, not a suite tool. |
| 6 | decisionmap | no — self-contradicting | Needs harness-specific transcript parsing (brittle) or LLM summarization (rejected above). `docs/decisions/` is already the durable version, written deliberately rather than mined. |
| 8 | apiwalk | no — its own note is right | Overlaps `xread` + `repomap`; for third-party libraries the real competitor is Context7, not a parser we maintain. |

The "Ideas I would NOT build" section above is sound and consistent with 0003.

Standing rule for revival: log the friction in `docs/known-issues/` each time
one of these is actually wanted mid-task. Three real entries clears the bar —
the same evidence standard used to archive two working tools.



