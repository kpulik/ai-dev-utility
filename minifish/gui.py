#!/usr/bin/env python3
"""
MiniFish GUI - Local web interface for the MiniFish prediction engine.
Run: python minifish/gui.py
Open: http://localhost:8000
"""

import http.server
import json
import os
import socketserver
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

PORT = 8000
OLLAMA_URL = "http://localhost:11434"
DATA_DIR = Path(__file__).parent / ".minifish-data"
REPORTS_DIR = DATA_DIR / "reports"
AGENTS_FILE = DATA_DIR / "agents.json"

# Ensure data dirs exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Default Agent Personas
# ============================================================================

DEFAULT_AGENTS = [
    {
        "id": "optimist",
        "name": "The Optimist",
        "emoji": "\U0001f7e2",
        "color": "#22c55e",
        "system": "You are an optimistic analyst who looks for opportunities, positive trends, and reasons things will succeed. You acknowledge risks but focus on upside potential. Keep responses to 2-3 sentences.",
    },
    {
        "id": "skeptic",
        "name": "The Skeptic",
        "emoji": "\U0001f534",
        "color": "#ef4444",
        "system": "You are a skeptical analyst who stress-tests ideas, finds flaws, and identifies risks others miss. You're not negative for its own sake but you demand evidence. Keep responses to 2-3 sentences.",
    },
    {
        "id": "pragmatist",
        "name": "The Pragmatist",
        "emoji": "\U0001f7e1",
        "color": "#eab308",
        "system": "You are a practical analyst focused on execution, feasibility, and real-world constraints like cost, timeline, and market readiness. You care about what actually works, not what sounds good. Keep responses to 2-3 sentences.",
    },
    {
        "id": "contrarian",
        "name": "The Contrarian",
        "emoji": "\U0001f7e3",
        "color": "#a855f7",
        "system": "You are a contrarian thinker who challenges consensus and explores non-obvious angles. When everyone agrees, you ask what they're missing. You look for second-order effects and hidden dynamics. Keep responses to 2-3 sentences.",
    },
    {
        "id": "enduser",
        "name": "The End User",
        "emoji": "\U0001f535",
        "color": "#3b82f6",
        "system": "You represent the average consumer or end user. You care about price, convenience, trust, and whether something actually solves a real problem in your daily life. You're not technical. Keep responses to 2-3 sentences.",
    },
    {
        "id": "historian",
        "name": "The Historian",
        "emoji": "\U0001f7e4",
        "color": "#d97706",
        "system": "You are a pattern-matcher who draws on historical precedents. You compare the current situation to similar past events and identify what usually happens in these scenarios. Keep responses to 2-3 sentences.",
    },
    {
        "id": "futurist",
        "name": "The Futurist",
        "emoji": "\u26aa",
        "color": "#06b6d4",
        "system": "You think in terms of long-term trends, technological trajectories, and paradigm shifts. You look 5-10 years out and consider how current events fit into larger arcs of change. Keep responses to 2-3 sentences.",
    },
]


def load_agents():
    if AGENTS_FILE.exists():
        try:
            return json.loads(AGENTS_FILE.read_text())
        except Exception:
            pass
    return DEFAULT_AGENTS


def save_agents(agents):
    AGENTS_FILE.write_text(json.dumps(agents, indent=2))


# ============================================================================
# Ollama Interaction
# ============================================================================


def ollama_get(path):
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def ollama_chat(model, system, messages):
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "stream": False,
        "options": {"temperature": 0.8, "num_predict": 300},
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read())
            return result.get("message", {}).get("content", "").strip()
    except Exception as e:
        return f"[Error: {e}]"


# ============================================================================
# Simulation Engine
# ============================================================================

# Global state for real-time streaming
simulation_state = {
    "running": False,
    "events": [],
    "lock": threading.Lock(),
}


def emit(event_type, data):
    with simulation_state["lock"]:
        simulation_state["events"].append(
            {"type": event_type, "data": data, "ts": time.time()}
        )


def run_simulation(topic, model, agent_ids, num_rounds):
    all_agents = load_agents()
    agents_map = {a["id"]: a for a in all_agents}
    selected = [agents_map[aid] for aid in agent_ids if aid in agents_map]

    if not selected:
        selected = all_agents[:5]

    histories = {a["id"]: [] for a in selected}

    with simulation_state["lock"]:
        simulation_state["running"] = True
        simulation_state["events"] = []

    emit("start", {"topic": topic, "model": model, "agents": len(selected), "rounds": num_rounds})

    # Phase 1: Initial reactions
    emit("phase", {"phase": 1, "name": "Initial Reactions"})
    for agent in selected:
        emit("thinking", {"agent": agent["id"], "name": agent["name"]})
        prompt = f"Analyze this topic and give your initial assessment:\n\n{topic}"
        histories[agent["id"]].append({"role": "user", "content": prompt})
        t0 = time.time()
        response = ollama_chat(model, agent["system"], histories[agent["id"]])
        elapsed = time.time() - t0
        histories[agent["id"]].append({"role": "assistant", "content": response})
        emit("response", {
            "agent": agent["id"],
            "name": agent["name"],
            "emoji": agent["emoji"],
            "color": agent["color"],
            "text": response,
            "time": round(elapsed, 1),
            "phase": 1,
            "round": 0,
        })

    # Phase 2: Debate rounds
    for r in range(1, num_rounds + 1):
        emit("phase", {"phase": 2, "name": f"Debate Round {r}/{num_rounds}"})
        for agent in selected:
            other_views = "\n".join(
                f"{a['name']}: {histories[a['id']][-1]['content']}"
                for a in selected
                if a["id"] != agent["id"]
            )
            prompt = (
                f"The other analysts said:\n\n{other_views}\n\n"
                f"Respond to their points. Agree or disagree? What are they missing? "
                f"Update or defend your position."
            )
            histories[agent["id"]].append({"role": "user", "content": prompt})
            emit("thinking", {"agent": agent["id"], "name": agent["name"]})
            t0 = time.time()
            response = ollama_chat(model, agent["system"], histories[agent["id"]])
            elapsed = time.time() - t0
            histories[agent["id"]].append({"role": "assistant", "content": response})
            emit("response", {
                "agent": agent["id"],
                "name": agent["name"],
                "emoji": agent["emoji"],
                "color": agent["color"],
                "text": response,
                "time": round(elapsed, 1),
                "phase": 2,
                "round": r,
            })

    # Phase 3: Moderator synthesis
    emit("phase", {"phase": 3, "name": "Moderator Synthesis"})
    emit("thinking", {"agent": "moderator", "name": "Moderator"})

    debate_parts = []
    for agent in selected:
        statements = [m["content"] for m in histories[agent["id"]] if m["role"] == "assistant"]
        debate_parts.append(
            f"{agent['emoji']} {agent['name']}:\n" +
            "\n".join(f"  Round {i}: {s}" for i, s in enumerate(statements))
        )

    mod_system = (
        "You are a senior analyst moderator. Synthesize the debate into a structured report:\n\n"
        "## Prediction Summary\nOne paragraph on consensus or disagreement.\n\n"
        "## Key Factors\nThe 3-5 factors that will determine the outcome.\n\n"
        "## Bull Case\nStrongest argument for a positive outcome.\n\n"
        "## Bear Case\nStrongest argument for a negative outcome.\n\n"
        "## Confidence Level\nLow / Medium / High with brief justification.\n\n"
        "## Recommendation\nWhat should someone do with this information?\n\n"
        "Be specific and actionable."
    )

    mod_prompt = f"Topic:\n{topic}\n\nDebate:\n\n" + "\n\n".join(debate_parts)
    t0 = time.time()
    report = ollama_chat(model, mod_system, [{"role": "user", "content": mod_prompt}])
    elapsed = time.time() - t0

    emit("report", {"text": report, "time": round(elapsed, 1)})

    # Save report
    report_data = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "topic": topic,
        "model": model,
        "agents": [a["name"] for a in selected],
        "rounds": num_rounds,
        "report": report,
        "timestamp": datetime.now().isoformat(),
        "events": simulation_state["events"][:],
    }
    report_path = REPORTS_DIR / f"{report_data['id']}.json"
    report_path.write_text(json.dumps(report_data, indent=2))

    emit("done", {"report_id": report_data["id"]})

    with simulation_state["lock"]:
        simulation_state["running"] = False


# ============================================================================
# HTTP Server
# ============================================================================

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MiniFish</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
    --bg-primary: #0a0e17;
    --bg-secondary: #111827;
    --bg-card: #151d2e;
    --bg-card-hover: #1a2540;
    --bg-input: #0d1220;
    --border: #1e2d4a;
    --border-bright: #2a3f6a;
    --text-primary: #e2e8f0;
    --text-secondary: #8892a8;
    --text-dim: #4a5568;
    --accent: #00d4aa;
    --accent-dim: #00d4aa22;
    --accent-glow: #00d4aa44;
    --red: #ef4444;
    --yellow: #eab308;
    --blue: #3b82f6;
    --font-mono: 'JetBrains Mono', monospace;
    --font-sans: 'DM Sans', sans-serif;
}

html { height: 100%; }
body {
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    line-height: 1.6;
}

/* Subtle grid background */
body::before {
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background-image:
        linear-gradient(var(--border) 1px, transparent 1px),
        linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 60px 60px;
    opacity: 0.15;
    pointer-events: none;
    z-index: 0;
}

/* Layout */
.app { position: relative; z-index: 1; max-width: 1100px; margin: 0 auto; padding: 24px 20px; }

/* Header */
.header { display: flex; align-items: center; gap: 16px; margin-bottom: 32px; }
.logo {
    font-family: var(--font-mono);
    font-size: 24px;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: -0.5px;
}
.logo span { color: var(--text-dim); font-weight: 400; }
.header-status {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.status-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--red);
}
.status-dot.connected { background: var(--accent); box-shadow: 0 0 8px var(--accent-glow); }

/* Navigation */
.nav {
    display: flex;
    gap: 2px;
    margin-bottom: 24px;
    background: var(--bg-secondary);
    border-radius: 10px;
    padding: 4px;
    border: 1px solid var(--border);
}
.nav-btn {
    font-family: var(--font-mono);
    font-size: 13px;
    padding: 10px 20px;
    background: transparent;
    color: var(--text-secondary);
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    font-weight: 500;
}
.nav-btn:hover { color: var(--text-primary); background: var(--bg-card); }
.nav-btn.active {
    background: var(--bg-card);
    color: var(--accent);
    box-shadow: 0 0 12px var(--accent-dim);
}

/* Panels */
.panel { display: none; }
.panel.active { display: block; animation: fadeIn 0.2s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* Forms */
.input-group { margin-bottom: 16px; }
.input-group label {
    display: block;
    font-family: var(--font-mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-dim);
    margin-bottom: 6px;
}
textarea, select, input[type="text"] {
    width: 100%;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 14px;
    padding: 12px 14px;
    outline: none;
    transition: border 0.2s;
}
textarea:focus, select:focus, input:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-dim);
}
textarea { resize: vertical; min-height: 120px; line-height: 1.5; }
select { cursor: pointer; }

.row { display: flex; gap: 16px; }
.row > * { flex: 1; }

/* Range slider */
.range-row {
    display: flex;
    align-items: center;
    gap: 12px;
}
.range-row input[type="range"] {
    flex: 1;
    -webkit-appearance: none;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    outline: none;
    border: none;
    padding: 0;
}
.range-row input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    background: var(--accent);
    border-radius: 50%;
    cursor: pointer;
    box-shadow: 0 0 8px var(--accent-glow);
}
.range-val {
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--accent);
    min-width: 24px;
    text-align: center;
}

/* Agent checkboxes */
.agent-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.agent-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s;
    font-size: 13px;
    user-select: none;
}
.agent-chip:hover { border-color: var(--border-bright); background: var(--bg-card-hover); }
.agent-chip.selected { border-color: var(--accent); background: var(--accent-dim); }
.agent-chip input { display: none; }
.agent-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }

/* Buttons */
.btn {
    font-family: var(--font-mono);
    font-size: 14px;
    font-weight: 600;
    padding: 12px 28px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s;
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.btn-primary {
    background: var(--accent);
    color: var(--bg-primary);
}
.btn-primary:hover { box-shadow: 0 0 20px var(--accent-glow); transform: translateY(-1px); }
.btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; box-shadow: none; }
.btn-secondary {
    background: var(--bg-card);
    color: var(--text-secondary);
    border: 1px solid var(--border);
}
.btn-secondary:hover { border-color: var(--border-bright); color: var(--text-primary); }
.btn-sm { padding: 6px 14px; font-size: 12px; }
.btn-danger { background: var(--red); color: white; }

/* Debate Feed */
.debate-feed { display: flex; flex-direction: column; gap: 12px; }
.debate-msg {
    padding: 14px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    border-left: 3px solid var(--border);
    animation: slideIn 0.3s ease;
}
@keyframes slideIn { from { opacity: 0; transform: translateX(-8px); } to { opacity: 1; transform: none; } }
.debate-msg-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}
.debate-msg-name {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 13px;
}
.debate-msg-meta {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-dim);
}
.debate-msg-text { font-size: 14px; color: var(--text-secondary); line-height: 1.6; }

.thinking-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 13px;
}
.thinking-dots span {
    display: inline-block;
    width: 6px; height: 6px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse 1.4s infinite;
    opacity: 0.3;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes pulse { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }

.phase-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 8px 0;
    font-family: var(--font-mono);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--accent);
}
.phase-divider::before, .phase-divider::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* Report */
.report-box {
    background: var(--bg-card);
    border: 1px solid var(--accent);
    border-radius: 12px;
    padding: 24px;
    margin-top: 16px;
    box-shadow: 0 0 30px var(--accent-dim);
}
.report-box h2 { font-family: var(--font-mono); color: var(--accent); font-size: 14px; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 2px; }
.report-text { white-space: pre-wrap; font-size: 14px; line-height: 1.7; color: var(--text-secondary); }
.report-text h2, .report-text strong { color: var(--text-primary); }

/* History */
.history-list { display: flex; flex-direction: column; gap: 8px; }
.history-item {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    cursor: pointer;
    transition: all 0.15s;
}
.history-item:hover { border-color: var(--border-bright); background: var(--bg-card-hover); }
.history-date { font-family: var(--font-mono); font-size: 12px; color: var(--text-dim); min-width: 140px; }
.history-topic { flex: 1; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.history-meta { font-family: var(--font-mono); font-size: 11px; color: var(--text-dim); }
.empty-state { text-align: center; padding: 60px 20px; color: var(--text-dim); font-family: var(--font-mono); font-size: 13px; }

/* Agent Editor */
.agent-edit-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
}
.agent-edit-header { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.agent-edit-header input[type="text"] { flex: 1; }
.agent-edit-color { width: 36px; height: 36px; border-radius: 6px; border: 2px solid var(--border); cursor: pointer; padding: 0; }
.agent-edit-card textarea { min-height: 60px; font-size: 13px; }
.agent-actions { display: flex; gap: 8px; margin-top: 20px; }

/* Modal overlay */
.modal-overlay {
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.7);
    z-index: 100;
    align-items: center;
    justify-content: center;
}
.modal-overlay.active { display: flex; }
.modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 16px;
    max-width: 700px;
    width: 90%;
    max-height: 80vh;
    overflow-y: auto;
    padding: 28px;
}
.modal h2 { font-family: var(--font-mono); font-size: 16px; margin-bottom: 20px; color: var(--accent); }
.modal-close {
    float: right;
    background: none;
    border: none;
    color: var(--text-dim);
    font-size: 20px;
    cursor: pointer;
}
.modal-close:hover { color: var(--text-primary); }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--border-bright); }
</style>
</head>
<body>
<div class="app">
    <div class="header">
        <div class="logo">minifish<span>.local</span></div>
        <div class="header-status">
            <div class="status-dot" id="statusDot"></div>
            <span id="statusText" style="color: var(--text-dim);">checking...</span>
        </div>
    </div>

    <div class="nav">
        <button class="nav-btn active" onclick="showPanel('predict')">Predict</button>
        <button class="nav-btn" onclick="showPanel('history')">History</button>
        <button class="nav-btn" onclick="showPanel('agents')">Agents</button>
    </div>

    <!-- PREDICT PANEL -->
    <div class="panel active" id="panel-predict">
        <div class="input-group">
            <label>Topic / Question / Paste Article</label>
            <textarea id="topicInput" placeholder="Will AI replace frontend developers by 2028?&#10;&#10;Or paste a news article, competitor announcement, product idea..."></textarea>
        </div>

        <div class="row">
            <div class="input-group">
                <label>Model</label>
                <select id="modelSelect"><option>loading...</option></select>
            </div>
            <div class="input-group">
                <label>Agents <span id="agentCountDisplay">5</span></label>
                <div class="range-row">
                    <input type="range" id="agentCount" min="3" max="7" value="5" oninput="updateAgentCount()">
                </div>
            </div>
            <div class="input-group">
                <label>Rounds <span id="roundCountDisplay">2</span></label>
                <div class="range-row">
                    <input type="range" id="roundCount" min="1" max="5" value="2" oninput="updateRoundCount()">
                </div>
            </div>
        </div>

        <div class="input-group">
            <label>Active Agents</label>
            <div class="agent-grid" id="agentGrid"></div>
        </div>

        <div style="margin-bottom: 24px;">
            <button class="btn btn-primary" id="runBtn" onclick="runPrediction()">
                Run Prediction
            </button>
        </div>

        <div id="debateFeed" class="debate-feed"></div>
    </div>

    <!-- HISTORY PANEL -->
    <div class="panel" id="panel-history">
        <div class="history-list" id="historyList">
            <div class="empty-state">No predictions yet. Run one first.</div>
        </div>
    </div>

    <!-- AGENTS PANEL -->
    <div class="panel" id="panel-agents">
        <p style="color: var(--text-dim); font-size: 13px; margin-bottom: 16px;">
            Customize agent personas. Changes apply to the next prediction.
        </p>
        <div id="agentEditor"></div>
        <div class="agent-actions">
            <button class="btn btn-primary btn-sm" onclick="addAgent()">+ Add Agent</button>
            <button class="btn btn-secondary btn-sm" onclick="resetAgents()">Reset to Defaults</button>
        </div>
    </div>
</div>

<!-- Report Modal -->
<div class="modal-overlay" id="reportModal">
    <div class="modal">
        <button class="modal-close" onclick="closeModal()">&times;</button>
        <h2 id="modalTitle">Prediction Report</h2>
        <div id="modalTopic" style="color: var(--text-dim); font-size: 13px; margin-bottom: 16px; font-family: var(--font-mono);"></div>
        <div class="report-text" id="modalReport"></div>
        <div style="margin-top: 20px; display: flex; gap: 8px;">
            <button class="btn btn-secondary btn-sm" onclick="exportReport()">Export Markdown</button>
            <button class="btn btn-secondary btn-sm" onclick="closeModal()">Close</button>
        </div>
    </div>
</div>

<script>
let agents = [];
let currentReportData = null;
let pollInterval = null;
let lastEventIndex = 0;

// ---- Init ----
async function init() {
    await checkOllama();
    await loadModels();
    await loadAgents();
    renderAgentGrid();
    renderAgentEditor();
    loadHistory();
}

async function checkOllama() {
    try {
        const r = await fetch('/api/status');
        const d = await r.json();
        const dot = document.getElementById('statusDot');
        const txt = document.getElementById('statusText');
        if (d.ollama) {
            dot.classList.add('connected');
            txt.textContent = 'ollama connected';
            txt.style.color = 'var(--accent)';
        } else {
            txt.textContent = 'ollama offline';
            txt.style.color = 'var(--red)';
        }
    } catch(e) {}
}

async function loadModels() {
    try {
        const r = await fetch('/api/models');
        const d = await r.json();
        const sel = document.getElementById('modelSelect');
        sel.innerHTML = '';
        (d.models || []).forEach(m => {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            if (m.includes('llama3.1') || m.includes('llama3.2')) opt.selected = true;
            sel.appendChild(opt);
        });
        if (!sel.options.length) {
            sel.innerHTML = '<option>no models found</option>';
        }
    } catch(e) {
        document.getElementById('modelSelect').innerHTML = '<option>error loading</option>';
    }
}

async function loadAgents() {
    try {
        const r = await fetch('/api/agents');
        agents = await r.json();
    } catch(e) { agents = []; }
}

// ---- Navigation ----
function showPanel(name) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('panel-' + name).classList.add('active');
    document.querySelectorAll('.nav-btn').forEach(b => {
        if (b.textContent.toLowerCase() === name) b.classList.add('active');
    });
    if (name === 'history') loadHistory();
}

// ---- Agent Grid ----
function renderAgentGrid() {
    const grid = document.getElementById('agentGrid');
    const count = parseInt(document.getElementById('agentCount').value);
    grid.innerHTML = agents.map((a, i) => `
        <label class="agent-chip ${i < count ? 'selected' : ''}" onclick="toggleAgent(this)">
            <input type="checkbox" value="${a.id}" ${i < count ? 'checked' : ''}>
            <div class="agent-dot" style="background:${a.color}"></div>
            ${a.emoji} ${a.name}
        </label>
    `).join('');
}

function toggleAgent(el) {
    const cb = el.querySelector('input');
    cb.checked = !cb.checked;
    el.classList.toggle('selected', cb.checked);
}

function updateAgentCount() {
    const v = document.getElementById('agentCount').value;
    document.getElementById('agentCountDisplay').textContent = v;
    renderAgentGrid();
}
function updateRoundCount() {
    document.getElementById('roundCountDisplay').textContent = document.getElementById('roundCount').value;
}

// ---- Run Prediction ----
async function runPrediction() {
    const topic = document.getElementById('topicInput').value.trim();
    if (!topic) return;

    const model = document.getElementById('modelSelect').value;
    const rounds = parseInt(document.getElementById('roundCount').value);
    const selectedAgents = [];
    document.querySelectorAll('#agentGrid input:checked').forEach(cb => selectedAgents.push(cb.value));

    if (selectedAgents.length < 3) {
        alert('Select at least 3 agents.');
        return;
    }

    const btn = document.getElementById('runBtn');
    btn.disabled = true;
    btn.textContent = 'Running...';

    const feed = document.getElementById('debateFeed');
    feed.innerHTML = '';
    lastEventIndex = 0;

    try {
        await fetch('/api/run', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ topic, model, agents: selectedAgents, rounds })
        });
        pollInterval = setInterval(pollEvents, 500);
    } catch(e) {
        btn.disabled = false;
        btn.textContent = 'Run Prediction';
        feed.innerHTML = '<div class="debate-msg"><div class="debate-msg-text" style="color:var(--red)">Error starting simulation.</div></div>';
    }
}

async function pollEvents() {
    try {
        const r = await fetch(`/api/events?since=${lastEventIndex}`);
        const events = await r.json();
        const feed = document.getElementById('debateFeed');

        events.forEach((evt, i) => {
            lastEventIndex++;
            if (evt.type === 'phase') {
                feed.innerHTML += `<div class="phase-divider">${evt.data.name}</div>`;
            } else if (evt.type === 'thinking') {
                // Remove previous thinking indicator
                const prev = document.getElementById('thinking-indicator');
                if (prev) prev.remove();
                feed.innerHTML += `<div class="thinking-indicator" id="thinking-indicator">
                    <div class="thinking-dots"><span></span><span></span><span></span></div>
                    ${evt.data.name} is thinking...
                </div>`;
            } else if (evt.type === 'response') {
                const prev = document.getElementById('thinking-indicator');
                if (prev) prev.remove();
                feed.innerHTML += `<div class="debate-msg" style="border-left-color:${evt.data.color}">
                    <div class="debate-msg-header">
                        <span class="debate-msg-name" style="color:${evt.data.color}">${evt.data.emoji} ${evt.data.name}</span>
                        <span class="debate-msg-meta">${evt.data.time}s</span>
                    </div>
                    <div class="debate-msg-text">${evt.data.text}</div>
                </div>`;
            } else if (evt.type === 'report') {
                const prev = document.getElementById('thinking-indicator');
                if (prev) prev.remove();
                feed.innerHTML += `<div class="report-box">
                    <h2>Prediction Report</h2>
                    <div class="report-text">${formatReport(evt.data.text)}</div>
                </div>`;
                currentReportData = evt.data;
            } else if (evt.type === 'done') {
                clearInterval(pollInterval);
                const btn = document.getElementById('runBtn');
                btn.disabled = false;
                btn.textContent = 'Run Prediction';
            }
            feed.scrollTop = feed.scrollHeight;
        });
        // Auto-scroll page
        if (events.length > 0) {
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
        }
    } catch(e) {}
}

function formatReport(text) {
    return text
        .replace(/## (.*)/g, '<strong style="color:var(--accent);font-family:var(--font-mono);font-size:12px;text-transform:uppercase;letter-spacing:1px;display:block;margin-top:16px;margin-bottom:4px;">$1</strong>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

// ---- History ----
async function loadHistory() {
    try {
        const r = await fetch('/api/reports');
        const reports = await r.json();
        const list = document.getElementById('historyList');
        if (!reports.length) {
            list.innerHTML = '<div class="empty-state">No predictions yet. Run one first.</div>';
            return;
        }
        list.innerHTML = reports.reverse().map(rep => `
            <div class="history-item" onclick="viewReport('${rep.id}')">
                <div class="history-date">${new Date(rep.timestamp).toLocaleString()}</div>
                <div class="history-topic">${escHtml(rep.topic)}</div>
                <div class="history-meta">${rep.agents.length} agents / ${rep.rounds}r</div>
            </div>
        `).join('');
    } catch(e) {}
}

async function viewReport(id) {
    try {
        const r = await fetch(`/api/report/${id}`);
        const rep = await r.json();
        currentReportData = rep;
        document.getElementById('modalTitle').textContent = 'Prediction Report';
        document.getElementById('modalTopic').textContent = rep.topic;
        document.getElementById('modalReport').innerHTML = formatReport(rep.report);
        document.getElementById('reportModal').classList.add('active');
    } catch(e) {}
}

function closeModal() {
    document.getElementById('reportModal').classList.remove('active');
}

function exportReport() {
    if (!currentReportData) return;
    const md = `# MiniFish Prediction Report\n\n**Topic:** ${currentReportData.topic || 'N/A'}\n**Date:** ${new Date().toISOString()}\n\n${currentReportData.report || currentReportData.text || ''}`;
    const blob = new Blob([md], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `minifish-report-${Date.now()}.md`;
    a.click();
}

// ---- Agent Editor ----
function renderAgentEditor() {
    const ed = document.getElementById('agentEditor');
    ed.innerHTML = agents.map((a, i) => `
        <div class="agent-edit-card">
            <div class="agent-edit-header">
                <input type="text" value="${escHtml(a.emoji)}" style="width:50px;text-align:center;" onchange="updateAgentField(${i},'emoji',this.value)">
                <input type="text" value="${escHtml(a.name)}" onchange="updateAgentField(${i},'name',this.value)">
                <input type="color" class="agent-edit-color" value="${a.color}" onchange="updateAgentField(${i},'color',this.value)">
                <button class="btn btn-secondary btn-sm" onclick="removeAgent(${i})" style="color:var(--red);">Remove</button>
            </div>
            <textarea onchange="updateAgentField(${i},'system',this.value)">${escHtml(a.system)}</textarea>
        </div>
    `).join('');
}

function updateAgentField(idx, field, value) {
    agents[idx][field] = value;
    saveAgentsToServer();
}

function removeAgent(idx) {
    if (agents.length <= 3) { alert('Minimum 3 agents required.'); return; }
    agents.splice(idx, 1);
    renderAgentEditor();
    renderAgentGrid();
    saveAgentsToServer();
}

function addAgent() {
    if (agents.length >= 10) { alert('Maximum 10 agents.'); return; }
    agents.push({
        id: 'custom_' + Date.now(),
        name: 'New Agent',
        emoji: '\u2b50',
        color: '#6b7280',
        system: 'You are a helpful analyst. Keep responses to 2-3 sentences.'
    });
    renderAgentEditor();
    renderAgentGrid();
    saveAgentsToServer();
}

function resetAgents() {
    if (!confirm('Reset all agents to defaults?')) return;
    fetch('/api/agents/reset', { method: 'POST' })
        .then(() => loadAgents())
        .then(() => { renderAgentEditor(); renderAgentGrid(); });
}

async function saveAgentsToServer() {
    await fetch('/api/agents', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(agents)
    });
}

function escHtml(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ---- Start ----
init();
</script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        elif self.path == "/api/status":
            ollama_ok = ollama_get("/api/tags") is not None
            self.send_json({"ollama": ollama_ok})

        elif self.path == "/api/models":
            data = ollama_get("/api/tags")
            models = []
            if data:
                models = [m.get("name", "") for m in data.get("models", [])]
            self.send_json({"models": models})

        elif self.path == "/api/agents":
            self.send_json(load_agents())

        elif self.path.startswith("/api/events"):
            since = 0
            if "since=" in self.path:
                try:
                    since = int(self.path.split("since=")[1])
                except ValueError:
                    pass
            with simulation_state["lock"]:
                events = simulation_state["events"][since:]
            self.send_json(events)

        elif self.path == "/api/reports":
            reports = []
            for f in sorted(REPORTS_DIR.glob("*.json")):
                try:
                    d = json.loads(f.read_text())
                    reports.append({
                        "id": d.get("id"),
                        "topic": d.get("topic", "")[:100],
                        "agents": d.get("agents", []),
                        "rounds": d.get("rounds", 0),
                        "timestamp": d.get("timestamp"),
                    })
                except Exception:
                    pass
            self.send_json(reports)

        elif self.path.startswith("/api/report/"):
            report_id = self.path.split("/api/report/")[1]
            report_path = REPORTS_DIR / f"{report_id}.json"
            if report_path.exists():
                self.send_json(json.loads(report_path.read_text()))
            else:
                self.send_json({"error": "not found"}, 404)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len) if content_len else b"{}"

        if self.path == "/api/run":
            if simulation_state["running"]:
                self.send_json({"error": "already running"}, 409)
                return
            data = json.loads(body)
            topic = data.get("topic", "")
            model = data.get("model", "llama3.2")
            agent_ids = data.get("agents", [])
            rounds = min(max(int(data.get("rounds", 2)), 1), 5)
            thread = threading.Thread(
                target=run_simulation,
                args=(topic, model, agent_ids, rounds),
                daemon=True,
            )
            thread.start()
            self.send_json({"status": "started"})

        elif self.path == "/api/agents":
            agents_data = json.loads(body)
            save_agents(agents_data)
            self.send_json({"status": "saved"})

        elif self.path == "/api/agents/reset":
            save_agents(DEFAULT_AGENTS)
            self.send_json({"status": "reset"})

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    print(f"\n  minifish.local")
    print(f"  {'='*40}")
    print(f"  Server:   http://localhost:{PORT}")
    print(f"  Ollama:   {OLLAMA_URL}")
    print(f"  Reports:  {REPORTS_DIR}")
    print(f"  {'='*40}")
    print(f"  Open http://localhost:{PORT} in your browser.\n")

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.allow_reuse_address = True
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
            httpd.shutdown()


if __name__ == "__main__":
    main()
