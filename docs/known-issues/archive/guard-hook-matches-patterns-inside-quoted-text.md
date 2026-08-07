# guard hook: matches command patterns inside quoted strings and heredoc bodies

**FIXED 2026-08-06 (guard hook `~/.claude/hooks/llm-tools-guard.py`)** —
`mask_literals()` blanks quoted spans and heredoc bodies to `x` (same
length, so match offsets still index the real string), and `check_shell`
now matches every rule against the masked copy. That closes both
directions at once, and makes the carve-out tests ask "does *this command*
redirect?" rather than "does a `>` appear in these bytes?".

Masking is skipped entirely when the call contains a command that
*executes* its quoted argument — `ssh`, `wsl`, `docker/podman/kubectl
exec`, `bash|sh|zsh|dash|pwsh|powershell -c`, `python|node|perl|ruby -c/-e`,
`cmd /c`. There the quoted text really is a command line, so masking it
would open a new bypass; those calls keep their pre-fix behaviour, which
is what [`archive/guard-hook-denies-ssh-remote-payloads.md`](guard-hook-denies-ssh-remote-payloads.md)
settled as WONTFIX. An *unterminated* quote is also left unmasked, so a
stray apostrophe can't silently disarm every rule after it — masking can
only ever fail closed.

Verified two ways: 32 behavioural cases (both repros, both bypasses, every
existing carve-out), and a 52-case old-vs-new differential over the
pre-fix backup asserting that the only DENY→ALLOW flips are the quoted-prose
false positives. Zero unintended loosening. The savings path benefits too
— it locates the suite-tool invocation in the masked string, so `sgrep
"a;b" path` no longer has its arguments truncated at the quoted `;`.

Residual, by design: prose containing an exec-form invocation (a commit
message mentioning `python -c` beside `json.loads`) still trips a rule.
That's the fail-closed half, and narrowing it further would cost the
guarantee above.

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
[`guard-hook-denies-redirected-searches.md`](guard-hook-denies-redirected-searches.md).

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
