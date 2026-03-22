#!/usr/bin/env python3
"""
MiniFish - Lightweight Multi-Agent Prediction Engine
Inspired by MiroFish, scaled down to run fast on local hardware via Ollama.

Instead of thousands of agents on simulated social networks, MiniFish runs
5-7 agents with distinct personalities in a structured debate format.
Each agent reads the seed material, forms an opinion, debates the others,
and a moderator synthesizes the final prediction report.

Runs in 2-5 minutes on an M4 Pro with a 3-8B parameter model via Ollama.

Usage:
    python minifish.py "Your topic or paste an article here"
    python minifish.py --file news_article.txt
    python minifish.py --file news_article.txt --rounds 3 --agents 5
    python minifish.py --interactive
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "llama3.2"
DEFAULT_AGENTS = 5
DEFAULT_ROUNDS = 2
MAX_AGENTS = 7
MAX_ROUNDS = 5

# ============================================================================
# Agent Personas
# ============================================================================

PERSONAS = [
    {
        "name": "The Optimist",
        "emoji": "🟢",
        "system": (
            "You are an optimistic analyst who looks for opportunities, "
            "positive trends, and reasons things will succeed. You acknowledge "
            "risks but focus on upside potential. Keep responses to 2-3 sentences."
        ),
    },
    {
        "name": "The Skeptic",
        "emoji": "🔴",
        "system": (
            "You are a skeptical analyst who stress-tests ideas, finds flaws, "
            "and identifies risks others miss. You're not negative for its own sake "
            "but you demand evidence. Keep responses to 2-3 sentences."
        ),
    },
    {
        "name": "The Pragmatist",
        "emoji": "🟡",
        "system": (
            "You are a practical analyst focused on execution, feasibility, and "
            "real-world constraints like cost, timeline, and market readiness. "
            "You care about what actually works, not what sounds good. Keep responses to 2-3 sentences."
        ),
    },
    {
        "name": "The Contrarian",
        "emoji": "🟣",
        "system": (
            "You are a contrarian thinker who challenges consensus and explores "
            "non-obvious angles. When everyone agrees, you ask what they're missing. "
            "You look for second-order effects and hidden dynamics. Keep responses to 2-3 sentences."
        ),
    },
    {
        "name": "The End User",
        "emoji": "🔵",
        "system": (
            "You represent the average consumer or end user. You care about "
            "price, convenience, trust, and whether something actually solves a "
            "real problem in your daily life. You're not technical. Keep responses to 2-3 sentences."
        ),
    },
    {
        "name": "The Historian",
        "emoji": "🟤",
        "system": (
            "You are a pattern-matcher who draws on historical precedents. "
            "You compare the current situation to similar past events and identify "
            "what usually happens in these scenarios. Keep responses to 2-3 sentences."
        ),
    },
    {
        "name": "The Futurist",
        "emoji": "⚪",
        "system": (
            "You think in terms of long-term trends, technological trajectories, "
            "and paradigm shifts. You look 5-10 years out and consider how current "
            "events fit into larger arcs of change. Keep responses to 2-3 sentences."
        ),
    },
]

MODERATOR_SYSTEM = (
    "You are a senior analyst moderator. You have just observed a multi-perspective "
    "debate among several analysts. Your job is to synthesize their views into a clear, "
    "actionable prediction report. Structure your report as follows:\n\n"
    "PREDICTION SUMMARY: One paragraph capturing the consensus (or lack thereof).\n\n"
    "KEY FACTORS: The 3-5 most important factors that will determine the outcome.\n\n"
    "BULL CASE: The strongest argument for a positive outcome.\n\n"
    "BEAR CASE: The strongest argument for a negative outcome.\n\n"
    "CONFIDENCE LEVEL: Low / Medium / High, with a brief justification.\n\n"
    "RECOMMENDATION: What should someone do with this information?\n\n"
    "Be specific and actionable. Do not hedge everything into meaninglessness."
)


# ============================================================================
# Ollama Client
# ============================================================================


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except (urllib.error.URLError, ConnectionRefusedError, OSError):
        return False


def check_model(model: str) -> bool:
    """Check if a model is available in Ollama."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            names = [m.get("name", "") for m in data.get("models", [])]
            return any(model in n for n in names)
    except Exception:
        return False


def chat(model: str, system: str, messages: list[dict], temperature: float = 0.8) -> str:
    """Send a chat request to Ollama and return the response text."""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 256,
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result.get("message", {}).get("content", "").strip()
    except urllib.error.URLError as e:
        return f"[Error communicating with Ollama: {e}]"
    except Exception as e:
        return f"[Error: {e}]"


# ============================================================================
# Simulation Engine
# ============================================================================


@dataclass
class SimulationConfig:
    topic: str
    model: str = DEFAULT_MODEL
    num_agents: int = DEFAULT_AGENTS
    num_rounds: int = DEFAULT_ROUNDS


@dataclass
class AgentState:
    persona: dict
    history: list = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.persona["name"]

    @property
    def emoji(self) -> str:
        return self.persona["emoji"]

    @property
    def system(self) -> str:
        return self.persona["system"]


def run_simulation(config: SimulationConfig) -> str:
    """Run the full multi-agent prediction simulation."""
    agents = [
        AgentState(persona=PERSONAS[i])
        for i in range(min(config.num_agents, len(PERSONAS)))
    ]

    transcript_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        transcript_lines.append(msg)

    log(f"\n{'='*60}")
    log(f"MINIFISH PREDICTION ENGINE")
    log(f"{'='*60}")
    log(f"Topic: {config.topic[:100]}{'...' if len(config.topic) > 100 else ''}")
    log(f"Agents: {config.num_agents} | Rounds: {config.num_rounds} | Model: {config.model}")
    log(f"{'='*60}\n")

    # Phase 1: Initial reactions
    log(f"--- Phase 1: Initial Reactions ---\n")
    for agent in agents:
        prompt = (
            f"You are analyzing the following topic. Give your initial reaction "
            f"and assessment:\n\n{config.topic}"
        )
        agent.history.append({"role": "user", "content": prompt})

        sys.stdout.write(f"  {agent.emoji} {agent.name} is thinking...")
        sys.stdout.flush()
        start = time.time()

        response = chat(config.model, agent.system, agent.history)
        elapsed = time.time() - start

        agent.history.append({"role": "assistant", "content": response})

        sys.stdout.write(f"\r  {agent.emoji} {agent.name} ({elapsed:.1f}s):\n")
        log(f"  {agent.emoji} {agent.name}:")
        log(f"     {response}\n")

    # Phase 2: Debate rounds
    for round_num in range(1, config.num_rounds + 1):
        log(f"--- Phase 2: Debate Round {round_num}/{config.num_rounds} ---\n")

        # Compile what everyone said in the previous round
        previous_statements = []
        for agent in agents:
            last_response = agent.history[-1]["content"]
            previous_statements.append(f"{agent.name}: {last_response}")
        context = "\n".join(previous_statements)

        for agent in agents:
            other_views = "\n".join(
                f"  {a.name}: {a.history[-1]['content']}"
                for a in agents
                if a.name != agent.name
            )

            prompt = (
                f"The other analysts said:\n\n{other_views}\n\n"
                f"Respond to their points. Do you agree or disagree? "
                f"What are they missing? Update or defend your position."
            )
            agent.history.append({"role": "user", "content": prompt})

            sys.stdout.write(f"  {agent.emoji} {agent.name} is responding...")
            sys.stdout.flush()
            start = time.time()

            response = chat(config.model, agent.system, agent.history)
            elapsed = time.time() - start

            agent.history.append({"role": "assistant", "content": response})

            sys.stdout.write(f"\r  {agent.emoji} {agent.name} ({elapsed:.1f}s):\n")
            log(f"  {agent.emoji} {agent.name}:")
            log(f"     {response}\n")

    # Phase 3: Moderator synthesis
    log(f"--- Phase 3: Moderator Synthesis ---\n")

    # Build the full debate transcript for the moderator
    debate_summary_parts = []
    for agent in agents:
        agent_statements = [
            msg["content"]
            for msg in agent.history
            if msg["role"] == "assistant"
        ]
        debate_summary_parts.append(
            f"{agent.emoji} {agent.name}:\n"
            + "\n".join(f"  Round {i}: {s}" for i, s in enumerate(agent_statements))
        )
    debate_summary = "\n\n".join(debate_summary_parts)

    moderator_prompt = (
        f"Original topic:\n{config.topic}\n\n"
        f"Full debate transcript:\n\n{debate_summary}\n\n"
        f"Synthesize this into your prediction report."
    )

    sys.stdout.write("  Moderator is synthesizing the report...")
    sys.stdout.flush()
    start = time.time()

    report = chat(
        config.model,
        MODERATOR_SYSTEM,
        [{"role": "user", "content": moderator_prompt}],
        temperature=0.4,
    )
    elapsed = time.time() - start

    sys.stdout.write(f"\r  Moderator report generated ({elapsed:.1f}s)\n\n")

    log(f"{'='*60}")
    log(f"PREDICTION REPORT")
    log(f"{'='*60}\n")
    log(report)
    log(f"\n{'='*60}")

    return "\n".join(transcript_lines)


# ============================================================================
# Interactive Mode
# ============================================================================


def interactive_mode(model: str) -> None:
    """Run MiniFish in interactive loop mode."""
    print("\nMiniFish Interactive Mode")
    print("Type a topic, question, or paste text. Type 'quit' to exit.\n")

    while True:
        try:
            topic = input("Topic > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not topic or topic.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        config = SimulationConfig(
            topic=topic,
            model=model,
            num_agents=DEFAULT_AGENTS,
            num_rounds=DEFAULT_ROUNDS,
        )
        run_simulation(config)
        print()


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MiniFish: Lightweight multi-agent prediction engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  python minifish.py "Will AI replace frontend developers by 2028?"\n'
            "  python minifish.py --file article.txt --rounds 3\n"
            "  python minifish.py --interactive\n"
            "  python minifish.py --model mistral --agents 7 --rounds 3 'Bitcoin ETF impact'\n"
        ),
    )
    parser.add_argument("topic", nargs="?", help="Topic or question to analyze")
    parser.add_argument("--file", "-f", help="Read topic from a text file")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--agents", "-a", type=int, default=DEFAULT_AGENTS, help=f"Number of agents, 3-{MAX_AGENTS} (default: {DEFAULT_AGENTS})")
    parser.add_argument("--rounds", "-r", type=int, default=DEFAULT_ROUNDS, help=f"Debate rounds, 1-{MAX_ROUNDS} (default: {DEFAULT_ROUNDS})")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive loop mode")
    parser.add_argument("--output", "-o", help="Save full transcript to file")

    args = parser.parse_args()

    # Validate
    args.agents = max(3, min(args.agents, MAX_AGENTS))
    args.rounds = max(1, min(args.rounds, MAX_ROUNDS))

    # Check Ollama
    if not check_ollama():
        print("Error: Ollama is not running.")
        print("Start it with: ollama serve")
        print("Install it with: brew install ollama")
        sys.exit(1)

    if not check_model(args.model):
        print(f"Model '{args.model}' not found in Ollama.")
        print(f"Pull it with: ollama pull {args.model}")
        sys.exit(1)

    # Interactive mode
    if args.interactive:
        interactive_mode(args.model)
        return

    # Get topic
    topic = None
    if args.file:
        try:
            with open(args.file, "r") as f:
                topic = f.read().strip()
        except FileNotFoundError:
            print(f"File not found: {args.file}")
            sys.exit(1)
    elif args.topic:
        topic = args.topic
    else:
        # Read from stdin if piped
        if not sys.stdin.isatty():
            topic = sys.stdin.read().strip()

    if not topic:
        parser.print_help()
        print("\nProvide a topic as an argument, --file, or pipe via stdin.")
        sys.exit(1)

    # Run simulation
    config = SimulationConfig(
        topic=topic,
        model=args.model,
        num_agents=args.agents,
        num_rounds=args.rounds,
    )

    start_time = time.time()
    transcript = run_simulation(config)
    total_time = time.time() - start_time

    print(f"\nTotal time: {total_time:.1f}s")

    # Save transcript if requested
    if args.output:
        with open(args.output, "w") as f:
            f.write(transcript)
        print(f"Transcript saved to: {args.output}")


if __name__ == "__main__":
    main()
