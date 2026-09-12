#!/usr/bin/env python3
"""Behavioural tests for the LLM-tools guard hook.

The hook (`~/.claude/hooks/llm-tools-guard.py`) lives outside this repo and
has no test suite of its own. Six issues have been filed against it and
fixed, each verified by a throwaway script that was then lost — and the
2026-08-06 redirect carve-out shipped a bypass precisely because nothing
re-ran the earlier cases. This file is that missing memory: every carve-out
and every closed bypass, as an executable assertion.

    python scripts/test-guard-hook.py [--hook PATH] [--baseline PATH]

`--baseline` (a pre-change copy of the hook) additionally runs a
differential: it reports every verdict the change flips, and fails on any
DENY -> ALLOW flip not listed as intended in CORPUS. That direction is the
dangerous one — the hook fails open, so a new bypass produces no signal at
all.

Exit 0 = pass, 1 = failure.
"""
import argparse
import atexit
import importlib.util
import os
import sys
import tempfile

DEFAULT_HOOK = os.path.expanduser("~/.claude/hooks/llm-tools-guard.py")

# The range-read rule asks the filesystem how long a file is, so its cases
# need a real one. 12 lines: short enough that a "small" range still covers
# it, which is the case the flat line cap alone cannot catch.
_fd, FIXTURE = tempfile.mkstemp(prefix="guard-fixture-", suffix=".txt")
with os.fdopen(_fd, "w") as _fh:
    _fh.write("".join(f"line {i}\n" for i in range(1, 13)))
atexit.register(lambda: os.path.exists(FIXTURE) and os.unlink(FIXTURE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import hook at {path} "
                         "(a .bak baseline must be copied to a .py name first)")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Denied(Exception):
    pass


def verdict(mod, command, tool):
    """ALLOW or DENY, without letting the hook call sys.exit.

    Older deployed copies take `check_shell(command)` with no tool
    argument; accept both so this can audit a server's copy as well as the
    working one.
    """
    def fake_deny(reason):
        raise Denied(reason)
    real, mod.deny = mod.deny, fake_deny
    try:
        try:
            mod.check_shell(tool, command)
        except TypeError:
            mod.check_shell(command)
        return "ALLOW"
    except Denied:
        return "DENY"
    finally:
        mod.deny = real


COMMIT_MSG = """git add -A && git commit -q -m "$(cat <<'EOF'
sgrep: normalize path separators at ingest

rg echoes the separator it was given, so a directory search and an
grep and cat and git diff all appear in this prose
EOF
)\""""

BARE_HEREDOC = """cat <<'EOF' > /tmp/x.sh
rg -n foo src
git diff
EOF"""

# (command, tool, expected, label, flip)
#
# `flip` marks a case whose verdict the current hook deliberately changed
# from an older one: "loosen" for a false deny that was fixed, "tighten" for
# a bypass that was closed. The differential run fails on any DENY -> ALLOW
# flip whose entry is not marked "loosen".
CORPUS = [
    # --- quoted text is an argument, not a command (both directions) ------
    (COMMIT_MSG, "Bash", "ALLOW", "commit message with rule vocabulary", "loosen"),
    (BARE_HEREDOC, "Bash", "ALLOW", "heredoc body with rule vocabulary", "loosen"),
    ('git commit -m "line one\ngit diff line two"', "Bash", "ALLOW",
     "multi-line quoted message, no heredoc", "loosen"),
    ('git commit -m "\ncat notes\n"', "Bash", "ALLOW",
     "cat at a line start inside quotes", "loosen"),
    ('git commit -m "\nGet-Content x\n"', "PowerShell", "ALLOW",
     "PS vocabulary at a line start inside quotes", "loosen"),
    ('git commit -m "Select-String is mentioned here"', "PowerShell", "ALLOW",
     "PS vocabulary mid-line", None),
    ('git commit -m "rg is fine"', "Bash", "ALLOW", "token mid-line", None),
    ('git commit -m "gitbrief hunks was the right call"', "Bash", "ALLOW",
     "gitbrief in a message (message masked, so no git diff either)", None),

    ('rg -n "a>b" src', "Bash", "DENY", "redirect char inside the pattern", "tighten"),
    ('rg -n "x | head" src', "Bash", "DENY", "pipe words inside the pattern", "tighten"),
    ("rg -n 'a>b' src", "Bash", "DENY", "single-quoted redirect char", "tighten"),
    ('cat notes.md "with > inside"', "Bash", "DENY",
     "quoted > cannot vouch for cat", "tighten"),
    ('git log --format="%h > %s"', "Bash", "DENY",
     "quoted > cannot vouch for git log", None),
    ('git diff && echo "gitbrief"', "Bash", "DENY",
     "gitbrief only in quotes must not disarm the call", "tighten"),
    ('Get-Content "a>b.txt"', "PowerShell", "DENY",
     "quoted > cannot bound Get-Content", None),

    # --- masking is off where the quoted text IS a command ---------------
    ("ssh host '\ncat /etc/hosts'", "Bash", "DENY",
     "ssh payload stays denied (archive/...ssh-remote-payloads, WONTFIX)", None),
    ('bash -c "\ncat /etc/passwd"', "Bash", "DENY", "bash -c payload", None),
    ('python -c "import json' + chr(59) + ' json.loads(x)"', "Bash", "DENY",
     "inline eval payload is code, not prose", None),
    ("echo don't && rg -n foo src", "Bash", "DENY",
     "stray apostrophe must not disarm the rest", None),

    # --- the rules themselves --------------------------------------------
    ("rg -n needle src", "Bash", "DENY", "plain rg", None),
    ("grep -rn foo .", "Bash", "DENY", "plain grep", None),
    ("egrep foo .", "Bash", "DENY", "egrep", None),
    ("git diff", "Bash", "DENY", "plain git diff", None),
    ("git diff HEAD~3", "Bash", "DENY", "git diff with a ref", None),
    ("git log", "Bash", "DENY", "plain git log", None),
    ("git log -5", "Bash", "DENY", "count without --oneline", None),
    ("git diff --stat -p", "Bash", "DENY", "-p re-enables patch text", None),
    ("git grep foo", "Bash", "DENY", "git grep", None),
    ("cat README.md", "Bash", "DENY", "plain cat", None),
    ("Select-String foo *.py", "PowerShell", "DENY", "plain Select-String", None),
    ("Get-Content x.txt", "PowerShell", "DENY", "unbounded Get-Content", None),

    # --- carve-outs -------------------------------------------------------
    ("git log -1", "Bash", "ALLOW", "bounded log", None),
    ("git log --oneline -5", "Bash", "ALLOW", "oneline with small count", None),
    ("git diff --stat", "Bash", "ALLOW", "summary-only diff", None),
    # --- git output that provably cannot reach context ---------------------
    # docs/known-issues/archive/guard-hook-git-log-ignores-bounding-pipe.md:
    # the git branch scoped args with SEP_RE, which splits on a single `|`,
    # so the bounding pipe was cut off before it could be seen. These flip
    # DENY -> ALLOW deliberately, on the same rule the grep/cat/range-read
    # branches already applied.
    ("git log --oneline origin/main..HEAD | head", "Bash", "ALLOW",
     "log bounded by a pipe into head", "loosen"),
    ("git log --oneline | head -5", "Bash", "ALLOW",
     "log bounded by head with a count", "loosen"),
    ("git log | wc -l", "Bash", "ALLOW", "log counted, not printed", "loosen"),
    ("git diff | head -20", "Bash", "ALLOW",
     "diff bounded by a pipe into head", "loosen"),
    ("git diff > /tmp/patch.txt", "Bash", "ALLOW",
     "diff redirected to a file costs no tokens", "loosen"),
    ("git log --oneline", "Bash", "DENY",
     "oneline with no count and no bounding pipe", None),
    ("git log | head; git diff", "Bash", "DENY",
     "bound applies per command, not across the chain", None),
    ("rg -n needle src > /tmp/out.txt", "Bash", "ALLOW", "redirected search", None),
    ("rg -n needle src | head -5", "Bash", "ALLOW", "bounded search", None),
    ("rg -n needle src | wc -l", "Bash", "ALLOW", "counted search", None),
    ("rg -n needle src 2>/dev/null", "Bash", "DENY", "stderr isn't stdout", None),
    ("ls | grep foo", "Bash", "ALLOW", "pipeline filter", None),
    ("cat file > out.txt", "Bash", "ALLOW", "redirected cat", None),
    ("cat file | head -5", "Bash", "ALLOW", "bounded cat", None),
    ("Get-Content x.txt -Tail 5", "PowerShell", "ALLOW", "bounded Get-Content", None),
    ("ls | sls foo", "PowerShell", "ALLOW", "PS pipeline filter", None),
    ("gitbrief hunks", "Bash", "ALLOW", "suite tool", None),
    ("sgrep foo src", "Bash", "ALLOW", "suite tool", None),
    ("", "Bash", "ALLOW", "empty command", None),

    # --- the structo redirect's own bypass route --------------------------
    ("python -m json.tool manifest.json", "Bash", "DENY",
     "json.tool reaches the blocked outcome by another route", "tighten"),
    ("python3 -m json.tool --sort-keys a.json", "Bash", "DENY",
     "python3 spelling, with flags", "tighten"),
    ("python -m json.tool a.json > norm.json", "Bash", "ALLOW",
     "normalizing to a file costs no tokens", None),
    ("python -m json.tool a.json | wc -l", "Bash", "ALLOW",
     "counted json.tool", None),
    ('git commit -m "dropped python -m json.tool for structo"', "Bash",
     "ALLOW", "json.tool named in a commit message", None),

    # --- range reads that are whole-file dumps in disguise ----------------
    # The 2026-09-11 session's five real bypasses, plus the shapes around
    # them. FIXTURE is 12 lines, so a range ending at or past 12 covers it.
    (f"sed -n 1,163p {FIXTURE}", "Bash", "DENY",
     "range past the file's length", "tighten"),
    (f"sed -n 1,12p {FIXTURE}", "Bash", "DENY",
     "range covering exactly the whole file", "tighten"),
    (f"sed -n '1,12p' {FIXTURE}", "Bash", "DENY",
     "quoted script: masking must not hide the range", "tighten"),
    (f"sed -n 1,$p {FIXTURE}", "Bash", "DENY", "open-ended sed range", "tighten"),
    (f"sed 's/a/b/' {FIXTURE}", "Bash", "DENY",
     "sed without -n prints every line", "tighten"),
    (f"head -n 400 {FIXTURE}", "Bash", "DENY", "head above the cap", "tighten"),
    (f"head -n 12 {FIXTURE}", "Bash", "DENY",
     "head covering the whole file", "tighten"),
    (f"tail -n +2 {FIXTURE}", "Bash", "DENY", "tail from a line to EOF", "tighten"),
    (f"awk 'NR<=163' {FIXTURE}", "Bash", "DENY", "awk range past the cap", "tighten"),

    # Caught live while verifying this very fix: 59 of 73 lines passed the
    # first cap as "bounded". A range that near the end is the whole file.
    (f"sed -n 1,10p {FIXTURE}", "Bash", "DENY",
     "range reaching 80% of the file", "tighten"),
    (f"wc -l {FIXTURE}; sed -n 1,12p {FIXTURE}", "Bash", "DENY",
     "range derived from a wc -l in the same call", "tighten"),

    (f"sed -n 5,20p {FIXTURE}", "Bash", "ALLOW", "genuinely bounded range", None),
    (f"sed -n 5p {FIXTURE}", "Bash", "ALLOW", "single-line print", None),
    (f"sed -i 's/a/b/' {FIXTURE}", "Bash", "ALLOW", "in-place edit prints nothing", None),
    (f"head {FIXTURE}", "Bash", "ALLOW", "head's 10-line default", None),
    (f"head -5 {FIXTURE}", "Bash", "ALLOW", "small head", None),
    (f"tail -5 {FIXTURE}", "Bash", "ALLOW", "small tail", None),
    (f"wc -l {FIXTURE}", "Bash", "ALLOW", "counting is not reading", None),
    (f"awk '{{s+=$1}} END{{print s}}' {FIXTURE}", "Bash", "ALLOW",
     "aggregation prints one line", None),
    (f"sed -n 1,163p {FIXTURE} > /tmp/o", "Bash", "ALLOW", "redirected range read", None),
    (f"sed -n 1,163p {FIXTURE} | wc -l", "Bash", "ALLOW", "counted range read", None),
    ("ls | sed -n 1,163p", "Bash", "ALLOW", "pipeline filter, no file", None),
    ("sed -n 1,40p nonexistent-file.txt", "Bash", "ALLOW",
     "unmeasurable and under the cap: no opinion", None),
    ("sed -n 1,163p nonexistent-file.txt", "Bash", "DENY",
     "unmeasurable but over the cap: the cap still decides", "tighten"),
    (f"git commit -m \"used sed -n 1,163p {FIXTURE} before\"", "Bash", "ALLOW",
     "range vocabulary inside a commit message", None),

    # --- scoping: one bounded command never vouches for another ----------
    (f"sed -n 5,20p {FIXTURE} && sed -n 1,163p {FIXTURE}", "Bash", "DENY",
     "second range read unbounded", "tighten"),
    ("rg -n a src > /tmp/o && rg -n b src", "Bash", "DENY", "second search unbounded", None),
    ("rg -n a src > /tmp/o1 && rg -n b src > /tmp/o2", "Bash", "ALLOW",
     "both searches redirected", None),
    ("git log -1 && git log", "Bash", "DENY", "second log unbounded", None),
    ("rg -n needle src && echo done > log.txt", "Bash", "DENY",
     "the redirect isn't the search's", None),
    ("rg -n needle src | grep other", "Bash", "DENY", "still reaches context", None),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hook", default=DEFAULT_HOOK)
    ap.add_argument("--baseline", help="pre-change copy, for a differential run")
    args = ap.parse_args()

    hook = load("guard_hook", args.hook)
    fails = 0

    for cmd, tool, want, label, _ in CORPUS:
        got = verdict(hook, cmd, tool)
        ok = got == want
        fails += not ok
        print(f"{'ok  ' if ok else 'FAIL'} [{want:5}] {label}"
              + ("" if ok else f"  -> got {got}"))

    # Offsets must survive masking: the savings path slices the raw command
    # using indices from a match against the masked one.
    if hasattr(hook, "mask_literals"):
        for s in (COMMIT_MSG, BARE_HEREDOC, 'rg -n "a>b" src', "echo don't", ""):
            if len(hook.mask_literals(s)) != len(s):
                print(f"FAIL mask_literals changed length of {s!r:.40}")
                fails += 1
        print("ok   mask_literals preserves offsets")

    if args.baseline:
        base = load("guard_baseline", args.baseline)
        print(f"\n--- differential vs {args.baseline} ---")
        for cmd, tool, _, label, flip in CORPUS:
            o, n = verdict(base, cmd, tool), verdict(hook, cmd, tool)
            if o == n:
                continue
            if o == "DENY" and n == "ALLOW" and flip != "loosen":
                print(f"REGRESSION (now allows): {label}: {cmd!r:.60}")
                fails += 1
            else:
                print(f"ok   flipped {o}->{n} as intended: {label}")

    print(f"\n{fails} failure(s) over {len(CORPUS)} cases")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
