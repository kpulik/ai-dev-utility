# AI Dev Utility

**Four open-source AI developer tools, unified into one setup script and one local dashboard. Local-first, with no required API costs when using Ollama.**

AI Dev Utility combines [The Agency](https://github.com/msitarzewski/agency-agents), [Impeccable](https://github.com/pbakaus/impeccable), [PromptFoo](https://github.com/promptfoo/promptfoo), and MiniFish (a lightweight local version of [MiroFish](https://github.com/666ghj/MiroFish)) into a single `setup.sh` that installs Claude Code personas and design rules, sets up PromptFoo configs, and provides a local dashboard for MiniFish and PromptFoo evals. Setup time depends on downloads.

MiniFish runs locally on Ollama. PromptFoo configs default to Ollama but can target cloud providers if you choose. The Agency and Impeccable are Claude Code instruction files (no model runtime). Provider fees apply only if you use cloud APIs.

## Quick start

```bash
git clone https://github.com/kpulik/ai-dev-utility.git
cd ai-dev-utility
./setup.sh          # installs all 4 tools (may take a few minutes)
python forge.py     # launches the web dashboard
# Open http://localhost:8000
```

Make sure Ollama is running first:

```bash
brew install ollama
ollama serve
ollama pull llama3.2      # or any model you prefer
```

To also install Ollama and pull a local model:

```bash
./setup.sh --ollama
```

## Prerequisites

- **Node.js 18+** and npm
- **Python 3.10+**
- **Git**
- **Claude Code** (optional; needed for Agency and Impeccable integration)
- **Ollama** (required for MiniFish and local PromptFoo evals)

## How each tool works

### Always on (passive) - The Agency + Impeccable

These install files globally into `~/.claude/agents/` and `~/.claude/skills/`. Once set up, they're active in every Claude Code session on your Mac, across every project. There's nothing to run. Claude Code automatically reads the agent persona files and applies the design rules.

They do not run a local model by themselves; they are instruction packs consumed by Claude Code.

`setup.sh` also offers to write agent and design rules into `~/.claude/CLAUDE.md` — Claude Code's global instruction file. When installed there, the rules apply to every project on your machine automatically, with no per-project setup required.

### Interactive - MiniFish

This is the main thing you actually run in the dashboard. Open the MiniFish tab, type a topic or paste an article, and watch a panel of agents debate it in real time (defaults to 5). The moderator synthesizes a prediction report at the end. All runs locally via Ollama.

### On demand - PromptFoo

Only relevant if you're building apps that make LLM calls. You write YAML test configs defining your prompts and expected behaviors, then run evals to catch regressions or red-team scans to find security vulnerabilities. The PromptFoo tab in the dashboard lets you edit configs and run evals; red-team scans run via the CLI script. PromptFoo itself is free, but cloud providers charge for their APIs if you use them.

| Tool | Mode | Cost |
| --- | --- | --- |
| **The Agency** | Always on in Claude Code globally | Free |
| **Impeccable** | Always on in Claude Code globally | Free |
| **MiniFish** | Interactive: run in this dashboard | Free tool; local model compute only |
| **PromptFoo** | On demand: test LLM prompts in your apps | Free tool; provider fees if you use cloud APIs |

## The web dashboard (forge.py)

`forge.py` is the primary interface for AI Dev Utility. It's a single-file Python web server with no dependencies beyond the standard library. Run it and open `http://localhost:8000`.

**Dashboard tabs:**

- **Dashboard** - Status overview (Ollama, models, agents, PromptFoo) and tool descriptions
- **MiniFish** - Run a prediction: pick a topic, model, and agents; watch the debate stream in real time (defaults to 5 agents)
- **History** - Browse saved prediction reports, view in modal, export as Markdown
- **PromptFoo** - Edit config files, run evals, view structured pass/fail results (red-team via CLI)
- **Configure** - All reference and config in one place, with inner tabs:
  - **Agents** - Browse and search all installed Agency personas (count depends on upstream; typically around 180)
  - **Design** - Reference grid of all 17 Impeccable commands; click to copy
  - **Personas** - Edit MiniFish agent personas (name, emoji, color, system prompt)
  - **Settings** - Configure Ollama URL, default model, default agent count and rounds

## Usage

### Agent personas (automatic)

Once installed, Claude Code has access to all installed agents via `~/.claude/agents/` (count depends on upstream; typically around 180). When you also install the global `~/.claude/CLAUDE.md`, Claude Code knows how and when to use each persona - no per-project setup needed.

### MiniFish predictions (via GUI)

Open the MiniFish tab, type a topic or paste an article, select your agents, click Run. The debate streams in as it happens.

### MiniFish predictions (CLI)

```bash
# Quick prediction
python minifish/minifish.py "Will AI replace frontend developers by 2028?"

# Analyze a news article
python minifish/minifish.py --file article.txt

# More thorough (7 agents, 3 rounds)
python minifish/minifish.py --agents 7 --rounds 3 "Your topic"

# Interactive mode
python minifish/minifish.py --interactive
```

### Prompt testing (via GUI)

Open the PromptFoo tab, select or edit a config, click Run Eval. Results show pass/fail counts per test. For red-team scans, use the CLI script below.

### Prompt testing (CLI)

```bash
# Edit configs/promptfoo/eval-config.yaml with your prompts, then:
./scripts/test-prompts.sh

# Security red-team scan:
./scripts/redteam.sh
```

### Apply to a new project

```bash
./scripts/new-project.sh ~/my-new-app
```

Copies PromptFoo configs and scripts into your project. Add a `CLAUDE.md` describing your tech stack and design direction — the more specific it is, the better every Claude Code interaction becomes.

### CLAUDE.md: global vs project

| File | Purpose |
| --- | --- |
| `~/.claude/CLAUDE.md` | Global rules — agent personas + design rules, active in every project |
| `<project>/CLAUDE.md` | Project-specific — tech stack, design direction, project description |

`setup.sh` copies `CLAUDE.md` from this repo into `~/.claude/CLAUDE.md` (with a Y/n prompt). If a global file already exists, the old one is backed up to `~/.claude/CLAUDE.md.bak` before being replaced.

## Project structure

```text
ai-dev-utility/
├── forge.py                          # Web dashboard (primary interface)
├── setup.sh                          # One-command install
├── CLAUDE.md                         # Source for global ~/.claude/CLAUDE.md
├── LICENSE
├── minifish/
│   ├── minifish.py                   # CLI prediction engine
│   ├── gui.py                        # GUI helper for the dashboard
│   └── README.md
├── configs/
│   ├── promptfoo/
│   │   ├── eval-config.yaml          # Prompt evaluation template
│   │   └── redteam-config.yaml       # Security red-team template
├── scripts/
│   ├── test-prompts.sh               # Run prompt evaluations
│   ├── redteam.sh                    # Run security scan
│   ├── new-project.sh                # Initialize AI Dev Utility in a new project
│   ├── update-all.sh                 # Update all tools
│   └── uninstall.sh                  # Remove installed components
├── docs/
│   └── USAGE.md                      # Usage guide and companion stack
└── .cache/                           # Cloned repos (gitignored)
```

## Updating

```bash
./scripts/update-all.sh
```

## Uninstalling

```bash
./scripts/uninstall.sh
```

Choose to remove everything or select individual components. If you installed the global `~/.claude/CLAUDE.md`, you'll be given the option to restore your previous backup or delete it.

## Troubleshooting

**Ollama offline in the dashboard** - Run `ollama serve` in a terminal. It doesn't start automatically on macOS unless you've set it up as a service.

**No models showing in MiniFish** - Pull a model first: `ollama pull llama3.2` (or any model you prefer). The model name must match exactly what `ollama list` shows, and you may need to set it in Settings or pass `--model` in the CLI.

**PromptFoo not found** - Run `npm install -g promptfoo` or re-run `./setup.sh`.

**Agent personas not showing** - Run `./setup.sh` to clone and install them into `~/.claude/agents/`. Check that the directory exists: `ls ~/.claude/agents/`.

**Port 8000 in use** - Edit the `PORT` constant at the top of `forge.py`.

**Restore previous global CLAUDE.md** - If setup overwrote your existing `~/.claude/CLAUDE.md`, the original is at `~/.claude/CLAUDE.md.bak`. Run `mv ~/.claude/CLAUDE.md.bak ~/.claude/CLAUDE.md` to restore it, or use `./scripts/uninstall.sh` which walks you through this.

## License

MIT. Each bundled tool retains its own license:

- The Agency: MIT
- Impeccable: Apache 2.0
- PromptFoo: MIT
- MiroFish (inspiration for MiniFish): AGPL-3.0

## Credits

- [The Agency](https://github.com/msitarzewski/agency-agents) by msitarzewski
- [Impeccable](https://github.com/pbakaus/impeccable) by Paul Bakaus
- [PromptFoo](https://github.com/promptfoo/promptfoo) by the PromptFoo team
- [MiroFish](https://github.com/666ghj/MiroFish) by Guo Hangjiang (MiniFish inspiration)

Inspired by Fireship's [March 2026 video](https://youtu.be/Xn-gtHDsaPY).
