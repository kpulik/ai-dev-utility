#!/usr/bin/env bash
# AI Dev Utility - Red-team security scan
# Usage: ./scripts/redteam.sh [config-file]

set -euo pipefail

CONFIG="${1:-configs/promptfoo/redteam-config.yaml}"

if ! command -v promptfoo &>/dev/null; then
    echo "PromptFoo not found. Install: npm install -g promptfoo"
    exit 1
fi

if [[ ! -f "$CONFIG" ]]; then
    echo "Config not found: $CONFIG"
    exit 1
fi

echo "Starting red-team security scan..."
echo "Config: $CONFIG"
echo ""

promptfoo redteam eval -c "$CONFIG"

echo ""
echo "View results: promptfoo view"
