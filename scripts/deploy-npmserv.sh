#!/bin/sh
# Deploy the committed state of this repo to npmserv:/opt/des_stack/LLM-tools,
# plus the guard hook to the remote ~/.claude/hooks/.
# Runs from Git Bash: scripts/deploy-npmserv.sh
# Override the target with NPMSERV_HOST (default root@192.168.1.120) and the
# hook source with GUARD_HOOK (default ~/.claude/hooks/llm-tools-guard.py).
set -e

HOST="${NPMSERV_HOST:-root@192.168.1.120}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARBALL=/tmp/llm-tools.tar.gz
HOOK="${GUARD_HOOK:-$HOME/.claude/hooks/llm-tools-guard.py}"
REMOTE_HOOK=.claude/hooks/llm-tools-guard.py

git -C "$REPO" archive --format=tar.gz -o "$TARBALL" HEAD
scp -o BatchMode=yes "$TARBALL" "$HOST:/tmp/llm-tools.tar.gz"
ssh -o BatchMode=yes "$HOST" update-llm-tools
rm -f "$TARBALL"

# The guard hook is not in the repo (it lives in ~/.claude/), so nothing in
# the tarball carries it and it used to drift — the server ran a copy three
# weeks and one silent bypass behind. Ship it here, gated on its own tests.
#
# It deploys *verbatim*: SAVINGS_ROOT resolves per host at import by picking
# the first entry of KNOWN_SAVINGS_ROOTS that exists on disk. If you add a
# new host, add its checkout path there rather than patching the copy on the
# server — hand-patching is exactly what caused the drift.
if [ ! -f "$HOOK" ]; then
    echo "deploy-npmserv: no guard hook at $HOOK (set GUARD_HOOK)" >&2
    exit 1
fi

python "$REPO/scripts/test-guard-hook.py" --hook "$HOOK" >/tmp/guard-tests.txt 2>&1 || {
    echo "deploy-npmserv: guard hook tests FAILED - not deploying the hook" >&2
    tail -20 /tmp/guard-tests.txt >&2
    exit 1
}

ssh -o BatchMode=yes "$HOST" \
    "test -f $REMOTE_HOOK && cp -p $REMOTE_HOOK $REMOTE_HOOK.bak-\$(date +%Y%m%d-%H%M%S) || true"
scp -o BatchMode=yes "$HOOK" "$HOST:$REMOTE_HOOK"
ssh -o BatchMode=yes "$HOST" "rm -rf .claude/hooks/__pycache__"

# Verify the bytes that actually landed, and that the hook resolves a real
# checkout on that host - a wrong SAVINGS_ROOT disables savings logging
# silently, since the hook fails open.
scp -o BatchMode=yes "$REPO/scripts/test-guard-hook.py" "$HOST:/tmp/test-guard-hook.py"
ssh -o BatchMode=yes "$HOST" "python3 /tmp/test-guard-hook.py --hook \$HOME/$REMOTE_HOOK | tail -1; \
    rm -f /tmp/test-guard-hook.py; \
    python3 \$HOME/$REMOTE_HOOK --rebuild"

echo "deploy-npmserv: OK - repo and guard hook deployed to $HOST"
