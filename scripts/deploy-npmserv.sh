#!/bin/sh
# Deploy the committed state of this repo to npmserv:/opt/des_stack/LLM-tools.
# Runs from Git Bash: scripts/deploy-npmserv.sh
# Override the target with NPMSERV_HOST (default root@192.168.1.120).
set -e

HOST="${NPMSERV_HOST:-root@192.168.1.120}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
TARBALL=/tmp/llm-tools.tar.gz

git -C "$REPO" archive --format=tar.gz -o "$TARBALL" HEAD
scp -o BatchMode=yes "$TARBALL" "$HOST:/tmp/llm-tools.tar.gz"
ssh -o BatchMode=yes "$HOST" update-llm-tools
rm -f "$TARBALL"
