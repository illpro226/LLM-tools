# codediff enumerates every new test as an API change

**RESOLVED 2026-07-27 (codediff v0.2.0, ADR-006).** Files matching the test
conventions now bypass symbol-level classification and emit one counted line
in a new **Tests** section (`+29 tests, +1 helper`). Test symbols can no
longer reach API/Behavior, so they also stop inflating the public-API and
behavior-delta risk flags — a better-tested change no longer reads as a
riskier one. Four regression tests pin it.

**STATUS at filing: open.**

**Date:** 2026-07-27
**Tool:** `codediff` 0.1.1
**Status:** Open

## What I tried

Ran `codediff` (working tree vs HEAD) before committing a change to
`G:\DataExtremes\Code\TOCH_SS` that merged two modules into a package, patched
two subcommands into an existing CLI, and added one new test file.

Under **API changes**, the first ~30 entries were every new test function,
one line each:

```
+ test_graph_key_to_files() (func)                              tests/test_v2_graph_manifest.py:27
+ test_graph_file_to_keys_skips_files_without_placeholders()     tests/test_v2_graph_manifest.py:34
+ test_graph_to_dict_switches_direction() (func)                 tests/test_v2_graph_manifest.py:40
... (27 more)
+ cmd_graph() (func)                                             toch/cli.py:233
```

`cmd_graph()` — the one genuinely new piece of public surface in the whole
change — was the last line of the section, below 30 lines of test names.
Under **Behavior changes**, the test file's private helpers (`_manifest`,
`_StubResolver`, `_StubResolver.__init__`) were listed too.

## Expected

Test functions are not API. A semantic summary should collapse them:

```
+ 29 tests in tests/test_v2_graph_manifest.py (graph, manifest, CLI flags)
```

More generally, files matching test conventions (`tests/**`, `test_*.py`,
`*_test.go`, `*.spec.ts`) deserve their own section — "Tests: +29 / -0 across
1 file" — rather than being folded into the API surface of the change.
A `+ test_*` symbol should probably never count toward risk flags either.

## Impact / workaround

The tool's stated job is a semantic summary to read *before* committing or
reviewing, so signal ordering is the whole product. Here the summary buried
the single most important fact (one new public CLI command) under noise, and
the noise scaled with test count — the better-tested the change, the worse
the summary. That's backwards, and it discourages exactly the behavior the
suite otherwise promotes.

Worth noting the section is accurate by a literal reading: these *are* newly
added top-level functions. The issue is that "API change" should mean
"surface a caller could depend on", and nothing depends on a test name.

Workaround: read past the test block to the tail of the API section, or run
`codediff` on a pathspec excluding `tests/` — though I didn't find a flag for
that, so it means staging selectively.
