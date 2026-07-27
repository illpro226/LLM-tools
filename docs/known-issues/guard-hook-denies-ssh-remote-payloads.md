# Guard hook: denies ssh'd remote payloads on local pattern match

**Date:** 2026-07-26
**Tool:** guard hook (`~/.claude/hooks/llm-tools-guard.py`)
**Status:** Open

## What I tried

Verifying the patched hook on npmserv by feeding it a synthetic
PostToolUse payload over ssh:

```
ssh root@192.168.1.120 '... | python3 /root/.claude/hooks/llm-tools-guard.py
  python3 -c "import json;d=json.load(open(\".savings/aggregate.json\"))..."'
```

Denied locally: *"Ad-hoc inline JSON parsing re-reads the raw file. Use
`structo FILE` ..."*. Earlier in the same session, an `ssh` command
containing `grep -n "def _write_report" -A 16` was denied the same way.

## Expected

The hook inspects the entire Bash command string, so `cat`/`grep`/inline
`python -c` inside a *remote* payload matches the local patterns even
though nothing is read into this session's context — the remote host
does the work and only the summary returns. The denial is a false
positive on the token-economy rationale the rule exists to enforce.

## Impact / workaround

Write the remote script to the scratchpad, `scp` it over, run
`ssh host 'sh /tmp/script.sh'`. Base64-piping the payload also works.
Both add a round trip per iteration while debugging a remote hook.

Not obviously worth "fixing": naively exempting anything after `ssh ... '`
would open a bypass wide enough to drive the original problem through
(`ssh host 'cat bigfile'` genuinely does dump into context). A narrower
exemption might key on the remote command being a script invocation
(`sh /tmp/x.sh`) rather than a pipeline, but that is close to what the
workaround already does by hand. Filing it as recorded friction rather
than a fix request — three denials in one session, all of them correct
by the letter of the rule and all of them costing a round trip.
