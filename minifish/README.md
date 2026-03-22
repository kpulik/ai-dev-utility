# MiniFish

A lightweight multi-agent prediction engine inspired by [MiroFish](https://github.com/666ghj/MiroFish), designed to run fast on local hardware via Ollama.

## How it differs from MiroFish

| | MiroFish | MiniFish |
|---|---|---|
| Agents | Thousands with generated personalities | 5-7 with curated personas |
| Platform | Simulated Twitter + Reddit | Structured debate format |
| Runtime | 5-60 min (cloud API) / hours (local) | 2-5 min (local Ollama) |
| Cost | $1-50 per simulation (API fees) | Free (runs on Ollama) |
| Dependencies | Node.js, Python, Docker, Zep Cloud, LLM API | Python 3 + Ollama |
| Output | Full social network simulation + report | Debate transcript + prediction report |

MiniFish trades scale for speed. Instead of emergent behavior from thousands of agents on fake social networks, it gets multi-perspective analysis from a small panel of distinct thinkers debating each other directly.

## The 7 agents

Each agent brings a fundamentally different lens:

- **The Optimist** - opportunities, upside potential, reasons it will work
- **The Skeptic** - risks, flaws, demands evidence
- **The Pragmatist** - execution, feasibility, real-world constraints
- **The Contrarian** - challenges consensus, second-order effects
- **The End User** - price, convenience, does this solve a real problem?
- **The Historian** - pattern-matching to historical precedents
- **The Futurist** - long-term trends, paradigm shifts, 5-10 year view

A moderator then synthesizes everything into a structured prediction report.

## Usage

```bash
# Simple topic
python minifish/minifish.py "Will AI replace frontend developers by 2028?"

# Read from a file (paste a news article into article.txt)
python minifish/minifish.py --file article.txt

# More agents, more debate rounds (slower but deeper)
python minifish/minifish.py --agents 7 --rounds 3 "Bitcoin ETF impact on retail"

# Use a different model
python minifish/minifish.py --model mistral "Should I build a SaaS for X?"

# Interactive mode (keep asking questions)
python minifish/minifish.py --interactive

# Save the full transcript
python minifish/minifish.py --output report.txt "Market for AI coding tools"

# Pipe input
cat article.txt | python minifish/minifish.py
```

## Requirements

- Python 3.10+
- Ollama running locally (`brew install ollama && ollama serve`)
- Any model pulled (`ollama pull llama3.2`)

No pip dependencies. No API keys. No Docker. Just Python and Ollama.
