#!/usr/bin/env bash
# AI Forge - Run prompt evaluations
# Usage: ./scripts/test-prompts.sh [config-file]

set -euo pipefail

CONFIG="${1:-configs/promptfoo/eval-config.yaml}"

if ! command -v promptfoo &>/dev/null; then
    echo "PromptFoo not found. Install: npm install -g promptfoo"
    exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "Config not found: $CONFIG"
    exit 1
fi

echo "Running prompt evaluation..."
echo "Config: $CONFIG"
echo ""

promptfoo eval -c "$CONFIG" --no-cache

echo ""
echo "View results: promptfoo view"
