#!/usr/bin/env bash
# AI Forge - Initialize AI Forge configs in a project
# Usage: ./scripts/new-project.sh /path/to/your/project

set -euo pipefail

FORGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
    echo "Usage: ./scripts/new-project.sh /path/to/your/project"
    echo ""
    echo "Copies AI Forge configs into your project:"
    echo "  CLAUDE.md              Claude Code project instructions"
    echo "  configs/promptfoo/     Prompt testing configs"
    echo "  scripts/               Test and red-team scripts"
    exit 1
fi

if [[ ! -d "$TARGET" ]]; then
    echo "Creating: $TARGET"
    mkdir -p "$TARGET"
fi

echo "Initializing AI Forge in: $TARGET"

# CLAUDE.md
if [[ -f "$TARGET/CLAUDE.md" ]]; then
    cp "$TARGET/CLAUDE.md" "$TARGET/CLAUDE.md.bak"
    echo "  Backed up existing CLAUDE.md"
fi
cp "$FORGE_DIR/CLAUDE.md" "$TARGET/CLAUDE.md"
echo "  Created CLAUDE.md"

# PromptFoo configs
mkdir -p "$TARGET/configs/promptfoo"
cp "$FORGE_DIR/configs/promptfoo/"*.yaml "$TARGET/configs/promptfoo/" 2>/dev/null || true
echo "  Created configs/promptfoo/"

# Scripts
mkdir -p "$TARGET/scripts"
for script in test-prompts.sh redteam.sh; do
    if [[ -f "$FORGE_DIR/scripts/$script" ]]; then
        cp "$FORGE_DIR/scripts/$script" "$TARGET/scripts/"
        chmod +x "$TARGET/scripts/$script"
    fi
done
echo "  Created scripts/"

echo ""
echo "Done! Next steps:"
echo "  1. Edit CLAUDE.md with your project description and design direction"
echo "  2. Edit configs/promptfoo/eval-config.yaml with your prompts"
echo "  3. Start coding in Claude Code"
