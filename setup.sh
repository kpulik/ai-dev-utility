#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# AI Dev Utility - Unified AI Developer Toolkit Setup
# 4 tools, local-first, no required API costs when using Ollama
# The Agency | Impeccable | PromptFoo | MiniFish
# ============================================================================

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/.setup.log"
: > "$LOG_FILE"

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err() { echo -e "${RED}[x]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }
section() { echo -e "\n${BOLD}--- $1 ---${NC}\n"; }

# Run a command silently while showing an animated spinner.
# Usage: run_with_spinner "Label text" cmd arg1 arg2 ...
run_with_spinner() {
    local msg="$1"
    shift
    "$@" >>"$LOG_FILE" 2>&1 &
    local pid=$!
    local i=0
    local sp='|/-\'
    local rc=0
    tput civis 2>/dev/null || true
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${CYAN}[${sp:$((i % 4)):1}]${NC} %s..." "$msg"
        sleep 0.08
        i=$((i + 1))
    done
    wait "$pid" || rc=$?
    tput cnorm 2>/dev/null || true
    if [[ $rc -eq 0 ]]; then
        printf "\r  ${GREEN}[+]${NC} %-60s\n" "$msg"
    else
        printf "\r  ${RED}[x]${NC} %-60s\n" "$msg (failed - see .setup.log)"
    fi
    return $rc
}

echo -e "${BOLD}"
echo "    _    ___   _____                    "
echo "   / \  |_ _| |  ___|__  _ __ __ _  ___ "
echo "  / _ \  | |  | |_ / _ \| '__/ _\` |/ _ \\"
echo " / ___ \ | |  |  _| (_) | | | (_| |  __/"
echo "/_/   \_\___| |_|  \___/|_|  \__, |\___|"
echo "                              |___/      "
echo -e "${NC}"
echo "All-local AI developer toolkit for Claude Code"
echo ""

# ============================================================================
# Check prerequisites
# ============================================================================
section "Checking prerequisites"

MISSING=()
command -v git &>/dev/null || MISSING+=("git")
command -v node &>/dev/null || MISSING+=("node (v18+)")
command -v npm &>/dev/null || MISSING+=("npm")
command -v python3 &>/dev/null || MISSING+=("python3 (3.10+)")

if [[ ${#MISSING[@]} -gt 0 ]]; then
    err "Missing required tools: ${MISSING[*]}"
    echo "Install them first, then re-run this script."
    exit 1
fi

NODE_VER=$(node -v | sed 's/v//' | cut -d. -f1)
if [[ "$NODE_VER" -lt 18 ]]; then
    err "Node.js 18+ required (found v$NODE_VER)"
    exit 1
fi

log "Prerequisites OK"

# Manifest tracks what this run installs so uninstall.sh knows what to remove
MANIFEST_FILE="$HOME/.claude/.ai-dev-utility-manifest"
mkdir -p "$HOME/.claude"
: > "$MANIFEST_FILE"

# ============================================================================
# Parse arguments
# ============================================================================
INSTALL_OLLAMA=false
TARGET_PROJECT=""

print_usage() {
    echo "Usage: ./setup.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  (no flags)       Install core: Agency + Impeccable + PromptFoo + MiniFish"
    echo "  --ollama         Also install Ollama and pull a default model"
    echo "  --project DIR    Apply AI Dev Utility configs to an existing project"
    echo "  --help           Show this help"
    echo ""
    echo "Examples:"
    echo "  ./setup.sh                       # Core tools for Claude Code"
    echo "  ./setup.sh --ollama              # Core tools + local LLM"
    echo "  ./setup.sh --project ~/my-app    # Apply to a project"
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --ollama) INSTALL_OLLAMA=true; shift ;;
        --project) TARGET_PROJECT="$2"; shift 2 ;;
        --help) print_usage; exit 0 ;;
        *) err "Unknown option: $1"; print_usage; exit 1 ;;
    esac
done

# ============================================================================
# 1. The Agency - Agent Personas
# ============================================================================
section "1/4 The Agency (Agent Personas)"

AGENCY_DIR="$SCRIPT_DIR/.cache/agency-agents"
if [[ -d "$AGENCY_DIR" ]]; then
    run_with_spinner "Updating Agency agents" git -C "$AGENCY_DIR" pull --quiet || true
else
    run_with_spinner "Cloning Agency agents" git clone --quiet --depth 1 https://github.com/msitarzewski/agency-agents.git "$AGENCY_DIR"
fi

# Install for Claude Code
CLAUDE_AGENTS_DIR="$HOME/.claude/agents"
mkdir -p "$CLAUDE_AGENTS_DIR"

# Copy all agents
if [[ -d "$AGENCY_DIR/agents" ]]; then
    AGENT_COUNT=$(find "$AGENCY_DIR/agents" -name "*.md" | wc -l | tr -d ' ')
    find "$AGENCY_DIR/agents" -name "*.md" -exec cp {} "$CLAUDE_AGENTS_DIR/" \; 2>/dev/null || true
    echo "agents" >> "$MANIFEST_FILE"
    log "Installed $AGENT_COUNT agent personas into ~/.claude/agents/"
else
    warn "Agent files not found in expected location, copying all .md files"
    find "$AGENCY_DIR" -maxdepth 3 -name "*.md" ! -name "README.md" ! -name "LICENSE*" \
        -exec cp {} "$CLAUDE_AGENTS_DIR/" \; 2>/dev/null || true
    echo "agents" >> "$MANIFEST_FILE"
    log "Installed agents for Claude Code"
fi

# ============================================================================
# 2. Impeccable - Frontend Design Commands
# ============================================================================
section "2/4 Impeccable (Design Commands)"

IMPECCABLE_DIR="$SCRIPT_DIR/.cache/impeccable"
if [[ -d "$IMPECCABLE_DIR" ]]; then
    run_with_spinner "Updating Impeccable" git -C "$IMPECCABLE_DIR" pull --quiet || true
else
    run_with_spinner "Cloning Impeccable" git clone --quiet --depth 1 https://github.com/pbakaus/impeccable.git "$IMPECCABLE_DIR"
fi

# Install for Claude Code
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$CLAUDE_SKILLS_DIR"

# Try the official install paths
INSTALLED_IMPECCABLE=false
for dir in "skills" "claude-code" "src"; do
    if [[ -d "$IMPECCABLE_DIR/$dir" ]]; then
        cp -r "$IMPECCABLE_DIR/$dir/"* "$CLAUDE_SKILLS_DIR/" 2>/dev/null || true
        INSTALLED_IMPECCABLE=true
        break
    fi
done

if ! $INSTALLED_IMPECCABLE; then
    find "$IMPECCABLE_DIR" -maxdepth 2 -name "*.md" ! -name "README.md" ! -name "LICENSE*" ! -name "CHANGELOG*" \
        -exec cp {} "$CLAUDE_SKILLS_DIR/" \; 2>/dev/null || true
fi

echo "skills" >> "$MANIFEST_FILE"
log "Installed Impeccable design skills into ~/.claude/skills/"

# ============================================================================
# Global Claude Code rules (~/.claude/CLAUDE.md)
# ============================================================================
section "Global Claude Code rules"

GLOBAL_CLAUDE="$HOME/.claude/CLAUDE.md"
INSTALL_GLOBAL_CLAUDE=false

if [[ -f "$GLOBAL_CLAUDE" ]]; then
    info "~/.claude/CLAUDE.md already exists."
    read -r -p "  Overwrite with AI Dev Utility global rules (agent personas + design)? [y/N]: " OW_CHOICE
    if [[ "$OW_CHOICE" == "y" || "$OW_CHOICE" == "Y" ]]; then
        INSTALL_GLOBAL_CLAUDE=true
    else
        info "Skipped. Keeping existing ~/.claude/CLAUDE.md"
    fi
else
    read -r -p "  Install global Claude Code rules into ~/.claude/CLAUDE.md? [Y/n]: " GC_CHOICE
    if [[ "$GC_CHOICE" != "n" && "$GC_CHOICE" != "N" ]]; then
        INSTALL_GLOBAL_CLAUDE=true
    else
        info "Skipped global rules install."
    fi
fi

if $INSTALL_GLOBAL_CLAUDE; then
    mkdir -p "$HOME/.claude"
    if [[ -f "$GLOBAL_CLAUDE" ]]; then
        cp "$GLOBAL_CLAUDE" "${GLOBAL_CLAUDE}.bak"
        echo "global_claude_bak" >> "$MANIFEST_FILE"
        info "Previous ~/.claude/CLAUDE.md backed up to ~/.claude/CLAUDE.md.bak"
    fi
    cp "$SCRIPT_DIR/CLAUDE.md" "$GLOBAL_CLAUDE"
    echo "global_claude" >> "$MANIFEST_FILE"
    log "Global rules written to ~/.claude/CLAUDE.md"
fi

# ============================================================================
# 3. PromptFoo - Prompt Testing & Red-Teaming
# ============================================================================
section "3/4 PromptFoo (Prompt Testing)"

if command -v promptfoo &>/dev/null; then
    PVER=$(promptfoo --version 2>/dev/null || echo "installed")
    log "PromptFoo already installed ($PVER)"
else
    run_with_spinner "Installing PromptFoo" npm install -g promptfoo@latest
    echo "promptfoo" >> "$MANIFEST_FILE"
fi

log "Configs ready in configs/promptfoo/"

# ============================================================================
# 4. MiniFish - Local Prediction Engine
# ============================================================================
section "4/4 MiniFish (Local Prediction Engine)"

if [[ -f "$SCRIPT_DIR/minifish/minifish.py" ]]; then
    chmod +x "$SCRIPT_DIR/minifish/minifish.py"
    log "MiniFish ready at minifish/minifish.py"
    info "Requires Ollama: brew install ollama && ollama pull llama3.2"
else
    err "minifish.py not found (should be in minifish/ directory)"
fi

# ============================================================================
# Ollama setup (optional)
# ============================================================================
if $INSTALL_OLLAMA; then
    section "Setting up Ollama (local LLM)"

    if command -v ollama &>/dev/null; then
        log "Ollama already installed"
    else
        if [[ "$OSTYPE" == "darwin"* ]]; then
            if command -v brew &>/dev/null; then
                run_with_spinner "Installing Ollama via Homebrew" brew install ollama
            else
                warn "Homebrew not found. Install Ollama manually: https://ollama.ai"
            fi
        else
            run_with_spinner "Installing Ollama" sh -c 'curl -fsSL https://ollama.ai/install.sh | sh'
        fi
    fi

    if command -v ollama &>/dev/null; then
        # Check if Ollama is running, start if not
        if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
            info "Starting Ollama..."
            ollama serve &>/dev/null &
            # Wait for Ollama to be ready (up to 20s)
            for i in $(seq 1 20); do
                if curl -s http://localhost:11434/api/tags &>/dev/null; then
                    log "Ollama is ready"
                    break
                fi
                sleep 1
            done
        fi

        # Model selection menu
        echo ""
        echo -e "${BOLD}Choose a model to pull:${NC}"
        echo "  1) llama3.2:3b      Fast, lightweight   (~2GB)  good for quick tasks"
        echo "  2) llama3.1:8b      Balanced            (~5GB)  solid all-rounder"
        echo "  3) qwen2.5:14b      Smarter, still fast (~9GB)  best quality on M4 Pro"
        echo "  4) mistral:7b       Alternative 7B      (~4GB)  strong reasoning"
        echo "  5) Skip             Don't pull any model"
        echo ""
        read -r -p "Enter choice [1-5]: " MODEL_CHOICE

        case "$MODEL_CHOICE" in
            1) PULL_MODEL="llama3.2:3b" ;;
            2) PULL_MODEL="llama3.1:8b" ;;
            3) PULL_MODEL="qwen2.5:14b" ;;
            4) PULL_MODEL="mistral:7b" ;;
            5) PULL_MODEL="" ;;
            *) warn "Invalid choice, skipping model pull"; PULL_MODEL="" ;;
        esac

        if [[ -n "$PULL_MODEL" ]]; then
            if ollama list 2>/dev/null | grep -q "${PULL_MODEL%%:*}"; then
                log "$PULL_MODEL already available"
            else
                info "Pulling $PULL_MODEL (this may take a few minutes)..."
                ollama pull "$PULL_MODEL"
                log "$PULL_MODEL ready"
            fi
        else
            info "Skipping model pull. Pull one later with: ollama pull <model>"
        fi

    fi
fi

# ============================================================================
# Apply to target project if specified
# ============================================================================
if [[ -n "$TARGET_PROJECT" ]]; then
    section "Applying to project: $TARGET_PROJECT"
    bash "$SCRIPT_DIR/scripts/new-project.sh" "$TARGET_PROJECT"
fi

# ============================================================================
# Summary
# ============================================================================
section "Setup Complete!"

echo -e "${BOLD}Installed:${NC}"
echo -e "  ${GREEN}[+]${NC} The Agency     180 agent personas in ~/.claude/agents/"
echo -e "  ${GREEN}[+]${NC} Impeccable     Design skills in ~/.claude/skills/"
if $INSTALL_GLOBAL_CLAUDE; then
    echo -e "  ${GREEN}[+]${NC} Global rules   Agent + design rules in ~/.claude/CLAUDE.md"
else
    echo -e "  ${CYAN}[-]${NC} Global rules   Skipped (run setup.sh again to install)"
fi
echo -e "  ${GREEN}[+]${NC} PromptFoo      Prompt testing + security scanning"
echo -e "  ${GREEN}[+]${NC} MiniFish       Local multi-agent predictions"
if $INSTALL_OLLAMA && command -v ollama &>/dev/null; then
    if [[ -n "${PULL_MODEL:-}" ]]; then
        echo -e "  ${GREEN}[+]${NC} Ollama         Local LLM runtime + $PULL_MODEL"
    else
        echo -e "  ${GREEN}[+]${NC} Ollama         Local LLM runtime (no model pulled)"
    fi
else
    echo -e "  ${CYAN}[i]${NC} Ollama         Install separately: brew install ollama"
fi

echo ""
echo -e "${BOLD}Quick start:${NC}"
echo "  Open any project in Claude Code and the agents + design rules are active."
echo ""
echo -e "${BOLD}Commands:${NC}"
echo "  Run a prediction:       python minifish/minifish.py \"your topic\""
echo "  Test prompts:           ./scripts/test-prompts.sh"
echo "  Security red-team:      ./scripts/redteam.sh"
echo "  Apply to a project:     ./scripts/new-project.sh ~/my-app"
echo "  Update everything:      ./scripts/update-all.sh"
echo "  Uninstall:              ./scripts/uninstall.sh"
echo ""
echo -e "${BOLD}For MiniFish + PromptFoo local evals, install Ollama:${NC}"
echo "  brew install ollama"
echo "  ollama serve"
echo "  ollama pull llama3.2"
echo ""
echo -e "Full docs: ${CYAN}docs/USAGE.md${NC}"
echo ""
