#!/bin/sh
# Install the optional guard hook: a PreToolUse/PostToolUse hook that nudges
# (and for a few raw git/grep/cat shapes, denies) Claude Code toward the
# suite's tools instead of built-ins, and logs a savings_record.md in this
# checkout. Entirely optional — the tools work standalone without it.
#
# Usage: sh scripts/install-hook.sh
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$REPO_DIR/hooks/llm-tools-guard.py"
DEST_DIR="$HOME/.claude/hooks"
DEST="$DEST_DIR/llm-tools-guard.py"
SETTINGS="$HOME/.claude/settings.json"

if [ ! -f "$SRC" ]; then
    echo "install-hook: $SRC not found" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
if [ -f "$DEST" ]; then
    cp -p "$DEST" "$DEST.bak-$(date +%Y%m%d-%H%M%S)"
    echo "install-hook: backed up existing $DEST"
fi
cp "$SRC" "$DEST"
echo "install-hook: copied hook to $DEST"

echo
echo "Next steps:"
echo "1. Register the hook in $SETTINGS (create if absent):"
cat <<'JSON'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|PowerShell|Read|Grep",
        "hooks": [
          { "type": "command",
            "command": "python \"HOME/.claude/hooks/llm-tools-guard.py\"",
            "timeout": 10 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Read|Grep|Bash|PowerShell",
        "hooks": [
          { "type": "command",
            "command": "python \"HOME/.claude/hooks/llm-tools-guard.py\"",
            "timeout": 10 }
        ]
      }
    ]
  }
}
JSON
echo "   (replace HOME with your actual home directory; merge with any"
echo "   existing \"hooks\" key rather than overwriting the file)"
echo
echo "2. Savings tracking (the per-tool $REPO_DIR/savings_record.md table)"
echo "   auto-detects this checkout only if its path matches a hard-coded"
echo "   entry in KNOWN_SAVINGS_ROOTS inside the hook. On a fresh clone it"
echo "   usually won't, so set this instead (in your shell profile):"
echo
echo "   export LLM_TOOLS_SAVINGS_ROOT=\"$REPO_DIR\""
echo
echo "   Without it the hook still enforces tool preference; it just skips"
echo "   savings logging rather than guessing a path (fail-open by design)."
