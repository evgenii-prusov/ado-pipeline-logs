#!/usr/bin/env bash
set -euo pipefail

SKILL_NAME="ado-pipeline-logs"
DEST="$HOME/.claude/skills/$SKILL_NAME"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/skills/$SKILL_NAME"

if [ ! -d "$SRC" ]; then
    echo "Error: skill source not found at $SRC"
    echo "Run this script from the repo root: bash install.sh"
    exit 1
fi

echo "Installing $SKILL_NAME skill..."

mkdir -p "$DEST/scripts"
cp "$SRC/SKILL.md" "$DEST/SKILL.md"
cp "$SRC/scripts/ado_pipeline_logs.py" "$DEST/scripts/ado_pipeline_logs.py"

echo "Installed to $DEST"
echo ""
echo "Next steps:"
echo "  1. Ensure you have 'az login' done or ADO_PAT env var set"
echo "  2. Add this to your .claude/settings.local.json permissions.allow:"
echo "     \"Bash(python3 $DEST/scripts/ado_pipeline_logs.py:*)\""
echo "  3. Restart Claude Code"
