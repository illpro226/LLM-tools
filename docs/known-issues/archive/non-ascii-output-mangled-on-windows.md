# sgrep/repomap/gitbrief mangle non-ASCII output on Windows

**RESOLVED 2026-07-27.** Diagnosis in the report was right: the inputs were
already read as UTF-8 and only stdout was unpinned —
`sys.stdout.reconfigure(errors="replace")` left `encoding` at the platform
default. Every tool in the suite now pins `encoding="utf-8"` at entry
(sgrep 0.1.1, repomap 0.2.0, gitbrief 0.1.1, xread 0.2.1, structo 0.3.1,
runlite 0.1.3, tokq 0.1.1, codediff 0.2.0, and rq/testmap/repoindex, which
had no reconfigure call at all). Recorded as a suite-wide rule in
INVARIANTS.md, since the failure mode is a silent write corruption rather
than a bad read. Regression tests in sgrep and repomap run the CLI as a
subprocess with `PYTHONIOENCODING=cp1252` and assert the UTF-8 bytes
survive; both fail against the old code.

**STATUS at filing: open.**

**Date:** 2026-07-27
**Tool:** `sgrep` 0.1.0, `repomap` 0.1.0, `gitbrief` (same symptom)
**Status:** Open

## What I tried

Working in `G:\DataExtremes\Code\TOCH_SS`, whose docs use em-dashes throughout
and whose subject matter includes `file→keys` arrows. Every tool that echoes
file content back rendered those characters as `�` or `?`:

```
sgrep:   docs/STATUS.md:68: - `docs/MEMDUMP_TOCH_v2_architecture.md` � architecture document ...
repomap: repomap . � 18 source files / 38 files
repomap: toch/cli.py:165 def scan_path(path: Path) -> dict[str, list] � Return {file_path: ...}
gitbrief: | `tests/` | Test suite � 69 tests, all passing. |
```

Isolated it with a minimal probe file containing one em-dash and one arrow:

1. **File on disk is valid UTF-8** — bytes are `e2 80 94` (em-dash) and
   `e2 86 92` (arrow).
2. **The Bash pipe carries UTF-8 fine** — `python -c "import sys;
   sys.stdout.reconfigure(encoding='utf-8'); print('A em-dash — here')"`
   through the same pipe renders clean.
3. **`sgrep` on that same file mangles it** — em-dash → `�`, arrow → `?`.

So it is not the source file and not the terminal capture layer. It is the
tools' stdout encoding on Windows falling back to cp1252 instead of UTF-8.

The two different corruptions are a hint at the mechanism: `�` is U+FFFD
(a *decode* failure) while `?` is the classic cp1252 *encode*-with-replace
output. Getting both in one line suggests a decode/encode round trip where
neither end is pinned to UTF-8.

## Expected

Byte-faithful passthrough of file content on Windows, matching what `rg`
itself emits. `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`
at entry (and explicit `encoding="utf-8"` on any subprocess capture of `rg`)
should cover it.

## Impact / workaround

Worse than cosmetic. These tools are the *recommended* substitute for reading
files, so their output is what gets reasoned over and, occasionally, copied
into an `Edit`. Pasting a mangled line back into a file would silently corrupt
it — the failure mode is a write, not just a bad read. In this session I read
mangled doc text for an entire session before noticing.

It also degrades the tools' own legibility: `repomap`'s docstring summaries
are separated from the symbol by an em-dash, so every summary line in a
`repomap` dump contains a `�`.

Workaround: none in-tool. Fall back to a bounded `Read` when the exact
characters matter (which is exactly the case the guard hook steers away from).
No workaround is needed for pure ASCII sources, which is probably why this has
gone unnoticed.
