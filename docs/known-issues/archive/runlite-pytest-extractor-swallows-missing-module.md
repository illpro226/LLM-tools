# runlite: pytest extractor reports "no problems", no log tail, when pytest itself is missing

**RESOLVED 2026-07-19 (runlite v0.1.2).** Both recommended fixes shipped:
a failing run whose extractor parses nothing falls back to `parse_generic`
so the log tail always appears, and the header now reads "no findings
(see log tail)" instead of "no problems" on nonzero exits. Regression
tests `test_failing_exit_never_reads_as_pass` and
`test_empty_extract_on_failure_falls_back_to_tail` cover both.

Original report follows.

**STATUS at filing: open.**

- **What broke:** on hosewater (192.168.1.200, Python 3.13.5, pytest not
  installed), `runlite -- python3 -m pytest -q` produced exactly one line:

  ```
  # runlite: exit 1 in 0.02s (pytest) no problems
  ```

  The child's only output — `/usr/bin/python3: No module named pytest` on
  stderr — was swallowed entirely: no failure section, no log tail. The
  exit code passed through correctly (1), but the report gave an agent
  nothing to act on and "no problems" actively contradicts the failure.
  Eleven consecutive test-suite runs (one per tool dir) all produced this
  same blind line before a manual `python3 -m pytest --version` found the
  real cause.
- **Contrast with the generic extractor:** locally (Windows,
  `python runlite.py -- python -m pytest_not_installed_xyz -q`), the
  generic extractor also says "no problems" but at least prints a
  `log tail (last 1 lines)` containing the `No module named ...` line.
  The pytest extractor — selected by command name before the child ever
  ran — prints no tail at all when the log contains no pytest-format
  content.
- **Why it matters:** the failure mode is exactly the environment runlite
  is most likely to meet on a fresh deployment (tool runner present,
  test framework absent). A wrapper whose job is failure-focused
  reporting should never emit less than the raw command did.
- **Recommended fix (two parts):**
  1. Any extractor that finds nothing to report on a nonzero exit must
     fall back to the generic log tail rather than staying silent.
  2. Reword "no problems" on nonzero exits (e.g. "no findings — see log
     tail") so the summary line can't contradict the exit code.
