"""PreToolUse/PostToolUse guard: redirect token-heavy tool calls to the LLM-tools suite.

Shell rules are matched against a *masked* copy of the command in which
quoted spans and heredoc bodies are blanked to `x` (`mask_literals`, which
preserves offsets). Without it the regexes cannot tell a command from an
argument that looks like one, and were wrong both ways: a commit message
line starting with `rg` tripped the search rule, and `rg -n "a>b" src`
satisfied the redirect carve-out and dumped. Masking is skipped entirely
when the call contains a command that executes its quoted argument
(`ssh`, `bash -c`, ...), so those payloads keep failing closed.

PreToolUse denies (each reason names the exact replacement command):
  - Bash/PowerShell `git diff` / `git log` / `git grep` -> gitbrief hunks |
    show | log | pr, or sgrep for git grep. Carve-outs for invocations
    bounded small by construction: `git log -1`/`-n 1`, or `--oneline`
    with an explicit count <= 10; and `git diff` in a summary-only format
    (`--stat`, `--numstat`, `--shortstat`, `--dirstat`, `--name-only`,
    `--name-status`), which cannot emit patch text. Flags are read from
    that sub-command's own arguments, not from anywhere in the command
    string, and every `git diff|log|grep` in a chain is checked — a bounded
    one does not vouch for an unbounded one after it.

Every shell deny says outright that nothing in the call ran, since a deny
verdict rejects the whole Bash command including any `&&`-chained steps.
  - Bash/PowerShell grep/rg file searches at command position -> sgrep
    (`| grep` pipeline filters of another command's output stay allowed;
    so do searches whose stdout is redirected to a file or piped into
    head/tail/wc, on the same reasoning as the `cat` carve-out below —
    output that never renders costs no tokens. Scoped per match, so a
    redirect on one command in a chain does not vouch for another.)
  - Bash/PowerShell `cat FILE` dumps -> xread / structo
    (heredocs, redirects, and pipes into head/tail/wc stay allowed)
  - PowerShell Get-Content/gc/type without a bounding flag -> xread / Read
  - PowerShell Select-String/sls file searches at command position -> sgrep
  - node -e / python -c one-liners that read + parse JSON -> structo
  - Grep tool in content mode over a directory (no small head_limit) -> sgrep
  - Read of a whole file above per-kind size limits (data 8KB, code/docs
    20KB, other 50KB) -> structo / xread / a bounded Read

PostToolUse (Read): at most one nudge per session when a whole-file
Read of a code/data file >= 6KB was allowed but a suite tool was cheaper.

PostToolUse (Bash/PowerShell): when the command invoked one of the 11 suite
tools, log actual output size to .savings/events.jsonl and roll it into
.savings/aggregate.json + a regenerated savings_record.md at SAVINGS_ROOT.
A raw-vs-suite byte "saved" figure is computed for:
  - xread/structo: baseline = the named file's raw size (no extra process)
  - gitbrief: baseline = byte size of running the equivalent raw `git diff`/
    `git log` command as a background subprocess (git only; never printed
    or returned to the model - measured for length only)
  - sgrep: baseline = byte size of the equivalent raw `rg` content-mode
    search as a background subprocess, carrying the same match-shaping
    flags (-C/-i/-F/-w/-t/-g) and the same paths so both sides answer the
    same question; skipped for --files-only/--counts-only calls, since
    comparing those to a raw content dump wouldn't be a fair comparison
  - codediff: baseline = byte size of the equivalent raw `git diff` for the
    same revision range, by the same method as gitbrief
  - runlite: baseline = the log size runlite reports in its own header
    (`[log N B]`). Exact, not measured: runlite buffers the whole log, and
    re-running a build to size it would be absurd and non-deterministic
Other suite tools (repomap, repoindex, tokq) have no raw equivalent to
measure and are counted without a baseline. rq and testmap are archived
(docs/decisions/0009 in LLM-tools) and no longer tracked here.
These extra subprocesses cost wall-clock time, never model tokens - their
output is measured for length and discarded, never surfaced to the model.

Fail-open: any error, or anything unrecognized, allows the call.
"""
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

DATA_LIMIT = 8_000    # bytes; structo covers these files completely
CODE_LIMIT = 20_000   # bytes; xread --symbol/--query covers targeted access
OTHER_LIMIT = 50_000  # bytes; roughly 12-15k tokens of raw text
NUDGE_FLOOR = 6_000   # bytes; below this a whole-file Read is cheap enough

# Extensions Read renders natively (images/notebooks/pdf) - never block these.
BINARY_OK = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
             ".pdf", ".ipynb"}
DATA_EXT = {".json", ".jsonl", ".yaml", ".yml", ".xml"}
CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".go",
            ".rs", ".c", ".h", ".cpp", ".hpp", ".cc", ".cs", ".java",
            ".rb", ".php", ".swift", ".kt", ".md", ".markdown"}

# A token at "command position": start of string/line, or after ; && ||
CMD = r"(?:^|[;\n]|&&|\|\|)\s*"
GIT_RE = re.compile(
    r"(?<![\w./\\-])git\s+(?:-[^\s]+\s+|-C\s+\S+\s+)*(diff|log|grep)\b")
# Where one command ends and the next begins, for scoping a match's arguments.
SEP_RE = re.compile(r"[;\n|]|&&|\|\|")
# Where one *pipeline* ends. Unlike SEP_RE this does not split on a single
# `|`, because a bounding `| head -5` belongs to the search it bounds.
PIPE_END_RE = re.compile(r"[;\n]|&&|\|\|")
# More than one command in the call, so a deny discards work the model asked for.
COMPOUND_RE = re.compile(r"&&|\|\||[;\n]")
# `-5`, `-n5`, `-n 5` — an explicit commit count on `git log`.
LOG_COUNT_RE = re.compile(r"(?:^|\s)-(?:n\s*)?(\d+)\b")
# `git diff` formats that cannot print patch text: one line per changed file
# at most, bounded by construction the same way `git log -1` is.
DIFF_SUMMARY_RE = re.compile(
    r"(?:^|\s)--(?:stat|numstat|shortstat|dirstat|name-only|name-status)"
    r"(?:=\S*)?(?=\s|$)")
# ...unless something re-enables patch output alongside them.
DIFF_PATCH_RE = re.compile(r"(?:^|\s)(?:-p|-u|--patch|--patch-with-stat|"
                           r"--cc|-c|-U\d*|--unified(?:=\d+)?)(?=\s|$)")
GREP_RE = re.compile(CMD + r"(?:command\s+)?(?:grep|egrep|fgrep|rg)\b")
CAT_RE = re.compile(CMD + r"cat\s+\S")
PS_GC_RE = re.compile(CMD + r"(?:Get-Content|gc|type)\b", re.IGNORECASE)
PS_SLS_RE = re.compile(CMD + r"(?:Select-String|sls)\b", re.IGNORECASE)
INLINE_EVAL_RE = re.compile(r"\bnode\s+(?:-e|--eval)\b|\bpython3?\s+-c\b")
JSON_PARSE_RE = re.compile(r"JSON\.parse|json\.loads?\b")
BOUNDED_PIPE_RE = re.compile(r"\|\s*(?:head|tail|wc)\b")
# A `>` not immediately preceded by a digit, so `2>/dev/null` (stderr-only)
# doesn't masquerade as a real stdout redirect the way `>`/`1>`/`&>` do.
STDOUT_REDIRECT_RE = re.compile(r"(?<!\d)>")
PS_BOUNDED_RE = re.compile(r"-TotalCount\b|-Tail\b|-First\b|-Last\b",
                           re.IGNORECASE)

# --- savings tracking -------------------------------------------------
# Where the LLM-tools checkout lives, per host. This file is deployed
# verbatim to every host that runs it (Windows workstation, npmserv), so it
# must not carry a single hard-coded root: the server copy used to be
# hand-patched here, which is how it silently drifted three weeks behind.
# Picking the first root that actually exists keeps one file valid
# everywhere; `LLM_TOOLS_SAVINGS_ROOT` still wins if set.
KNOWN_SAVINGS_ROOTS = (r"G:\DataExtremes\Code\LLM-tools",
                       "/opt/des_stack/LLM-tools")


def _default_savings_root():
    """The first known checkout present on this host, or None.

    None rather than a guess: writing to a root that doesn't exist would
    create a junk directory named after the *other* platform's path (a
    literal `G:\\DataExtremes\\...` folder on Linux), and savings telemetry
    is not worth that. Recording is skipped instead, which is the same
    fail-open posture the rest of the hook takes.
    """
    for root in KNOWN_SAVINGS_ROOTS:
        if os.path.isdir(root):
            return root
    return None


SAVINGS_ROOT = os.environ.get("LLM_TOOLS_SAVINGS_ROOT") or _default_savings_root()
SAVINGS_DIR = os.path.join(SAVINGS_ROOT, ".savings") if SAVINGS_ROOT else None
EVENTS_PATH = os.path.join(SAVINGS_DIR, "events.jsonl") if SAVINGS_DIR else None
AGG_PATH = os.path.join(SAVINGS_DIR, "aggregate.json") if SAVINGS_DIR else None
RECORD_PATH = (os.path.join(SAVINGS_ROOT, "savings_record.md")
               if SAVINGS_ROOT else None)
BYTES_PER_TOKEN = 3.7  # same fallback heuristic tokq documents using
# v3: codediff and runlite gained baselines, and sgrep stopped repeating the
# file path on context lines. v2 sgrep rows stay creditable - they were fair
# measurements of the format that existed then - but the version marks the
# boundary if the two formats ever need separating.
EVENT_SCHEMA = 3

SUITE_TOOLS = ("xread", "sgrep", "structo", "gitbrief", "repomap",
               "repoindex", "codediff", "runlite", "tokq")
SUITE_TOOL_RE = re.compile(
    CMD + r"(?:python3?\s+\S*[\\/])?(?:\./)?(" +
    "|".join(SUITE_TOOLS) + r")(?:\.py|\.cmd|\.sh)?\b")


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def _own_args(command: str, end: int) -> str:
    """The matched command's own arguments, up to the next shell separator.

    Scoping matters: a `-1` belonging to some later command in the chain
    must not read as a bound on this one.
    """
    tail = command[end:]
    sep = SEP_RE.search(tail)
    return tail[:sep.start()] if sep else tail


def _log_is_bounded(args: str) -> bool:
    """True for `git log` calls that are small by construction, not by luck."""
    m = LOG_COUNT_RE.search(args)
    if not m:
        return False  # no count at all is the unbounded dump the rule targets
    n = int(m.group(1))
    if n == 1:
        return True  # one commit is cheap in any format
    return n <= 10 and "--oneline" in args


def _diff_is_summary(args: str) -> bool:
    """True for `git diff` formats that provably cannot emit patch text.

    `--stat`/`--numstat`/`--name-only` and friends print at most one line
    per changed file — the same bounded-by-construction plumbing the
    `git log -1` carve-out recognises, and cheaper than the gitbrief call
    that would answer the question. Flags are read from this sub-command's
    own arguments, so a later pipe can't whitelist a raw diff.
    """
    return bool(DIFF_SUMMARY_RE.search(args)) and not DIFF_PATCH_RE.search(args)


def _own_pipeline(command: str, end: int) -> str:
    """The matched command's own pipeline, up to the next command boundary.

    Like `_own_args` but keeps `|`, so a bounding `| head` stays attached to
    the search it bounds while a redirect belonging to some *later* command
    in the chain cannot vouch for this one.
    """
    tail = command[end:]
    m = PIPE_END_RE.search(tail)
    return tail[:m.start()] if m else tail


def _output_reaches_context(args: str) -> bool:
    """False when a command's stdout provably can't land in the model's
    context: redirected to a file, or piped through head/tail/wc.

    This is the `cat` rule's own carve-out, applied to searches for the same
    reason. Output going to a file costs no tokens; getting it back into
    context takes a second hop that is itself guarded (Read is size-limited
    here, xread/structo are budgeted). Measuring a suite tool against its raw
    equivalent — the method the savings record is built on — is exactly this
    shape, and denying it made the baseline harder to produce than to fake.
    """
    return not (STDOUT_REDIRECT_RE.search(args)
                or BOUNDED_PIPE_RE.search(args))


# A heredoc introducer: `<<EOF`, `<<-EOF`, `<<'EOF'`, `<<"EOF"`.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# Commands that *execute* their quoted argument, so text inside the quotes is
# a real command line after all and masking it would open a bypass. Seeing any
# of these turns masking off for the whole call, keeping the pre-masking
# behaviour (ssh payloads stay denied — archive/guard-hook-denies-ssh-remote-
# payloads.md is a recorded WONTFIX, not an oversight).
_EXEC_QUOTED_RE = re.compile(
    r"(?<![\w./\\-])(?:ssh|wsl)(?![\w.-])"
    r"|(?<![\w./\\-])(?:docker|podman|kubectl)\s+exec(?![\w.-])"
    r"|(?<![\w./\\-])(?:bash|sh|zsh|dash|pwsh|powershell|python3?|node|perl|"
    r"ruby)\s+(?:-\S+\s+)*(?:-c|-e|--eval|-Command|-EncodedCommand)(?![\w.-])"
    r"|(?<![\w./\\-])cmd(?:\.exe)?\s+(?:/\w+\s+)*/[ck](?![\w.-])")


def _mask_heredocs(s: str) -> str:
    """Blank heredoc bodies, preserving length so offsets stay valid."""
    out = list(s)
    pos = 0
    while True:
        m = _HEREDOC_RE.search(s, pos)
        if not m:
            break
        nl = s.find("\n", m.end())
        if nl == -1:
            break  # no body on this line; nothing to blank
        delim, end, i = m.group(2), len(s), nl + 1
        while i <= len(s):
            j = s.find("\n", i)
            line = s[i:] if j == -1 else s[i:j]
            if line.strip() == delim:
                end = i
                break
            if j == -1:
                break
            i = j + 1
        for k in range(nl + 1, end):
            out[k] = "x"
        pos = end
    return "".join(out)


def _mask_quotes(s: str) -> str:
    """Blank the interiors of balanced quoted spans, preserving length.

    An *unterminated* quote is left alone: masking to end-of-string on a
    stray apostrophe would silently disarm every rule after it, and this
    function must only ever be able to fail closed.
    """
    out = list(s)
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c in "'\"":
            j = i + 1
            while j < n:
                if c == '"' and s[j] == "\\":
                    j += 2
                    continue
                if s[j] == c:
                    break
                j += 1
            if j >= n:
                i += 1  # unterminated: leave the rest raw
                continue
            for k in range(i + 1, j):
                out[k] = "x"
            i = j + 1
            continue
        i += 1
    return "".join(out)


def mask_literals(command: str) -> str:
    """The command with quoted text and heredoc bodies blanked out to `x`,
    same length, so offsets from a match still index the real string.

    Every shell rule here is a regex over the command string, and without
    this the regexes cannot tell a command from an argument that merely
    looks like one. That was wrong in both directions: a commit message
    whose line began with `rg` tripped the search rule (fails closed, just
    annoying), and a search whose *pattern* contained `>` or `| head`
    satisfied the redirect/bounding carve-out and dumped unbudgeted output
    (fails open — no signal at all). Blanking the literals fixes both, and
    makes the carve-out ask the right question: does *this command*
    redirect, not does a `>` appear anywhere in these bytes.
    """
    try:
        if _EXEC_QUOTED_RE.search(command):
            return command
        return _mask_quotes(_mask_heredocs(command))
    except Exception:
        return command  # masking must never be the reason a rule stops firing


def deny_shell(command: str, reason: str) -> None:
    """Deny a shell call, saying plainly what the verdict costs."""
    if COMPOUND_RE.search(command):
        reason += (" NOTE: nothing in this call ran. A deny rejects the whole "
                   "command, including steps chained with && || ; or "
                   "newlines — any commit/push/build in it did NOT happen. "
                   "Re-run those as their own call.")
    deny(reason)


def check_shell(tool: str, raw_command: str) -> None:
    # Every rule below reads the masked string, never the raw one: quoted
    # text and heredoc bodies are arguments, not commands. `deny_shell` gets
    # it too — a `;` inside quotes doesn't make the call compound.
    command = mask_literals(raw_command)
    if "gitbrief" in command:
        return
    # Every `git diff|log|grep` in the call, not just the first: one bounded
    # sub-command must not vouch for an unbounded one chained after it.
    for m in GIT_RE.finditer(command):
        sub = m.group(1)
        if sub == "grep":
            deny_shell(command,
                       "Raw `git grep` dumps matching lines. Use "
                       "`sgrep PATTERN [PATH]` (start with --files-only or "
                       "--counts-only, then narrow).")
        args = _own_args(command, m.end())
        if sub == "log" and _log_is_bounded(args):
            continue
        if sub == "diff" and _diff_is_summary(args):
            continue
        deny_shell(
            command,
            f"Raw `git {sub}` output is token-heavy. Use the LLM-tools "
            "suite instead: `gitbrief hunks [FILE...]` or `gitbrief pr "
            "BASE` for diffs, `gitbrief log` for history, `gitbrief "
            "show FILE` for one file's diff. (Bounded lookups are allowed: "
            "`git log -1`/`-n 1` or `--oneline` with a count of 10 or "
            "fewer, and `git diff` in a summary-only format — `--stat`, "
            "`--numstat`, `--shortstat`, `--name-only`, `--name-status` — "
            "none of which can print patch text.)"
        )
    for m in GREP_RE.finditer(command):
        # Scoped per match, not across the whole string: one redirected
        # search must not whitelist an unredirected one chained after it.
        if not _output_reaches_context(_own_pipeline(command, m.end())):
            continue
        deny_shell(
            command,
            "Raw grep/rg over files dumps unbudgeted lines. Use "
            "`sgrep PATTERN [PATH]` — start with --files-only or "
            "--counts-only, then narrow. (Filtering another command's "
            "output with `| grep` is allowed and was not matched here; so "
            "is a search whose stdout goes to a file or through "
            "head/tail/wc, which costs no tokens.)")
    if (CAT_RE.search(command) and "<<" not in command
            and not STDOUT_REDIRECT_RE.search(command)
            and not BOUNDED_PIPE_RE.search(command)):
        deny_shell(
            command,
            "`cat FILE` dumps the whole file. Use `xread FILE --symbol "
            "NAME | --query \"...\" | --headings` (docs), `structo FILE` "
            "for JSON/YAML/XML, or a bounded Read with offset/limit.")
    if (INLINE_EVAL_RE.search(command) and JSON_PARSE_RE.search(command)):
        deny_shell(
            command,
            "Ad-hoc inline JSON parsing re-reads the raw file. Use "
            "`structo FILE` for the shape or `structo FILE --path a.b[0].c`"
            " for one value.")
    if tool == "PowerShell":
        if PS_GC_RE.search(command) and not PS_BOUNDED_RE.search(command):
            deny_shell(
                command,
                "Unbounded Get-Content dumps the whole file. Add "
                "-TotalCount/-Tail, or use `xread FILE --symbol NAME | "
                "--query \"...\"` / `structo FILE` for data files.")
        if PS_SLS_RE.search(command):
            deny_shell(
                command,
                "Select-String over files dumps unbudgeted lines. Use "
                "`sgrep PATTERN [PATH]` — start with --files-only or "
                "--counts-only. (Piping another command's output into "
                "`| sls` is allowed and was not matched here.)")


def check_grep(tool_input: dict) -> None:
    if tool_input.get("output_mode") != "content":
        return  # files_with_matches / count are already compact
    head = tool_input.get("head_limit")
    if isinstance(head, (int, float)) and 0 < head <= 25:
        return  # explicitly bounded peek
    path = tool_input.get("path") or ""
    if path and os.path.isfile(path):
        return  # single-file content grep is bounded and Edit-adjacent
    deny("Grep in content mode across a directory dumps raw lines. Use "
         "`sgrep PATTERN [PATH]` (start with --files-only or --counts-only, "
         "then narrow), or re-run Grep with output_mode files_with_matches/"
         "count, a single-file path, or head_limit <= 25.")


def _read_limit(ext: str) -> int:
    if ext in DATA_EXT:
        return DATA_LIMIT
    if ext in CODE_EXT:
        return CODE_LIMIT
    return OTHER_LIMIT


def check_read(tool_input: dict) -> None:
    if tool_input.get("limit") or tool_input.get("offset") or tool_input.get("pages"):
        return
    path = tool_input.get("file_path") or ""
    ext = os.path.splitext(path)[1].lower()
    if ext in BINARY_OK:
        return
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size <= _read_limit(ext):
        return
    hint = ("`structo FILE` (schema/shape) or `structo FILE --path a.b`"
            if ext in DATA_EXT else
            "`xread FILE --symbol NAME` or `xread FILE --query \"...\"` "
            "(--headings for docs)")
    deny(
        f"File is {size:,} bytes - reading it whole wastes context. "
        f"Prefer {hint}. If you genuinely need raw lines (e.g. before an "
        "Edit), re-Read with offset/limit."
    )


def nudge_read(data: dict) -> None:
    tool_input = data.get("tool_input") or {}
    if tool_input.get("limit") or tool_input.get("offset") or tool_input.get("pages"):
        return
    path = tool_input.get("file_path") or ""
    ext = os.path.splitext(path)[1].lower()
    if ext not in DATA_EXT and ext not in CODE_EXT:
        return
    try:
        size = os.path.getsize(path)
    except OSError:
        return
    if size < NUDGE_FLOOR:
        return
    marker = os.path.join(
        tempfile.gettempdir(),
        f"llm-tools-nudge-{data.get('session_id') or 'nosession'}.flag")
    if os.path.exists(marker):
        return  # one nudge per session is enough
    with open(marker, "w"):
        pass
    tool = ("structo FILE [--path a.b]" if ext in DATA_EXT
            else "xread FILE --symbol NAME | --query \"...\"")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"Guard nudge: that whole-file Read ({size:,} bytes) was "
                f"allowed, but `{tool}` is usually cheaper for targeted "
                "access. Prefer the LLM-tools suite for the rest of this "
                "session, including mid-task."),
        }
    }))


def _response_text(resp) -> str:
    if isinstance(resp, str):
        return resp
    if isinstance(resp, dict):
        parts = [v for k in ("stdout", "output", "result", "text", "content")
                  if isinstance(v := resp.get(k), str)]
        if parts:
            return "\n".join(parts)
        return json.dumps(resp)
    return str(resp)


def _first_file_arg(rest: str, cwd: str):
    for tok in rest.split():
        if tok.startswith("-"):
            continue
        path = tok if os.path.isabs(tok) else os.path.join(cwd, tok)
        return path
    return None


def _run_raw_bytes(args, cwd: str, timeout: float = 5.0):
    """Run a raw baseline command in the background; return len(stdout) only.
    Output is never printed or returned to the model - byte count only.
    Non-zero exit means the raw equivalent didn't honestly run (bad pattern,
    bad path, no matches): return None so the call logs as n/a rather than
    a fake 0-byte baseline that scores the suite tool as pure loss."""
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, timeout=timeout)
        if p.returncode != 0:
            return None
        return len(p.stdout)
    except Exception:
        return None


# Shell operators that end the suite-tool invocation. Anything from here on
# (`| head -40`, `> out.txt`, `2>&1`) belongs to the shell, not the tool, and
# must never reach a baseline command as if it were a pattern or a path.
_SHELL_OPS = {"|", "|&", ";", "&", "&&", "||", ">", ">>", "<", "<<",
              "1>", "2>", "&>", "2>&1", "1>&2", ">&"}


def _shell_tokens(rest: str):
    """Quote-aware split of a suite-tool argument string, truncated at the
    first unquoted shell operator. Returns None if the string can't be
    tokenized (e.g. a Windows path mangled by posix backslash escaping) so
    the caller logs n/a rather than running a half-parsed baseline.

    Quote-aware matters: a bare regex split on `|` would cut a quoted
    alternation pattern like 'queryRaw|executeRaw' in half and measure a
    baseline for a different search than the one that ran."""
    try:
        tokens = shlex.split(rest, posix=True)
    except ValueError:
        return None
    out = []
    for t in tokens:
        if t in _SHELL_OPS:
            break
        out.append(t)
    return out


def _gitbrief_baseline(rest: str, cwd: str):
    git = shutil.which("git")
    if not git:
        return None
    tokens = _shell_tokens(rest)
    if not tokens:
        return None
    sub, args = tokens[0], tokens[1:]
    positional = [t for t in args if not t.startswith("-")]
    if sub == "hunks":
        cmd = [git, "--no-pager", "diff", "HEAD", "--no-renames"]
        if positional:
            cmd += ["--"] + positional
        return _run_raw_bytes(cmd, cwd)
    if sub == "show":
        if not positional:
            return None
        cmd = [git, "--no-pager", "diff", "HEAD", "--no-renames",
               "--", positional[0]]
        return _run_raw_bytes(cmd, cwd)
    if sub == "log":
        cmd = [git, "--no-pager", "log"]
        i = 0
        while i < len(args):
            if args[i] in ("-n", "--grep", "--author") and i + 1 < len(args):
                cmd += [args[i], args[i + 1]]
                i += 2
            else:
                i += 1
        return _run_raw_bytes(cmd, cwd)
    if sub == "pr":
        if not positional:
            return None
        return _run_raw_bytes(
            [git, "--no-pager", "diff", f"{positional[0]}...HEAD"], cwd)
    return None


# sgrep flags that consume the next token, so their values are never
# mistaken for the pattern/path positionals.
_SGREP_VALUE_FLAGS = {"-t", "--type", "-g", "--glob", "-C", "--context",
                      "--max-tokens", "--config", "--rg"}
# sgrep flags that change *which lines rg would print*, and so must be
# mirrored onto the baseline command for it to answer the same question.
# Kept in sync with sgrep.py's own rg argument construction (main()).
_SGREP_PASSTHROUGH_BOOL = {"-i": "-i", "--ignore-case": "-i",
                           "-F": "-F", "--fixed-strings": "-F",
                           "-w": "-w", "--word-regexp": "-w"}
_SGREP_PASSTHROUGH_VALUE = {"-t": "-t", "--type": "-t",
                            "-g": "-g", "--glob": "-g",
                            "-C": "-C", "--context": "-C"}


def _sgrep_baseline(rest: str, cwd: str):
    """Byte size of the raw `rg` command that answers the same question.

    "Same question" is the whole point: the baseline must carry every flag
    that changes which lines rg prints - above all -C. Measuring a
    `sgrep PAT src -C 12` call against a context-free `rg -n PAT src`
    compares 12 lines per match to one, and scores sgrep as a large loss
    for faithfully printing the context it was asked for. All paths are
    passed too; taking only the first understated multi-path searches."""
    tokens = _shell_tokens(rest)
    if not tokens:
        return None
    if any(t in ("--files-only", "--counts-only") for t in tokens):
        return None  # not a fair comparison against a raw content dump
    positional = []
    passthrough = []
    skip = False
    pending = None
    for t in tokens:
        if skip:
            skip = False
            if pending:
                passthrough += [pending, t]
                pending = None
            continue
        if t.startswith("-") and t != "-":
            if t in _SGREP_VALUE_FLAGS:
                skip = True
                pending = _SGREP_PASSTHROUGH_VALUE.get(t)
            elif t in _SGREP_PASSTHROUGH_BOOL:
                passthrough.append(_SGREP_PASSTHROUGH_BOOL[t])
            continue
        positional.append(t)
    if not positional:
        return None
    rg = shutil.which("rg")
    if not rg:
        return None
    # `--` so a pattern starting with `-` is not read as a flag, matching
    # how sgrep hands the pattern to rg itself.
    cmd = [rg, "-n"] + passthrough + ["--"] + positional
    return _run_raw_bytes(cmd, cwd)


# codediff flags that consume the next token.
_CODEDIFF_VALUE_FLAGS = {"--max-tokens", "--repoindex", "--repoindex-lib"}


def _codediff_baseline(rest: str, cwd: str):
    """Byte size of the raw `git diff` that codediff summarized.

    codediff's whole claim is that reading what a change *means* beats
    reading the hunks, so the hunks are the honest baseline - the same
    comparison gitbrief already makes. `--json` is credited too: it is the
    narrator payload, not a machine-only export, and it answers the same
    question at the same altitude."""
    git = shutil.which("git")
    if not git:
        return None
    tokens = _shell_tokens(rest)
    if tokens is None:
        return None
    positional = []
    skip = False
    for t in tokens:
        if skip:
            skip = False       # a flag's value is not a revision: `--max-
            continue           # tokens 0` must not be read as the ref `0`
        if t.startswith("-"):
            skip = t in _CODEDIFF_VALUE_FLAGS
            continue
        positional.append(t)
    cmd = [git, "--no-pager", "diff", "--no-renames"]
    if "--staged" in tokens or "--cached" in tokens:
        cmd.append("--cached")
    elif positional:
        cmd.append(positional[0])   # REF or A..B, passed through as given
    else:
        cmd.append("HEAD")          # default: working tree vs HEAD
    return _run_raw_bytes(cmd, cwd, timeout=10.0)


# runlite reports the size of the log its report stands in for, in its own
# header line. Reading it back is the only way to baseline runlite: the
# alternative is re-running the build, which is slow, side-effecting, and
# not even guaranteed to produce the same log.
_RUNLITE_LOG_RE = re.compile(r"\[log (\d+) B\]")


def _runlite_baseline(response_text: str):
    m = _RUNLITE_LOG_RE.search(response_text)
    return int(m.group(1)) if m else None


_CONTEXT_FLAG_RE = re.compile(r"(?:^|\s)(?:-C|--context)(?:[=\s]|$)")


def _event_credited(ev: dict) -> bool:
    """Whether an event's baseline is a fair comparison for its output.

    Fairness is decided at read time, not write time, so a baseline bug
    found later can be retired from the numbers without inventing
    replacement measurements for calls whose working tree is long gone.

    v1 sgrep baselines dropped every flag before running `rg`, so a call
    that asked for -C printed N lines per match while its baseline printed
    one. Those rows are uncreditable - not zero, not negative, absent."""
    if ev.get("baseline_bytes") is None:
        return False
    if not ev.get("baseline_bytes"):
        return False  # a raw command that matched nothing is n/a, not 0
    if (ev.get("tool") == "sgrep" and ev.get("v", 1) < 2
            and _CONTEXT_FLAG_RE.search(ev.get("argv") or "")):
        return False
    return True


def _read_events():
    events = []
    try:
        with open(EVENTS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    continue  # a torn append never poisons the whole log
    except OSError:
        pass
    return events


def rebuild_aggregate() -> dict:
    """Fold events.jsonl into aggregate.json and rewrite the report.

    The aggregate is a pure function of the event log rather than an
    incrementally mutated counter: an incremental counter silently drifts
    when a write is lost, and cannot be corrected when a baseline rule
    changes. Re-reading the log costs wall-clock time on a hook that
    already shells out to `rg`/`git`, and costs the model nothing."""
    agg = {}
    for ev in _read_events():
        tool = ev.get("tool")
        if tool not in SUITE_TOOLS:
            continue
        row = agg.setdefault(tool, {
            "count": 0, "with_baseline": 0, "actual_bytes": 0,
            "credited_actual_bytes": 0, "baseline_bytes": 0, "last_ts": ""})
        row["count"] += 1
        row["actual_bytes"] += ev.get("actual_bytes") or 0
        ts = ev.get("ts") or ""
        if ts > row["last_ts"]:
            row["last_ts"] = ts
        if _event_credited(ev):
            row["with_baseline"] += 1
            row["baseline_bytes"] += ev["baseline_bytes"]
            row["credited_actual_bytes"] += ev.get("actual_bytes") or 0
    os.makedirs(SAVINGS_DIR, exist_ok=True)
    with open(AGG_PATH, "w", encoding="utf-8") as f:
        json.dump(agg, f, indent=2, sort_keys=True)
    _write_report(agg)
    return agg


def _load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _tok(n_bytes) -> str:
    return f"~{int(round(n_bytes / BYTES_PER_TOKEN)):,}"


# The event log is append-only and nothing trims it; every suite call
# re-folds the whole thing (ADR-0007 explains why that purity is worth
# keeping). Surfacing the size here means the compaction trigger is read by
# whoever reads the record, instead of waiting to be rediscovered as a
# slowdown.
COMPACT_AT_BYTES = 4_000_000


def _log_size_note() -> str:
    try:
        size = os.path.getsize(EVENTS_PATH)
    except OSError:
        return ""
    note = " (%.1f MB, append-only)" % (size / 1e6)
    if size >= COMPACT_AT_BYTES:
        note += (" — **over the %.0f MB compaction trigger; see "
                 "docs/decisions/0007-savings-log-operations.md**"
                 % (COMPACT_AT_BYTES / 1e6))
    return note


def _write_report(agg: dict) -> None:
    rows = []
    # Every suite tool gets a row, including the ones with no calls at all.
    # Ranking only the tools that were used hides the more important
    # signal: a tool nobody reaches for is not "neutral", it is unadopted,
    # and it never appears in a table keyed on savings.
    for t in sorted(SUITE_TOOLS):
        row = agg.get(t) or {
            "count": 0, "with_baseline": 0, "actual_bytes": 0,
            "credited_actual_bytes": 0, "baseline_bytes": 0, "last_ts": ""}
        credited = row.get("with_baseline", 0)
        # Compare like with like: only the output of calls that actually got
        # a baseline may be charged against that baseline. Charging every
        # call's output against the credited subset's baseline manufactures
        # losses for tools whose calls are often uncreditable.
        saved = (row["baseline_bytes"] - row.get("credited_actual_bytes", 0)
                 if credited else None)
        rows.append((t, row, credited, saved))
    # Credited rows first, biggest savings on top; then uncredited-but-used
    # by call count; unused tools last, where a zero is easy to spot.
    rows.sort(key=lambda r: (r[1]["count"] == 0, r[3] is None,
                             -(r[3] or 0), -r[1]["count"], r[0]))
    total_calls = sum(r[1]["count"] for r in rows)
    credited_calls = sum(r[2] for r in rows)
    net_saved = sum(r[3] for r in rows if r[3] is not None)
    updated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# LLM-tools savings record",
        "",
        "These measurements come from real development sessions, not "
        "synthetic benchmarks.",
        "",
        f"**Net savings: {_tok(net_saved)} tokens** across {total_calls} "
        f"suite calls ({credited_calls} credited against a measured raw "
        f"equivalent). Updated {updated}.",
        "",
        "| tool | calls | last used | credited | output | credited output "
        "| raw equivalent | saved | avg saved/credited call |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for t, row, credited, saved in rows:
        out_s = _tok(row["actual_bytes"])
        last = (row.get("last_ts") or "")[:10] or "**never**"
        if saved is None:
            cred_out_s = base_s = saved_s = avg_s = "n/a"
        else:
            cred_out_s = _tok(row.get("credited_actual_bytes", 0))
            base_s = _tok(row["baseline_bytes"])
            saved_s = f"**{_tok(saved)}**"
            avg_s = _tok(saved / credited)
        lines.append(f"| {t} | {row['count']} | {last} | {credited} | "
                     f"{out_s} | {cred_out_s} | {base_s} | {saved_s} | "
                     f"{avg_s} |")
    total_actual = sum(r[1]["actual_bytes"] for r in rows)
    total_credited_actual = sum(r[1].get("credited_actual_bytes", 0)
                                for r in rows if r[3] is not None)
    total_baseline = sum(r[1]["baseline_bytes"] for r in rows
                         if r[3] is not None)
    avg_total = (_tok(net_saved / credited_calls) if credited_calls
                 else "n/a")
    unused = [r[0] for r in rows if r[1]["count"] == 0]
    unused_note = (" Currently never called: " +
                   ", ".join(f"`{u}`" for u in unused) + "."
                   if unused else "")
    lines += [
        f"| **total** | {total_calls} | | {credited_calls} | "
        f"{_tok(total_actual)} | {_tok(total_credited_actual)} | "
        f"{_tok(total_baseline)} | "
        f"**{_tok(net_saved)}** | {avg_total} |",
        "",
        "All figures are tokens, estimated as bytes/3.7 (tokq's fallback "
        "heuristic), not exact counts.",
        "",
        "\"output\" is what the tool actually printed across every call; "
        "\"credited output\" is just the calls that got a baseline, and is "
        "the only figure charged against it. \"raw equivalent\" "
        "is the size of the naive alternative: the whole file for "
        "`xread`/`structo`, a background run of the equivalent raw "
        "`git`/`rg` command for `gitbrief`/`sgrep`/`codediff` (measured "
        "for length only, never shown to the model), and for `runlite` "
        "the log size it reports itself - exact rather than estimated, "
        "since it buffers the whole log and re-running a build to measure "
        "it would be neither cheap nor deterministic. \"n/a\" means no "
        "raw equivalent "
        "could be derived honestly for that call shape - those calls are "
        "counted but never credited toward savings. A raw command that "
        "ran fine but matched nothing is n/a too, not a 0-byte baseline: "
        "crediting those scored the suite call as pure loss. Other suite "
        "tools have no raw equivalent and log output size only.",
        "",
        "A baseline is only credited when it answers the *same question* "
        "as the call it is compared against - for `sgrep` that means the "
        "raw `rg` carries the same `-C`, `-i`, `-t`, `-g` and every path. "
        "Schema-v1 `sgrep` rows that used `-C` were measured against a "
        "context-free `rg` and are excluded rather than restated, since "
        "the working trees they ran in are gone.",
        "",
        "**Savings is not the only signal.** A tool nobody calls scores "
        "neutral here while being the most expensive thing in the suite: "
        "unused surface area that still has to be maintained, documented "
        "and kept in an agent's head. Read the `calls` and `last used` "
        "columns before the `saved` column." + unused_note,
        "",
        "Auto-generated by the guard hook; raw per-call data in "
        "`.savings/events.jsonl`" + _log_size_note() + ". Regenerate with "
        "`python llm-tools-guard.py --rebuild`.",
    ]
    os.makedirs(os.path.dirname(RECORD_PATH), exist_ok=True)
    with open(RECORD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def record_savings(data: dict) -> None:
    if not SAVINGS_ROOT:
        return  # no known checkout on this host; see _default_savings_root
    tool = data.get("tool_name")
    if tool not in ("Bash", "PowerShell"):
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    # Locate the invocation in the masked string so a tool name quoted inside
    # a commit message isn't logged as a call, and so the separator that ends
    # its arguments is a real one. Offsets are preserved, so the slice still
    # comes from the raw command — the baseline needs the actual pattern.
    masked = mask_literals(command)
    m = SUITE_TOOL_RE.search(masked)
    if not m:
        return
    suite_tool = m.group(1)
    sep = re.search(r"[;\n]|&&|\|\|", masked[m.end():])
    rest = command[m.end():m.end() + sep.start()] if sep else command[m.end():]
    cwd = data.get("cwd") or os.getcwd()
    response_text = _response_text(data.get("tool_response"))
    actual_bytes = len(response_text.encode("utf-8", errors="replace"))
    baseline_bytes = None
    if suite_tool in ("xread", "structo"):
        path = _first_file_arg(rest, cwd)
        if path and os.path.isfile(path):
            try:
                baseline_bytes = os.path.getsize(path)
            except OSError:
                pass
    elif suite_tool == "gitbrief":
        baseline_bytes = _gitbrief_baseline(rest, cwd)
    elif suite_tool == "sgrep":
        baseline_bytes = _sgrep_baseline(rest, cwd)
    elif suite_tool == "codediff":
        baseline_bytes = _codediff_baseline(rest, cwd)
    elif suite_tool == "runlite":
        baseline_bytes = _runlite_baseline(response_text)
    # A raw command that ran but matched nothing is not a 0-byte baseline -
    # there is no honest comparison to make, so it is n/a like any other
    # underivable baseline.
    if baseline_bytes == 0:
        baseline_bytes = None
    event = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        # Schema version. v1 measured sgrep against a context-free `rg`
        # even when the call asked for -C, so v1 -C rows are not
        # creditable; see _event_credited.
        "v": EVENT_SCHEMA,
        "tool": suite_tool,
        "cwd": cwd,
        # The invocation, so a surprising row can be traced back to the call
        # that produced it. Machine-local: .savings/ is gitignored.
        "argv": rest.strip()[:500],
        "actual_bytes": actual_bytes,
        "baseline_bytes": baseline_bytes,
    }
    os.makedirs(SAVINGS_DIR, exist_ok=True)
    with open(EVENTS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    rebuild_aggregate()


def main() -> None:
    if "--rebuild" in sys.argv[1:]:
        if not SAVINGS_ROOT:
            print("no LLM-tools checkout found on this host; set "
                  "LLM_TOOLS_SAVINGS_ROOT or add one to KNOWN_SAVINGS_ROOTS. "
                  f"Looked for: {', '.join(KNOWN_SAVINGS_ROOTS)}",
                  file=sys.stderr)
            sys.exit(1)
        agg = rebuild_aggregate()
        calls = sum(r["count"] for r in agg.values())
        print(f"rebuilt {AGG_PATH} and {RECORD_PATH} "
              f"from {calls} events")
        return
    data = json.load(sys.stdin)
    event = data.get("hook_event_name", "PreToolUse")
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    if event == "PostToolUse":
        if tool == "Read":
            nudge_read(data)
        record_savings(data)
        return
    if tool in ("Bash", "PowerShell"):
        check_shell(tool, tool_input.get("command") or "")
    elif tool == "Read":
        check_read(tool_input)
    elif tool == "Grep":
        check_grep(tool_input)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # fail open: never let a guard bug block real work
