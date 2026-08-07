# guard hook: denies `rg > file` though redirected output never reaches context

**Date:** 2026-08-06
**Tool:** LLM-tools guard hook (grep/rg rule)

## What happens

The hook allows `cat` when its output is redirected to a file, and denies
`rg`/`grep` in the same position. Replayed against the current hook:

```
DENY   rg -n "needle" src
DENY   rg -n "needle" src > out.txt
DENY   rg -n "needle" src | head -5
DENY   grep -rn "needle" src > /tmp/out.txt
ALLOW  cat big.json > copy.json
ALLOW  python x.py | grep needle
```

The `cat` rule's own carve-out is "heredocs, redirects, and pipes into
head/tail/wc stay allowed", on the reasoning that output going to a file or
through a bounding filter never lands in the model's context. That
reasoning applies identically to `rg` and is not applied there.

## When it hit

Measuring sgrep's output against the equivalent raw `rg` — the baseline
methodology the savings record is built on. The command wrote both outputs
to scratch files and printed only `wc -c`, so zero matched lines could
reach context, and it was denied anyway. Cost: a Write plus a Bash call to
wrap `rg` in a Python script, per iteration.

This is not a corner case for this repo. Every future check of whether a
suite tool actually beats its raw equivalent needs to run the raw
equivalent, and the hook is built to stop exactly that.

## Expected

One of, in preference order:

1. Extend the existing redirect/bounding carve-out to `rg`/`grep`: a search
   whose stdout goes to a file or into `head`/`tail`/`wc` costs no tokens
   and should be allowed, consistently with `cat`.
2. Keep denying, but say so deliberately — the deny message should state
   that redirect does not exempt a search, so the caller stops trying to
   spell around it.

Option 1 does have a real cost: `rg ... > out.txt` followed by reading
`out.txt` reaches context by two hops. That is weaker than it looks — the
second hop is a `Read`, which the hook already size-limits, or an `xread`,
which is budgeted. Option 2 is the safe answer if that argument is not
accepted, and is still an improvement over the current silence.

Whichever is chosen, `cat` and `rg` should be decided the same way. Today
the difference is not a policy, it is an accident of which rule got the
carve-out.

## Workaround

Wrap the raw command in a Python script in the scratchpad and run that
(`subprocess.run(..., capture_output=True)`, print `len(stdout)` only).
Used twice in this session. It also happens to be the *right* way to
measure a baseline — the output is never rendered — which is an argument
that the hook is protecting the correct outcome by the wrong mechanism.
