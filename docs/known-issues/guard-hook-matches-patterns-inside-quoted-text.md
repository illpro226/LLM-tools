# guard hook: matches command patterns inside quoted strings and heredoc bodies

**Date:** 2026-08-06
**Tool:** LLM-tools guard hook (all shell rules)
**Severity:** contains a live bypass introduced the same day — see
*Regression* below. The false-deny half is cosmetic; the false-allow half
is not.

## What happens

Every shell rule is a regex over the raw command string. The matcher has no
idea which bytes are a command and which are quoted text, so it is wrong in
both directions.

### Direction 1 — prose trips a rule (annoying, fails closed)

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

The anchor is what makes this specific: a token mid-line is safe
(`git commit -m "rg is fine"` → ALLOW, verified), because `"` is not a
command separator. It takes a **line start** inside the quoted text — which
is exactly what a multi-line commit message or heredoc produces.

### Direction 2 — quoted text suppresses a rule (a real bypass)

The same blindness lets a genuine dump through, because the carve-out tests
(`STDOUT_REDIRECT_RE`, `BOUNDED_PIPE_RE`) also read the raw string:

```
ALLOW  rg -n "a>b" src        <-- WRONG: the `>` is inside the pattern
ALLOW  rg -n "x | head" src   <-- WRONG: the `| head` is inside the pattern
```

Both dump unbudgeted matches straight to context. Verified in-process
against the live hook; `rg -n "needle" src` still denies, so the rule is
intact and it is specifically the quoted span that defeats it.

## Regression

**Direction 2 did not exist before 2026-08-06.** Replayed against the
pre-change backup (`llm-tools-guard.py.bak-20260806`), both commands DENY.
They were opened by the redirect/bounding carve-out added for
[`archive/guard-hook-denies-redirected-searches.md`](archive/guard-hook-denies-redirected-searches.md).

That is worth stating plainly rather than filing as a neutral finding: the
carve-out was correct in intent and is well-scoped across *commands*
(`_own_pipeline` stops at `;`/newline/`&&`/`||`), but it introduced a test
that a search's own argument text can satisfy. Before it, quote-blindness
could only cause false denies — irritating, but the hook failed closed.
Now it can cause false allows, and because the hook fails open by design, a
bypass produces **zero signal**: the dump simply happens.

## When it happens

- Direction 1: any shell call carrying multi-line quoted text whose lines
  start with rule vocabulary. Commit messages are the common case, and this
  repo's subject vocabulary is `sgrep`, `grep`, `cat`, `diff`, `log`. Cost
  two commits in one session, each needing the message moved to a file.
- Direction 2: any search whose *pattern* contains `>` or `| head`/`tail`/
  `wc`. Reachable by accident — `rg "a->b"` and `rg "foo|head"` are ordinary
  searches — not only by deliberate evasion.

## Expected

Tokenize quote-aware before matching, so rules are tested against actual
command words rather than the raw string. The hook already has this:
`_shell_tokens()` uses `shlex.split` and stops at the first unquoted shell
operator, and its docstring gives the identical rationale ("a bare regex
split on `|` would cut a quoted alternation pattern in half"). It is only
wired into the savings path. The deny path should use the same primitive.

Heredoc bodies (`<<'EOF' … EOF`) must be stripped before matching too;
`shlex` will not do that on its own.

Two useful properties of that fix: it closes both directions at once, and
it makes the carve-out tests ask the right question — "does *this command*
redirect?" instead of "does a `>` appear anywhere in these bytes?"

## Mitigation available now

If the full tokenizer rewrite is too large to take on immediately, the
bypass alone can be closed by blanking quoted spans before running the
carve-out tests only — leaving the deny regexes untouched, so no rule gets
weaker and Direction 1 is unaffected. That is a narrow, low-risk change and
should probably land ahead of the broader fix, since it is the half that
fails open.

## Workaround

- Direction 1: `git commit -F FILE` with the message in a file. Used twice.
- Direction 2: none — it is silent. Until fixed, do not assume an allowed
  `rg` was budget-checked if its pattern contains `>` or a pipe word.
