#!/usr/bin/env bash
# AI Forge - Update all tools
# Usage: ./scripts/update-all.sh

set -euo pipefail

echo "Updating AI Forge tools..."

if [[ -d ".cache/agency-agents" ]]; then
    echo "[1/3] Updating Agency agents..."
    cd .cache/agency-agents && git pull --quiet && cd ../..
fi

if [[ -d ".cache/impeccable" ]]; then
    echo "[2/3] Updating Impeccable..."
    cd .cache/impeccable && git pull --quiet && cd ../..
fi

echo "[3/3] Updating PromptFoo..."
npm update -g promptfoo 2>/dev/null || echo "  Skipped (not installed globally)"

if pip3 show openviking &>/dev/null 2>&1; then
    echo "[bonus] Updating OpenViking..."
    pip3 install openviking --upgrade --quiet 2>/dev/null || true
fi

echo ""
echo "Done!"
