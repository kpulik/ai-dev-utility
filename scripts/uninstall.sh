#!/usr/bin/env bash
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[x]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }

MANIFEST_FILE="$HOME/.claude/.ai-dev-utility-manifest"

# ============================================================================
# Read manifest
# ============================================================================
HAS_AGENTS=false
HAS_SKILLS=false
HAS_GLOBAL_CLAUDE=false
HAS_GLOBAL_CLAUDE_BAK=false
HAS_PROMPTFOO=false

if [[ -f "$MANIFEST_FILE" ]]; then
    while IFS= read -r line; do
        case "$line" in
            agents)            HAS_AGENTS=true ;;
            skills)            HAS_SKILLS=true ;;
            global_claude)     HAS_GLOBAL_CLAUDE=true ;;
            global_claude_bak) HAS_GLOBAL_CLAUDE_BAK=true ;;
            promptfoo)         HAS_PROMPTFOO=true ;;
        esac
    done < "$MANIFEST_FILE"
else
    warn "No AI Dev Utility manifest found (~/.claude/.ai-dev-utility-manifest)."
    warn "Either AI Dev Utility was never installed, or setup was run before tracking was added."
    echo ""
    echo "You can still remove components manually:"
    echo "  Agents:        rm -rf ~/.claude/agents/"
    echo "  Skills:        rm -rf ~/.claude/skills/"
    echo "  Global rules:  rm ~/.claude/CLAUDE.md"
    echo "  PromptFoo:     npm uninstall -g promptfoo"
    exit 0
fi

# ============================================================================
# Show what's installed
# ============================================================================
echo -e "\n${BOLD}AI Dev Utility - Uninstall${NC}\n"
echo -e "${BOLD}Installed components:${NC}"

[[ "$HAS_AGENTS" == true ]]        && echo -e "  ${GREEN}[+]${NC} Agent personas     (~/.claude/agents/)" \
                                   || echo -e "  ${CYAN}[-]${NC} Agent personas     not installed"
[[ "$HAS_SKILLS" == true ]]        && echo -e "  ${GREEN}[+]${NC} Design skills      (~/.claude/skills/)" \
                                   || echo -e "  ${CYAN}[-]${NC} Design skills      not installed"
[[ "$HAS_GLOBAL_CLAUDE" == true ]] && echo -e "  ${GREEN}[+]${NC} Global CLAUDE.md   (~/.claude/CLAUDE.md)" \
                                   || echo -e "  ${CYAN}[-]${NC} Global CLAUDE.md   not installed"
[[ "$HAS_GLOBAL_CLAUDE_BAK" == true ]] && echo -e "  ${CYAN}[i]${NC} Backup available   (~/.claude/CLAUDE.md.bak)"
[[ "$HAS_PROMPTFOO" == true ]]     && echo -e "  ${GREEN}[+]${NC} PromptFoo          (global npm package)" \
                                   || echo -e "  ${CYAN}[-]${NC} PromptFoo          not installed by AI Dev Utility"

echo ""
echo -e "${BOLD}What would you like to remove?${NC}"
echo "  1) Everything installed by AI Dev Utility"
echo "  2) Choose individually"
echo "  q) Quit"
echo ""
read -r -p "Enter choice [1/2/q]: " CHOICE

case "$CHOICE" in
    1) REMOVE_ALL=true ;;
    2) REMOVE_ALL=false ;;
    q|Q) echo "Cancelled."; exit 0 ;;
    *) err "Invalid choice."; exit 1 ;;
esac

# Helper: ask yes/no for individual removal
ask_remove() {
    local label="$1"
    read -r -p "  Remove $label? [y/N]: " R
    [[ "$R" == "y" || "$R" == "Y" ]]
}

# ============================================================================
# Removal functions
# ============================================================================
remove_agents() {
    if [[ -d "$HOME/.claude/agents" ]]; then
        warn "This removes ALL files in ~/.claude/agents/ — including any you added manually."
        read -r -p "  Confirm removal? [y/N]: " CONF
        if [[ "$CONF" == "y" || "$CONF" == "Y" ]]; then
            rm -rf "$HOME/.claude/agents"
            log "Removed ~/.claude/agents/"
        else
            info "Skipped agent personas."
        fi
    else
        info "~/.claude/agents/ not found, skipping."
    fi
}

remove_skills() {
    if [[ -d "$HOME/.claude/skills" ]]; then
        warn "This removes ALL files in ~/.claude/skills/ — including any you added manually."
        read -r -p "  Confirm removal? [y/N]: " CONF
        if [[ "$CONF" == "y" || "$CONF" == "Y" ]]; then
            rm -rf "$HOME/.claude/skills"
            log "Removed ~/.claude/skills/"
        else
            info "Skipped design skills."
        fi
    else
        info "~/.claude/skills/ not found, skipping."
    fi
}

remove_global_claude() {
    if [[ -f "$HOME/.claude/CLAUDE.md" ]]; then
        if [[ "$HAS_GLOBAL_CLAUDE_BAK" == true && -f "$HOME/.claude/CLAUDE.md.bak" ]]; then
            echo ""
            echo "  A backup of your previous ~/.claude/CLAUDE.md exists."
            echo "    r) Restore backup"
            echo "    d) Delete (no restore)"
            echo "    s) Skip"
            read -r -p "  Choice [r/d/s]: " BAK_CHOICE
            case "$BAK_CHOICE" in
                r|R)
                    mv "$HOME/.claude/CLAUDE.md.bak" "$HOME/.claude/CLAUDE.md"
                    log "Restored ~/.claude/CLAUDE.md from backup."
                    ;;
                d|D)
                    rm "$HOME/.claude/CLAUDE.md"
                    rm -f "$HOME/.claude/CLAUDE.md.bak"
                    log "Removed ~/.claude/CLAUDE.md"
                    ;;
                *)
                    info "Skipped global CLAUDE.md."
                    ;;
            esac
        else
            read -r -p "  Delete ~/.claude/CLAUDE.md? [y/N]: " CONF
            if [[ "$CONF" == "y" || "$CONF" == "Y" ]]; then
                rm "$HOME/.claude/CLAUDE.md"
                log "Removed ~/.claude/CLAUDE.md"
            else
                info "Skipped global CLAUDE.md."
            fi
        fi
    else
        info "~/.claude/CLAUDE.md not found, skipping."
    fi
}

remove_promptfoo() {
    if command -v promptfoo &>/dev/null; then
        if npm uninstall -g promptfoo 2>/dev/null; then
            log "Removed PromptFoo"
        else
            warn "npm uninstall failed. Try manually: npm uninstall -g promptfoo"
        fi
    else
        info "PromptFoo not found in PATH, skipping."
    fi
}

# ============================================================================
# Execute removals
# ============================================================================
echo ""

if $REMOVE_ALL; then
    [[ "$HAS_AGENTS" == true ]]        && remove_agents
    [[ "$HAS_SKILLS" == true ]]        && remove_skills
    [[ "$HAS_GLOBAL_CLAUDE" == true ]] && remove_global_claude
    [[ "$HAS_PROMPTFOO" == true ]]     && remove_promptfoo
else
    [[ "$HAS_AGENTS" == true ]]        && ask_remove "agent personas (~/.claude/agents/)"       && remove_agents
    [[ "$HAS_SKILLS" == true ]]        && ask_remove "design skills (~/.claude/skills/)"        && remove_skills
    [[ "$HAS_GLOBAL_CLAUDE" == true ]] && ask_remove "global CLAUDE.md (~/.claude/CLAUDE.md)"  && remove_global_claude
    [[ "$HAS_PROMPTFOO" == true ]]     && ask_remove "PromptFoo (npm package)"                  && remove_promptfoo
fi

# Clean up manifest
rm -f "$MANIFEST_FILE"
log "Manifest removed."

echo ""
echo -e "${BOLD}Done.${NC} Re-run ./setup.sh to reinstall."
echo ""
