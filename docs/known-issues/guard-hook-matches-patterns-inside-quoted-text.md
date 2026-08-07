# guard hook: matches command patterns inside quoted strings and heredoc bodies

**Date:** 2026-08-06
**Tool:** LLM-tools guard hook (all shell rules)

## What happens

A commit was denied because its *message* had a line beginning with `rg`:

```
git add -A && git commit -q -m "$(cat <<'EOF'
sgrep: normalize path separators at ingest

rg echoes the separator it was given, so a directory search and an
...
EOF
)"
```

`GREP_RE` is `(?:^|[;\n]|&&|\|\|)\s*(?:command\s+)?(?:grep|egrep|fgrep|rg)\b`.
Inside the heredoc, the newline before `rg echoes…` satisfies the
command-position anchor, so prose became a command match. Nothing in the
call ran — including the commit.

## When it happens

Any shell call carrying English text that a rule's vocabulary appears in,
at the start of a line or after `&&`/`;`. Commit messages are the obvious
case and are frequent: this repo's whole subject vocabulary is `sgrep`,
`grep`, `cat`, `diff`, `log`. It cost two commits in one session, each
needing the message rewritten into a scratch file and passed with `-F`.

The same blind spot cuts the other way, which is the more serious half: a
rule can be *evaded* by the same mechanism it is falsely tripped by, since
the matcher has no idea what is quoted.

## Expected

The deny path should tokenize quote-aware before matching, so patterns are
tested against actual command words rather than against the raw string.
The hook already has exactly this — `_shell_tokens()` uses `shlex.split`
and stops at the first unquoted shell operator — but only on the savings
path, where its docstring gives the identical rationale ("a bare regex
split on `|` would cut a quoted alternation pattern in half").

Heredoc bodies (`<<'EOF' … EOF`) should be stripped before matching too;
`shlex` will not do that on its own.

## Related

The redirect carve-out added in
[`archive/guard-hook-denies-redirected-searches.md`](archive/guard-hook-denies-redirected-searches.md)
inherits the same weakness in the other direction: `STDOUT_REDIRECT_RE` is
a regex over the raw string, so a `>` inside a quoted search pattern
(`rg "a>b" src`) would read as a redirect and allow a search that does
reach context. Narrow — it takes a `>` inside the pattern — but it is the
same root cause and should be fixed by the same change.

## Workaround

Write the message to a file and use `git commit -F FILE`. Used twice.
For non-git cases, avoid rule vocabulary at line starts inside quoted text.
