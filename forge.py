#!/usr/bin/env python3
"""
AI Forge - Unified GUI
One dashboard controlling all tools: Agency, Impeccable, PromptFoo, MiniFish.

Run:    python forge.py
Open:   http://localhost:8000

No pip dependencies. Just Python 3.10+ and Ollama.
"""

import http.server
import json
import os
import socketserver
import subprocess
import shutil
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

PORT = 8000
FORGE_DIR = Path(__file__).parent
DATA_DIR = FORGE_DIR / ".forge-data"
REPORTS_DIR = DATA_DIR / "reports"
AGENTS_FILE = DATA_DIR / "agents.json"
SETTINGS_FILE = DATA_DIR / "settings.json"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Default Agents
# ============================================================================

DEFAULT_AGENTS = [
    {"id":"optimist","name":"The Optimist","emoji":"\U0001f7e2","color":"#22c55e",
     "system":"You are an optimistic analyst who looks for opportunities, positive trends, and reasons things will succeed. You acknowledge risks but focus on upside potential. Keep responses to 2-3 sentences."},
    {"id":"skeptic","name":"The Skeptic","emoji":"\U0001f534","color":"#ef4444",
     "system":"You are a skeptical analyst who stress-tests ideas, finds flaws, and identifies risks others miss. You're not negative for its own sake but you demand evidence. Keep responses to 2-3 sentences."},
    {"id":"pragmatist","name":"The Pragmatist","emoji":"\U0001f7e1","color":"#eab308",
     "system":"You are a practical analyst focused on execution, feasibility, and real-world constraints like cost, timeline, and market readiness. You care about what actually works, not what sounds good. Keep responses to 2-3 sentences."},
    {"id":"contrarian","name":"The Contrarian","emoji":"\U0001f7e3","color":"#a855f7",
     "system":"You are a contrarian thinker who challenges consensus and explores non-obvious angles. When everyone agrees, you ask what they're missing. You look for second-order effects. Keep responses to 2-3 sentences."},
    {"id":"enduser","name":"The End User","emoji":"\U0001f535","color":"#3b82f6",
     "system":"You represent the average consumer or end user. You care about price, convenience, trust, and whether something solves a real problem in daily life. You're not technical. Keep responses to 2-3 sentences."},
    {"id":"historian","name":"The Historian","emoji":"\U0001f7e4","color":"#d97706",
     "system":"You are a pattern-matcher who draws on historical precedents. You compare the current situation to similar past events. Keep responses to 2-3 sentences."},
    {"id":"futurist","name":"The Futurist","emoji":"\u26aa","color":"#06b6d4",
     "system":"You think in terms of long-term trends, technological trajectories, and paradigm shifts. You look 5-10 years out. Keep responses to 2-3 sentences."},
]

# ============================================================================
# Impeccable Commands Reference
# ============================================================================

IMPECCABLE_COMMANDS = [
    {"cmd": "/audit", "desc": "Run a comprehensive quality check on your UI: accessibility, contrast, responsive breakpoints, loading/error/empty states.", "category": "quality"},
    {"cmd": "/critique", "desc": "Get honest design criticism. Identifies what's weak, generic, or inconsistent.", "category": "quality"},
    {"cmd": "/distill", "desc": "Simplify a complex UI. Progressive disclosure, reduce cognitive load, hide advanced options.", "category": "simplify"},
    {"cmd": "/strip", "desc": "Remove all decorative elements. Get to the raw functional core.", "category": "simplify"},
    {"cmd": "/colorize", "desc": "Apply a brand color palette. Dominant color with sharp accents, OKLCH color space.", "category": "style"},
    {"cmd": "/typeset", "desc": "Choose distinctive typography. Pair a display font with a body font. Never Inter/Roboto/Arial.", "category": "style"},
    {"cmd": "/animate", "desc": "Add purposeful motion. Staggered reveals on load, meaningful hover states. No bounce easing.", "category": "enhance"},
    {"cmd": "/delight", "desc": "Add one memorable micro-interaction that makes the UI feel special and unique.", "category": "enhance"},
    {"cmd": "/polish", "desc": "Refine spacing, alignment, shadows, and small details that separate good from great.", "category": "enhance"},
    {"cmd": "/contrast", "desc": "Maximize visual hierarchy. Make the important things impossible to miss.", "category": "style"},
    {"cmd": "/responsive", "desc": "Ensure the layout adapts beautifully across mobile, tablet, and desktop.", "category": "quality"},
    {"cmd": "/darkmode", "desc": "Add or improve dark mode. Not just inverted colors but a cohesive dark palette.", "category": "style"},
    {"cmd": "/a11y", "desc": "Fix accessibility issues. WCAG compliance, keyboard nav, screen reader labels, focus indicators.", "category": "quality"},
    {"cmd": "/density", "desc": "Increase information density without sacrificing clarity. Tighter but still readable.", "category": "simplify"},
    {"cmd": "/whitespace", "desc": "Add breathing room. Generous margins, padding, and negative space.", "category": "simplify"},
    {"cmd": "/brand", "desc": "Infuse brand personality throughout. Consistent voice, colors, shapes, and feel.", "category": "style"},
    {"cmd": "/wow", "desc": "Go all out. Make this page unforgettable with bold creative choices.", "category": "enhance"},
]

# ============================================================================
# Helpers
# ============================================================================

def load_agents():
    if AGENTS_FILE.exists():
        try: return json.loads(AGENTS_FILE.read_text())
        except: pass
    return DEFAULT_AGENTS

def save_agents(agents):
    AGENTS_FILE.write_text(json.dumps(agents, indent=2))

def load_settings():
    defaults = {"ollama_url": "http://localhost:11434", "default_model": "", "default_agents": 5, "default_rounds": 2}
    if SETTINGS_FILE.exists():
        try:
            stored = json.loads(SETTINGS_FILE.read_text())
            defaults.update(stored)
        except: pass
    return defaults

def save_settings(s):
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))

# Mutable settings loaded at startup; updated via /api/settings POST
APP_SETTINGS = load_settings()

def get_ollama_url():
    return APP_SETTINGS.get("ollama_url", "http://localhost:11434")

def ollama_get(path):
    try:
        req = urllib.request.Request(f"{get_ollama_url()}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except: return None

def ollama_chat(model, system, messages):
    payload = {"model": model, "messages": [{"role":"system","content":system}]+messages, "stream": False, "options": {"temperature":0.8,"num_predict":300}}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(f"{get_ollama_url()}/api/chat", data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read()).get("message",{}).get("content","").strip()
    except Exception as e:
        return f"[Error: {e}]"

# ============================================================================
# Simulation
# ============================================================================

sim_state = {"running": False, "events": [], "lock": threading.Lock()}

def emit(t, d):
    with sim_state["lock"]:
        sim_state["events"].append({"type":t,"data":d,"ts":time.time()})

def run_simulation(topic, model, agent_ids, num_rounds):
    all_agents = load_agents()
    amap = {a["id"]:a for a in all_agents}
    selected = [amap[aid] for aid in agent_ids if aid in amap] or all_agents[:5]
    histories = {a["id"]:[] for a in selected}
    with sim_state["lock"]:
        sim_state["running"] = True
        sim_state["events"] = []
    emit("start",{"topic":topic,"model":model,"agents":len(selected),"rounds":num_rounds})
    # Phase 1
    emit("phase",{"phase":1,"name":"Initial Reactions"})
    for a in selected:
        emit("thinking",{"agent":a["id"],"name":a["name"]})
        p = f"Analyze this topic and give your initial assessment:\n\n{topic}"
        histories[a["id"]].append({"role":"user","content":p})
        t0=time.time()
        r=ollama_chat(model,a["system"],histories[a["id"]])
        histories[a["id"]].append({"role":"assistant","content":r})
        emit("response",{"agent":a["id"],"name":a["name"],"emoji":a["emoji"],"color":a["color"],"text":r,"time":round(time.time()-t0,1),"phase":1,"round":0})
    # Phase 2
    for rnd in range(1,num_rounds+1):
        emit("phase",{"phase":2,"name":f"Debate Round {rnd}/{num_rounds}"})
        for a in selected:
            others = "\n".join(f"{o['name']}: {histories[o['id']][-1]['content']}" for o in selected if o["id"]!=a["id"])
            p=f"The other analysts said:\n\n{others}\n\nRespond to their points. Agree or disagree? What are they missing?"
            histories[a["id"]].append({"role":"user","content":p})
            emit("thinking",{"agent":a["id"],"name":a["name"]})
            t0=time.time()
            r=ollama_chat(model,a["system"],histories[a["id"]])
            histories[a["id"]].append({"role":"assistant","content":r})
            emit("response",{"agent":a["id"],"name":a["name"],"emoji":a["emoji"],"color":a["color"],"text":r,"time":round(time.time()-t0,1),"phase":2,"round":rnd})
    # Phase 3
    emit("phase",{"phase":3,"name":"Moderator Synthesis"})
    emit("thinking",{"agent":"moderator","name":"Moderator"})
    parts=[]
    for a in selected:
        stmts=[m["content"] for m in histories[a["id"]] if m["role"]=="assistant"]
        parts.append(f"{a['emoji']} {a['name']}:\n"+"\n".join(f"  Round {i}: {s}" for i,s in enumerate(stmts)))
    mod_sys="You are a senior analyst moderator. Synthesize into:\n\n## Prediction Summary\nOne paragraph.\n\n## Key Factors\n3-5 factors.\n\n## Bull Case\nBest positive argument.\n\n## Bear Case\nBest negative argument.\n\n## Confidence Level\nLow/Medium/High.\n\n## Recommendation\nActionable advice.\n\nBe specific."
    t0=time.time()
    report=ollama_chat(model,mod_sys,[{"role":"user","content":f"Topic:\n{topic}\n\nDebate:\n\n"+"\n\n".join(parts)}])
    emit("report",{"text":report,"time":round(time.time()-t0,1)})
    rd={"id":datetime.now().strftime("%Y%m%d_%H%M%S"),"topic":topic,"model":model,"agents":[a["name"] for a in selected],"rounds":num_rounds,"report":report,"timestamp":datetime.now().isoformat(),"events":sim_state["events"][:]}
    (REPORTS_DIR/f"{rd['id']}.json").write_text(json.dumps(rd,indent=2))
    emit("done",{"report_id":rd["id"]})
    with sim_state["lock"]:
        sim_state["running"]=False

# ============================================================================
# Agency Scanner
# ============================================================================

def scan_agency_agents():
    """Scan installed agent persona files."""
    agents_dir = Path.home() / ".claude" / "agents"
    agents = []
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*.md")):
            try:
                text = f.read_text(errors='replace')
                title = f.stem.replace("-"," ").replace("_"," ").title()
                for line in text.split("\n"):
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
                preview = ""
                for line in text.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                        preview = stripped[:200]
                        break
                agents.append({"file": f.name, "title": title, "preview": preview, "size": len(text)})
            except:
                agents.append({"file": f.name, "title": f.stem, "preview": "", "size": 0})
    return agents

def read_agent_file(filename):
    p = Path.home() / ".claude" / "agents" / Path(filename).name
    if p.exists():
        return p.read_text(errors='replace')
    return None

# ============================================================================
# PromptFoo Integration
# ============================================================================

def find_promptfoo():
    """Locate the promptfoo binary, checking PATH and common npm global locations."""
    p = shutil.which("promptfoo")
    if p:
        return p
    for candidate in [
        "/usr/local/bin/promptfoo",
        "/opt/homebrew/bin/promptfoo",
        str(Path.home() / ".npm-global" / "bin" / "promptfoo"),
        str(Path.home() / ".local" / "bin" / "promptfoo"),
    ]:
        if Path(candidate).exists():
            return candidate
    return None

def get_promptfoo_status():
    """Check if promptfoo is installed and get version."""
    pf = find_promptfoo()
    if not pf:
        return {"installed": False, "version": None}
    try:
        r = subprocess.run([pf, "--version"], capture_output=True, text=True, timeout=5)
        version = r.stdout.strip() or r.stderr.strip() or "installed"
        return {"installed": True, "version": version}
    except:
        return {"installed": True, "version": "installed"}

def run_promptfoo_eval(config_path):
    """Run promptfoo eval and return results."""
    pf = find_promptfoo()
    if not pf:
        return {"success": False, "parsed": False, "stdout": "", "stderr": "promptfoo not found. Run: npm install -g promptfoo"}
    output_file = str(DATA_DIR / "promptfoo_result.json")
    try:
        r = subprocess.run(
            [pf, "eval", "-c", config_path, "--no-cache", "--output", output_file],
            capture_output=True, text=True, timeout=300, cwd=str(FORGE_DIR)
        )
        result = {"success": r.returncode == 0, "stdout": r.stdout[-3000:], "stderr": r.stderr[-2000:], "parsed": False}
        output_path = Path(output_file)
        if output_path.exists():
            try:
                data = json.loads(output_path.read_text())
                stats = data.get("stats", {})
                passes = stats.get("successes", 0)
                failures = stats.get("failures", 0)
                rows = data.get("results", [])
                result.update({
                    "parsed": True,
                    "passes": passes,
                    "failures": failures,
                    "total": passes + failures,
                    "results": [
                        {
                            "prompt": str(row.get("prompt", {}).get("raw", ""))[:200],
                            "pass": row.get("success", False),
                            "score": row.get("score"),
                            "output": str((row.get("response") or {}).get("output", ""))[:300],
                            "error": str(row.get("error") or "")[:200],
                        }
                        for row in rows[:50]
                    ],
                })
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        return result
    except subprocess.TimeoutExpired:
        return {"success": False, "parsed": False, "stdout": "", "stderr": "Timed out after 5 minutes"}
    except Exception as e:
        return {"success": False, "parsed": False, "stdout": "", "stderr": str(e)}

def get_promptfoo_configs():
    """List available promptfoo config files."""
    cfg_dir = FORGE_DIR / "configs" / "promptfoo"
    configs = []
    if cfg_dir.exists():
        for f in cfg_dir.glob("*.yaml"):
            configs.append({"file": f.name, "path": str(f), "size": f.stat().st_size})
        for f in cfg_dir.glob("*.yml"):
            configs.append({"file": f.name, "path": str(f), "size": f.stat().st_size})
    return configs

def read_config_file(filename):
    p = FORGE_DIR / "configs" / "promptfoo" / Path(filename).name
    if p.exists():
        return p.read_text()
    return None

def write_config_file(filename, content):
    p = FORGE_DIR / "configs" / "promptfoo" / Path(filename).name
    p.write_text(content)

# ============================================================================
# HTML
# ============================================================================

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI Forge</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,500;0,600;0,700;1,400&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
--bg-0:#06090f;--bg-1:#0c1018;--bg-2:#111827;--bg-3:#1a2332;--bg-4:#1e2d4a;
--border:#1a2540;--border-hi:#2a3f6a;
--text-1:#e8ecf2;--text-2:#94a3b8;--text-3:#4a5a72;
--acc:#00e4b8;--acc-dim:rgba(0,228,184,0.12);--acc-glow:rgba(0,228,184,0.25);
--red:#f43f5e;--orange:#f59e0b;--blue:#3b82f6;--purple:#a855f7;--green:#22c55e;
--mono:'JetBrains Mono',monospace;--sans:'DM Sans',sans-serif;
--radius:10px;
}
html{height:100%}
body{font-family:var(--sans);background:var(--bg-0);color:var(--text-1);min-height:100vh;line-height:1.6;overflow-x:hidden}
body::before{content:'';position:fixed;inset:0;background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px);background-size:50px 50px;opacity:0.07;pointer-events:none;z-index:0}

/* Layout */
.layout{display:flex;min-height:100vh;position:relative;z-index:1}
.sidebar{width:216px;background:var(--bg-1);border-right:1px solid var(--border);padding:0;flex-shrink:0;position:sticky;top:0;height:100vh;display:flex;flex-direction:column;overflow:hidden}
.main{flex:1;padding:32px 40px;max-width:1140px;min-height:100vh}

/* Sidebar logo */
.sidebar-logo{padding:20px 20px 18px;border-bottom:1px solid var(--border)}
.logo-wordmark{font-family:var(--mono);font-size:17px;font-weight:700;color:var(--acc);letter-spacing:-0.5px;display:flex;align-items:baseline;gap:6px}
.logo-wordmark small{color:var(--text-3);font-weight:400;font-size:11px}
.logo-sub{font-size:11px;color:var(--text-3);font-family:var(--mono);margin-top:3px}

/* Nav */
.nav-body{flex:1;padding:10px 8px}
.nav-sep{height:1px;background:var(--border);margin:8px 8px}
.nav-item{display:flex;align-items:center;gap:9px;padding:9px 11px;border-radius:8px;cursor:pointer;color:var(--text-2);transition:all .15s;margin-bottom:2px;border:1px solid transparent;position:relative}
.nav-item:hover{background:var(--bg-2);color:var(--text-1)}
.nav-item.active{background:var(--acc-dim);color:var(--acc);border-color:rgba(0,228,184,0.18)}
.nav-icon{font-size:14px;width:17px;text-align:center;flex-shrink:0;opacity:.7}
.nav-item.active .nav-icon{opacity:1}
.nav-label{font-family:var(--mono);font-size:12px;letter-spacing:0.2px;flex:1}
.nav-badge{font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:.8px;padding:2px 5px;border-radius:3px;background:rgba(0,228,184,0.15);color:var(--acc);border:1px solid rgba(0,228,184,0.2)}

/* Sidebar status */
.sidebar-status{padding:12px 18px;border-top:1px solid var(--border);font-family:var(--mono);font-size:11px;color:var(--text-3)}
.status-row{display:flex;align-items:center;gap:7px;margin-bottom:4px}
.dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.dot-on{background:var(--acc);box-shadow:0 0 5px var(--acc-glow)}
.dot-off{background:var(--red)}
.dot-warn{background:var(--orange)}

/* Page header */
.page-header{margin-bottom:26px}
.page-header h2{font-family:var(--mono);font-size:21px;font-weight:700;letter-spacing:-0.5px;color:var(--text-1)}
.page-header p{color:var(--text-3);font-size:13px;margin-top:4px}

/* Generic card */
.card{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.card-title{font-family:var(--mono);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:2px;color:var(--text-3)}

/* Dashboard status bar */
.status-bar{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}
.status-pill{display:flex;align-items:center;gap:10px;padding:11px 16px;background:var(--bg-2);border:1px solid var(--border);border-radius:9px;min-width:150px;flex:1}
.sp-dot-wrap{flex-shrink:0}
.sp-label{font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:1.2px;color:var(--text-3);margin-bottom:2px}
.sp-val{font-family:var(--mono);font-size:13px;font-weight:600;color:var(--text-1);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px}

/* Dashboard tool cards */
.dash-hero{background:var(--bg-2);border:1px solid var(--acc);border-radius:var(--radius);padding:24px;margin-bottom:16px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.dash-hero::after{content:'';position:absolute;inset:0;background:linear-gradient(135deg,rgba(0,228,184,0.04) 0%,transparent 60%);pointer-events:none}
.dash-hero:hover{box-shadow:0 0 32px var(--acc-dim);transform:translateY(-1px)}
.dash-hero-inner{display:flex;align-items:center;justify-content:space-between;gap:20px}
.dash-hero-text{flex:1}
.dash-hero-title{font-family:var(--mono);font-size:18px;font-weight:700;color:var(--acc);margin-bottom:6px}
.dash-hero-desc{font-size:13px;color:var(--text-2);line-height:1.6;max-width:520px}
.dash-hero-action{font-family:var(--mono);font-size:11px;color:var(--acc);margin-top:10px;opacity:.8}

.dash-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:0}
.dash-card{background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);padding:18px;cursor:pointer;transition:all .18s}
.dash-card:hover{border-color:var(--border-hi);background:var(--bg-3);transform:translateY(-1px)}
.dc-badge{display:inline-block;font-family:var(--mono);font-size:8px;text-transform:uppercase;letter-spacing:1.2px;padding:2px 7px;border-radius:3px;margin-bottom:10px;font-weight:600}
.badge-interactive{background:rgba(0,228,184,0.12);color:var(--acc);border:1px solid rgba(0,228,184,0.2)}
.badge-ondemand{background:rgba(59,130,246,0.12);color:var(--blue);border:1px solid rgba(59,130,246,0.2)}
.badge-alwayson{background:rgba(34,197,94,0.1);color:var(--green);border:1px solid rgba(34,197,94,0.2)}
.badge-setup{background:rgba(245,158,11,0.1);color:var(--orange);border:1px solid rgba(245,158,11,0.2)}
.dc-title{font-family:var(--mono);font-size:13px;font-weight:700;color:var(--text-1);margin-bottom:6px}
.dc-desc{font-size:12px;color:var(--text-3);line-height:1.5}
.dc-action{font-family:var(--mono);font-size:10px;color:var(--acc);margin-top:10px;opacity:.7}

/* Inner tabs (Configure) */
.itab-nav{display:flex;gap:2px;background:var(--bg-1);border:1px solid var(--border);border-radius:10px;padding:3px;margin-bottom:22px}
.itab{flex:1;text-align:center;padding:7px 10px;border-radius:8px;cursor:pointer;font-family:var(--mono);font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--text-3);transition:all .15s;white-space:nowrap}
.itab:hover{color:var(--text-2)}
.itab.active{background:var(--bg-3);color:var(--acc);box-shadow:0 1px 4px rgba(0,0,0,.4)}

/* MiniFish two-column */
.predict-layout{display:grid;grid-template-columns:350px 1fr;gap:20px;align-items:start}
.predict-controls{position:sticky;top:20px}
.no-model-warn{margin-top:10px;padding:9px 12px;background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.2);border-radius:7px;font-size:12px;color:var(--orange);font-family:var(--mono)}

/* Forms */
label.field-label{display:block;font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-3);margin-bottom:6px;font-weight:600}
textarea,select,input[type="text"],input[type="number"]{width:100%;background:var(--bg-1);border:1px solid var(--border);border-radius:8px;color:var(--text-1);font-family:var(--sans);font-size:14px;padding:10px 12px;outline:none;transition:border .2s}
textarea:focus,select:focus,input:focus{border-color:var(--acc);box-shadow:0 0 0 3px var(--acc-dim)}
textarea{resize:vertical;min-height:100px;font-family:var(--sans);line-height:1.5}
.code-textarea{font-family:var(--mono);font-size:13px;line-height:1.6;min-height:200px;tab-size:2}
select{cursor:pointer}
.row{display:flex;gap:12px}.row>*{flex:1}
.input-group{margin-bottom:14px}

/* Range */
.range-row{display:flex;align-items:center;gap:10px}
input[type="range"]{flex:1;-webkit-appearance:none;height:4px;background:var(--border);border-radius:2px;outline:none;border:none;padding:0}
input[type="range"]::-webkit-slider-thumb{-webkit-appearance:none;width:15px;height:15px;background:var(--acc);border-radius:50%;cursor:pointer;box-shadow:0 0 7px var(--acc-glow)}
.range-val{font-family:var(--mono);font-size:14px;color:var(--acc);min-width:18px;text-align:center}

/* Buttons */
.btn{font-family:var(--mono);font-size:13px;font-weight:600;padding:10px 22px;border:none;border-radius:8px;cursor:pointer;transition:all .15s;display:inline-flex;align-items:center;gap:8px}
.btn-primary{background:var(--acc);color:var(--bg-0)}
.btn-primary:hover{box-shadow:0 0 18px var(--acc-glow);transform:translateY(-1px)}
.btn-primary:disabled{opacity:.35;cursor:not-allowed;transform:none;box-shadow:none}
.btn-ghost{background:transparent;color:var(--text-2);border:1px solid var(--border)}
.btn-ghost:hover{border-color:var(--border-hi);color:var(--text-1)}
.btn-sm{padding:6px 14px;font-size:11px}
.btn-full{width:100%;justify-content:center}
.btn-danger{background:var(--red);color:#fff}

/* Agent chips */
.agent-grid{display:flex;flex-wrap:wrap;gap:5px}
.agent-chip{display:flex;align-items:center;gap:5px;padding:6px 11px;background:var(--bg-3);border:1px solid var(--border);border-radius:7px;cursor:pointer;font-size:12px;user-select:none;transition:all .12s}
.agent-chip:hover{border-color:var(--border-hi)}
.agent-chip.on{border-color:var(--acc);background:var(--acc-dim)}
.chip-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}

/* Debate feed */
.feed{display:flex;flex-direction:column;gap:10px}
.feed-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:60px 20px;color:var(--text-3);font-family:var(--mono);font-size:12px;text-align:center;border:1px dashed var(--border);border-radius:var(--radius);background:var(--bg-2)}
.feed-empty .fe-icon{font-size:32px;margin-bottom:12px;opacity:.4}
.msg{padding:14px;background:var(--bg-3);border:1px solid var(--border);border-radius:var(--radius);border-left:3px solid var(--border);animation:fadeUp .25s ease}
@keyframes fadeUp{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.msg-head{display:flex;align-items:center;gap:8px;margin-bottom:5px}
.msg-name{font-family:var(--mono);font-weight:600;font-size:12px}
.msg-time{margin-left:auto;font-family:var(--mono);font-size:10px;color:var(--text-3)}
.msg-text{font-size:13px;color:var(--text-2);line-height:1.6}
.phase-div{display:flex;align-items:center;gap:12px;margin:4px 0;font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:2.5px;color:var(--acc)}
.phase-div::before,.phase-div::after{content:'';flex:1;height:1px;background:var(--border)}
.thinking{display:flex;align-items:center;gap:8px;padding:10px 14px;color:var(--text-3);font-family:var(--mono);font-size:12px}
.dots span{display:inline-block;width:4px;height:4px;background:var(--acc);border-radius:50%;animation:blink 1.4s infinite;opacity:.3}
.dots span:nth-child(2){animation-delay:.2s}.dots span:nth-child(3){animation-delay:.4s}
@keyframes blink{0%,80%,100%{opacity:.3}40%{opacity:1}}

/* Report box */
.report-box{background:var(--bg-2);border:1px solid var(--acc);border-radius:12px;padding:20px;margin-top:12px;box-shadow:0 0 24px var(--acc-dim)}
.report-box h3{font-family:var(--mono);color:var(--acc);font-size:10px;margin-bottom:12px;text-transform:uppercase;letter-spacing:2px}
.report-text{white-space:pre-wrap;font-size:13px;line-height:1.7;color:var(--text-2)}

/* History */
.hist-item{display:flex;align-items:center;gap:14px;padding:12px 16px;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;transition:all .12s;margin-bottom:6px}
.hist-item:hover{border-color:var(--border-hi);background:var(--bg-3)}
.hist-date{font-family:var(--mono);font-size:11px;color:var(--text-3);min-width:130px}
.hist-topic{flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hist-meta{font-family:var(--mono);font-size:10px;color:var(--text-3)}

/* Agency agents list */
.agency-item{display:flex;align-items:start;gap:12px;padding:12px 14px;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:6px;cursor:pointer;transition:all .12s}
.agency-item:hover{border-color:var(--border-hi);background:var(--bg-3)}
.agency-name{font-family:var(--mono);font-size:13px;font-weight:600;margin-bottom:2px}
.agency-preview{font-size:12px;color:var(--text-3);line-height:1.4}
.agency-file{font-family:var(--mono);font-size:10px;color:var(--text-3);background:var(--bg-1);padding:2px 7px;border-radius:4px;white-space:nowrap;flex-shrink:0}

/* Impeccable grid */
.imp-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
.imp-card{padding:14px;background:var(--bg-2);border:1px solid var(--border);border-radius:var(--radius);cursor:pointer;transition:all .12s}
.imp-card:hover{border-color:var(--acc);background:var(--bg-3)}
.imp-cmd{font-family:var(--mono);font-size:14px;font-weight:700;color:var(--acc);margin-bottom:4px}
.imp-desc{font-size:12px;color:var(--text-2);line-height:1.5}
.imp-cat{display:inline-block;font-family:var(--mono);font-size:9px;text-transform:uppercase;letter-spacing:1px;padding:2px 7px;border-radius:4px;margin-top:7px}
.cat-quality{background:rgba(59,130,246,0.15);color:var(--blue)}
.cat-simplify{background:rgba(245,158,11,0.15);color:var(--orange)}
.cat-style{background:rgba(168,85,247,0.15);color:var(--purple)}
.cat-enhance{background:rgba(34,197,94,0.15);color:var(--green)}

/* Agent persona editor */
.edit-card{background:var(--bg-3);border:1px solid var(--border);border-radius:var(--radius);padding:14px;margin-bottom:10px}
.edit-head{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.edit-head input[type="text"]{flex:1}
.edit-color{width:34px;height:34px;border-radius:6px;border:2px solid var(--border);cursor:pointer;padding:0}

/* PromptFoo */
.pf-run-output{background:var(--bg-1);border:1px solid var(--border);border-radius:var(--radius);padding:14px;font-family:var(--mono);font-size:12px;color:var(--text-2);white-space:pre-wrap;max-height:400px;overflow-y:auto;margin-top:12px}

/* Section subheader */
.sub-header{font-family:var(--mono);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1.5px;color:var(--text-3);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)}

/* Modal */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:100;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:var(--bg-2);border:1px solid var(--border);border-radius:14px;max-width:720px;width:92%;max-height:82vh;overflow-y:auto;padding:24px}
.modal h2{font-family:var(--mono);font-size:14px;color:var(--acc);margin-bottom:16px}
.modal-x{float:right;background:none;border:none;color:var(--text-3);font-size:20px;cursor:pointer;padding:0 4px}
.modal-x:hover{color:var(--text-1)}

/* Empty state */
.empty{text-align:center;padding:48px 20px;color:var(--text-3);font-family:var(--mono);font-size:12px}

/* Scrollbar */
::-webkit-scrollbar{width:5px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* Responsive */
@media(max-width:900px){
  .sidebar{width:56px;overflow:hidden}
  .nav-label,.nav-badge,.logo-wordmark small,.logo-sub{display:none}
  .main{padding:20px 16px}
  .predict-layout{grid-template-columns:1fr}
  .predict-controls{position:static}
  .dash-cards{grid-template-columns:1fr}
}
@media(max-width:640px){.status-bar{flex-direction:column}.dash-hero-inner{flex-direction:column}}
</style>
</head>
<body>
<div class="layout">
  <div class="sidebar">
    <div class="sidebar-logo">
      <div class="logo-wordmark">AI Forge <small>v1</small></div>
      <div class="logo-sub">local dev toolkit</div>
    </div>
    <div class="nav-body">
      <div class="nav-item active" onclick="nav('dash')"><span class="nav-icon">&#9670;</span><span class="nav-label">Dashboard</span></div>
      <div class="nav-sep"></div>
      <div class="nav-item" onclick="nav('predict')"><span class="nav-icon">&#9733;</span><span class="nav-label">MiniFish</span><span class="nav-badge">run</span></div>
      <div class="nav-item" onclick="nav('history')"><span class="nav-icon">&#8986;</span><span class="nav-label">History</span></div>
      <div class="nav-item" onclick="nav('promptfoo')"><span class="nav-icon">&#9888;</span><span class="nav-label">PromptFoo</span></div>
      <div class="nav-sep"></div>
      <div class="nav-item" onclick="nav('configure')"><span class="nav-icon">&#9881;</span><span class="nav-label">Configure</span></div>
    </div>
    <div class="sidebar-status">
      <div class="status-row"><div class="dot" id="dotOllama"></div><span id="txtOllama">ollama</span></div>
      <div class="status-row"><div class="dot" id="dotPf"></div><span id="txtPf">promptfoo</span></div>
      <div class="status-row"><div class="dot" id="dotAgency"></div><span id="txtAgency">agents</span></div>
    </div>
  </div>
  <div class="main" id="mainContent"></div>
</div>

<div class="modal-bg" id="modal"><div class="modal"><button class="modal-x" onclick="closeModal()">&times;</button><div id="modalBody"></div></div></div>

<script>
// ============================================================================
// State
// ============================================================================
let agents=[], ollamaModels=[], pfStatus={}, agencyAgents=[], appSettings={};
let currentPanel='dash', configPanel='agents';
let currentReport=null;

// ============================================================================
// Init
// ============================================================================
async function init(){
  await Promise.all([checkStatus(), loadModels(), loadAgents(), loadAgency(), loadAppSettings()]);
  nav('dash');
}

async function checkStatus(){
  try{
    const r=await fetch('/api/status');const d=await r.json();
    el('dotOllama').className='dot '+(d.ollama?'dot-on':'dot-off');
    el('txtOllama').textContent='ollama '+(d.ollama?'ok':'offline');
    el('dotPf').className='dot '+(d.promptfoo?'dot-on':'dot-warn');
    el('txtPf').textContent='promptfoo '+(d.promptfoo_version||'missing');
    el('dotAgency').className='dot '+(d.agents_count>0?'dot-on':'dot-off');
    el('txtAgency').textContent=d.agents_count+' agents';
    pfStatus=d;
  }catch(e){}
}
async function loadModels(){try{const r=await fetch('/api/models');const d=await r.json();ollamaModels=d.models||[];}catch(e){ollamaModels=[];}}
async function loadAgents(){try{const r=await fetch('/api/agents');agents=await r.json();}catch(e){agents=[];}}
async function loadAgency(){try{const r=await fetch('/api/agency');agencyAgents=await r.json();}catch(e){agencyAgents=[];}}
async function loadAppSettings(){try{const r=await fetch('/api/settings');appSettings=await r.json();}catch(e){appSettings={};}}

// ============================================================================
// Navigation
// ============================================================================
function el(id){return document.getElementById(id)}

function nav(panel){
  currentPanel=panel;
  if(simPollInterval&&panel!=='predict'){stopPolling();}
  document.querySelectorAll('.nav-item').forEach((n,i)=>{
    const panels=['dash','predict','history','promptfoo','configure'];
    n.classList.toggle('active',panels[i]===panel);
  });
  const m=el('mainContent');
  const renderers={dash:renderDash,predict:renderPredict,history:renderHistory,promptfoo:renderPromptFoo,configure:renderConfigure};
  (renderers[panel]||renderDash)(m);
}

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}

// ============================================================================
// Dashboard
// ============================================================================
function renderDash(m){
  checkStatus();
  const ollamaOk=pfStatus.ollama;
  const modelStr=ollamaModels.length?ollamaModels.slice(0,3).join(', ')+(ollamaModels.length>3?' +more':''):'none found';
  const pfVer=pfStatus.promptfoo?(pfStatus.promptfoo_version||'ok'):'not installed';
  const agCnt=pfStatus.agents_count||0;
  m.innerHTML=`
  <div class="page-header"><h2>Dashboard</h2><p>Your AI toolkit status and quick navigation</p></div>
  <div class="status-bar">
    <div class="status-pill"><div class="sp-dot-wrap"><div class="dot ${ollamaOk?'dot-on':'dot-off'}"></div></div><div><div class="sp-label">Ollama</div><div class="sp-val" style="color:${ollamaOk?'var(--acc)':'var(--red)'}">${ollamaOk?'Connected':'Offline'}</div></div></div>
    <div class="status-pill"><div class="sp-dot-wrap"><div class="dot ${ollamaModels.length?'dot-on':'dot-warn'}"></div></div><div><div class="sp-label">Models</div><div class="sp-val">${esc(modelStr)}</div></div></div>
    <div class="status-pill"><div class="sp-dot-wrap"><div class="dot ${agCnt>0?'dot-on':'dot-off'}"></div></div><div><div class="sp-label">Agent Personas</div><div class="sp-val">${agCnt} installed</div></div></div>
    <div class="status-pill"><div class="sp-dot-wrap"><div class="dot ${pfStatus.promptfoo?'dot-on':'dot-warn'}"></div></div><div><div class="sp-label">PromptFoo</div><div class="sp-val">${esc(pfVer)}</div></div></div>
  </div>
  <div class="dash-hero" onclick="nav('predict')">
    <div class="dash-hero-inner">
      <div class="dash-hero-text">
        <div style="margin-bottom:8px"><span class="dc-badge badge-interactive">Interactive</span></div>
        <div class="dash-hero-title">MiniFish Predictions</div>
        <div class="dash-hero-desc">The main thing you run here. Paste a topic or question, pick your analyst agents, and watch them debate in real time. The moderator synthesizes a structured prediction report at the end. All runs locally via Ollama.</div>
        <div class="dash-hero-action">Open MiniFish &rarr;</div>
      </div>
    </div>
  </div>
  <div class="dash-cards">
    <div class="dash-card" onclick="nav('history')">
      <div class="dc-badge badge-interactive">History</div>
      <div class="dc-title">Prediction Reports</div>
      <div class="dc-desc">Browse, view, and export all your saved MiniFish prediction reports.</div>
      <div class="dc-action">View History &rarr;</div>
    </div>
    <div class="dash-card" onclick="nav('promptfoo')">
      <div class="dc-badge badge-ondemand">On Demand</div>
      <div class="dc-title">PromptFoo Testing</div>
      <div class="dc-desc">Only relevant if you build apps that make LLM calls. Write test configs and run evals or red-team security scans against your prompts.</div>
      <div class="dc-action">Test Prompts &rarr;</div>
    </div>
    <div class="dash-card" onclick="nav('configure')">
      <div class="dc-badge badge-alwayson">Always On</div>
      <div class="dc-title">Agency + Impeccable</div>
      <div class="dc-desc">${agCnt} agent personas and 17 design commands are installed globally in <span style="font-family:var(--mono);color:var(--acc);font-size:11px">~/.claude/agents/</span>. Active in every Claude Code session on your Mac. Nothing to run.</div>
      <div class="dc-action">Browse &rarr;</div>
    </div>
  </div>`;
}

// ============================================================================
// MiniFish
// ============================================================================
function renderPredict(m){
  const defModel=appSettings.default_model||'';
  const defAgents=appSettings.default_agents||5;
  const defRounds=appSettings.default_rounds||2;
  const modelOpts=ollamaModels.map(x=>`<option value="${esc(x)}" ${(defModel?x===defModel:x.includes('llama3.1'))?'selected':''}>${esc(x)}</option>`).join('');
  const chipHtml=agents.map((a,i)=>`<div class="agent-chip ${i<defAgents?'on':''}" data-id="${esc(a.id)}" onclick="this.classList.toggle('on')"><span class="chip-dot" style="background:${a.color}"></span>${a.emoji} ${esc(a.name)}</div>`).join('');
  m.innerHTML=`
  <div class="page-header"><h2>MiniFish</h2><p>Multi-agent prediction engine. Select agents, enter a topic, run the debate.</p></div>
  <div class="predict-layout">
    <div class="predict-controls">
      <div class="card" style="margin-bottom:0">
        <div class="input-group">
          <label class="field-label">Topic or question</label>
          <textarea id="topic" rows="4" placeholder="Will AI replace frontend developers by 2028?&#10;&#10;Or paste a news article, product idea, or market question..."></textarea>
        </div>
        <div class="row">
          <div class="input-group">
            <label class="field-label">Model</label>
            <select id="model">${modelOpts||'<option value="">no models found</option>'}</select>
          </div>
          <div class="input-group">
            <label class="field-label">Rounds &nbsp;<span id="rcD" style="color:var(--acc)">${defRounds}</span></label>
            <div class="range-row"><input type="range" id="rc" min="1" max="5" value="${defRounds}" oninput="el('rcD').textContent=this.value"></div>
          </div>
        </div>
        <div class="input-group">
          <label class="field-label">Agents &mdash; click to toggle</label>
          <div class="agent-grid" id="agentGrid">${chipHtml}</div>
        </div>
        <button class="btn btn-primary btn-full" id="runBtn" onclick="runSim()">Run Prediction</button>
        ${ollamaModels.length===0?'<div class="no-model-warn">No models found. Run: ollama pull llama3.1:8b</div>':''}
      </div>
    </div>
    <div>
      <div class="feed" id="feed">
        <div class="feed-empty"><div class="fe-icon">&#9733;</div>Select agents and run a prediction<br>to see the debate here.</div>
      </div>
    </div>
  </div>`;
}

let simPollInterval=null, simPollIdx=0;

function stopPolling(){
  if(simPollInterval){clearInterval(simPollInterval);simPollInterval=null;}
  simPollIdx=0;
}

async function runSim(){
  const topic=el('topic').value.trim();if(!topic)return;
  const model=el('model').value;
  const rounds=+el('rc').value;
  const sel=[];document.querySelectorAll('#agentGrid .agent-chip.on').forEach(c=>sel.push(c.dataset.id));
  if(sel.length<3){alert('Select at least 3 agents');return;}
  el('runBtn').disabled=true;el('runBtn').textContent='Running...';
  el('feed').innerHTML='';
  stopPolling();
  try{
    const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic,model,agents:sel,rounds})});
    const d=await r.json();
    if(d.error){el('runBtn').disabled=false;el('runBtn').textContent='Run Prediction';alert(d.error);return;}
    simPollIdx=0;
    simPollInterval=setInterval(pollEvents,400);
  }catch(e){el('runBtn').disabled=false;el('runBtn').textContent='Run Prediction';}
}

async function pollEvents(){
  try{
    const r=await fetch(`/api/events?since=${simPollIdx}`);
    const evts=await r.json();
    for(const evt of evts){handleSimEvent(evt);simPollIdx++;}
  }catch(e){}
}

function handleSimEvent(evt){
  const f=el('feed');if(!f)return;
  if(evt.type==='phase') f.innerHTML+=`<div class="phase-div">${esc(evt.data.name)}</div>`;
  else if(evt.type==='thinking'){const p=document.getElementById('thk');if(p)p.remove();f.innerHTML+=`<div class="thinking" id="thk"><div class="dots"><span></span><span></span><span></span></div>${esc(evt.data.name)} thinking...</div>`;}
  else if(evt.type==='response'){const p=document.getElementById('thk');if(p)p.remove();f.innerHTML+=`<div class="msg" style="border-left-color:${evt.data.color}"><div class="msg-head"><span class="msg-name" style="color:${evt.data.color}">${evt.data.emoji} ${esc(evt.data.name)}</span><span class="msg-time">${evt.data.time}s</span></div><div class="msg-text">${esc(evt.data.text)}</div></div>`;f.scrollIntoView({block:'end',behavior:'smooth'});}
  else if(evt.type==='report'){const p=document.getElementById('thk');if(p)p.remove();currentReport=evt.data;f.innerHTML+=`<div class="report-box"><h3>Prediction Report</h3><div class="report-text">${fmtReport(evt.data.text)}</div><div style="margin-top:14px"><button class="btn btn-ghost btn-sm" onclick="exportMd()">Export Markdown</button></div></div>`;f.scrollIntoView({block:'end',behavior:'smooth'});}
  else if(evt.type==='done'){stopPolling();const b=el('runBtn');if(b){b.disabled=false;b.textContent='Run Prediction';}}
}

function fmtReport(t){return t.replace(/## (.*)/g,'<strong style="color:var(--acc);font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:1px;display:block;margin-top:14px;margin-bottom:2px">$1</strong>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>')}

function exportMd(){
  if(!currentReport)return;
  const md=`# MiniFish Prediction Report\n\n${currentReport.text||currentReport.report||''}`;
  const b=new Blob([md],{type:'text/markdown'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=`minifish-${Date.now()}.md`;a.click();
}

// ============================================================================
// History
// ============================================================================
function renderHistory(m){
  m.innerHTML=`<div class="page-header"><h2>History</h2><p>Saved MiniFish prediction reports</p></div><div id="histList"><div class="empty">Loading...</div></div>`;
  fetch('/api/reports').then(r=>r.json()).then(reps=>{
    const h=el('histList');
    if(!reps.length){h.innerHTML='<div class="empty">No predictions yet. Run one in MiniFish.</div>';return;}
    h.innerHTML=reps.reverse().map(r=>`<div class="hist-item" onclick="viewReport('${r.id}')"><div class="hist-date">${new Date(r.timestamp).toLocaleString()}</div><div class="hist-topic">${esc(r.topic)}</div><div class="hist-meta">${r.agents.length}a &middot; ${r.rounds}r</div></div>`).join('');
  });
}

async function viewReport(id){
  const r=await fetch(`/api/report/${id}`);const d=await r.json();currentReport=d;
  el('modalBody').innerHTML=`<h2>Prediction Report</h2><div style="color:var(--text-3);font-family:var(--mono);font-size:12px;margin-bottom:14px">${esc(d.topic)}</div><div class="report-text">${fmtReport(d.report)}</div><div style="margin-top:16px"><button class="btn btn-ghost btn-sm" onclick="exportMd()">Export Markdown</button></div>`;
  el('modal').classList.add('open');
}
function closeModal(){el('modal').classList.remove('open')}

// ============================================================================
// PromptFoo
// ============================================================================
function renderPromptFoo(m){
  m.innerHTML=`
  <div class="page-header"><h2>PromptFoo</h2><p>Test and red-team LLM prompts in apps you build. Edit a config file, then run an eval or security scan.</p></div>
  <div class="card">
    <div class="card-header"><div class="card-title">Config Files</div></div>
    <div id="pfConfigs">Loading...</div>
  </div>
  <div class="card">
    <div class="card-header"><div class="card-title">Editor</div><div><button class="btn btn-ghost btn-sm" onclick="savePfConfig()">Save</button></div></div>
    <select id="pfFile" onchange="loadPfFile()" style="margin-bottom:10px"></select>
    <textarea id="pfEditor" class="code-textarea" placeholder="Select a config file above..."></textarea>
  </div>
  <div class="card">
    <div class="card-header"><div class="card-title">Run</div></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button class="btn btn-primary btn-sm" id="pfRunBtn" onclick="runPf('eval')">Run Eval</button>
      <button class="btn btn-ghost btn-sm" onclick="runPf('redteam')">Run Red-Team</button>
      <button class="btn btn-ghost btn-sm" onclick="openPfView()">Open Results UI</button>
    </div>
    <div id="pfOutput" class="pf-run-output" style="display:none"></div>
  </div>`;
  fetch('/api/promptfoo/configs').then(r=>r.json()).then(cfgs=>{
    el('pfConfigs').innerHTML=cfgs.map(c=>`<div style="font-family:var(--mono);font-size:12px;padding:3px 0;color:var(--text-2)">${c.file} <span style="color:var(--text-3);font-size:10px">(${(c.size/1024).toFixed(1)}kb)</span></div>`).join('')||'<div class="empty">No configs found in configs/promptfoo/</div>';
    const sel=el('pfFile');sel.innerHTML=cfgs.map(c=>`<option value="${esc(c.file)}">${esc(c.file)}</option>`).join('');
    if(cfgs.length)loadPfFile();
  });
}

async function loadPfFile(){
  const f=el('pfFile').value;if(!f)return;
  const r=await fetch(`/api/promptfoo/config/${f}`);const t=await r.text();
  el('pfEditor').value=t;
}

async function savePfConfig(){
  const f=el('pfFile').value;const c=el('pfEditor').value;if(!f)return;
  await fetch(`/api/promptfoo/config/${f}`,{method:'POST',headers:{'Content-Type':'text/plain'},body:c});
  alert('Saved!');
}

async function runPf(type){
  const b=el('pfRunBtn');b.disabled=true;b.textContent='Running...';
  const out=el('pfOutput');out.style.display='block';out.textContent='Running promptfoo... this may take a minute.\n';
  try{
    const file=el('pfFile').value||(type==='redteam'?'redteam-config.yaml':'eval-config.yaml');
    const r=await fetch(`/api/promptfoo/run/${file}`,{method:'POST'});
    const d=await r.json();
    if(d.parsed){out.textContent=fmtPfResults(d);}
    else{out.textContent=d.success?'Completed.\n\n'+d.stdout:'Failed:\n\n'+d.stderr+'\n\n'+d.stdout;}
  }catch(e){out.textContent='Error: '+e;}
  b.disabled=false;b.textContent='Run Eval';
}

function fmtPfResults(d){
  const pct=d.total?Math.round(d.passes/d.total*100):0;
  let s=`Results: ${d.passes}/${d.total} passed (${pct}%)\n${'='.repeat(40)}\n\n`;
  (d.results||[]).forEach((r,i)=>{
    s+=`${r.pass?'[PASS]':'[FAIL]'} Test ${i+1}: ${r.prompt.slice(0,80)}\n`;
    if(r.output) s+=`  Output: ${r.output.slice(0,120)}\n`;
    if(!r.pass&&r.error) s+=`  Error: ${r.error.slice(0,120)}\n`;
    s+='\n';
  });
  return s;
}

async function openPfView(){
  const r=await fetch('/api/promptfoo/view',{method:'POST'});
  const d=await r.json();
  if(d.error){alert('PromptFoo not found. Run: npm install -g promptfoo');return;}
  setTimeout(()=>window.open('http://localhost:15500','_blank'),1500);
}

// ============================================================================
// Configure (inner tabs: Agents, Design, Personas, Settings)
// ============================================================================
function renderConfigure(m){
  const tabs=['agents','design','personas','settings'];
  const labels=['Agents','Design','Personas','Settings'];
  const tabHtml=tabs.map((t,i)=>`<div class="itab ${configPanel===t?'active':''}" onclick="setConfigPanel('${t}')">${labels[i]}</div>`).join('');
  m.innerHTML=`
  <div class="page-header"><h2>Configure</h2><p>Agent personas, design commands, MiniFish agents, and settings</p></div>
  <div class="itab-nav">${tabHtml}</div>
  <div id="configBody"></div>`;
  renderConfigBody();
}

function setConfigPanel(p){
  configPanel=p;
  const tabs=['agents','design','personas','settings'];
  document.querySelectorAll('.itab').forEach((t,i)=>t.classList.toggle('active',tabs[i]===p));
  renderConfigBody();
}

function renderConfigBody(){
  const cb=el('configBody');if(!cb)return;
  const fns={agents:renderAgentsPanel,design:renderDesignPanel,personas:renderPersonasPanel,settings:renderSettingsPanel};
  (fns[configPanel]||renderAgentsPanel)(cb);
}

// --- Agents panel ---
function renderAgentsPanel(m){
  m.innerHTML=`
  <div style="margin-bottom:12px;font-size:13px;color:var(--text-2);line-height:1.6">
    These personas are installed in <span style="font-family:var(--mono);color:var(--acc);font-size:12px">~/.claude/agents/</span> and active in every Claude Code session on your Mac. Claude Code automatically applies the right specialist when it detects relevant work.
  </div>
  <div class="input-group"><input type="text" id="agencySearch" placeholder="Search ${agencyAgents.length} agents..." oninput="filterAgency()"></div>
  <div id="agencyList"></div>`;
  renderAgencyList(agencyAgents);
}

function renderAgencyList(list){
  el('agencyList').innerHTML=list.map(a=>`<div class="agency-item" onclick="viewAgentFile('${esc(a.file)}')"><div style="flex:1"><div class="agency-name">${esc(a.title)}</div><div class="agency-preview">${esc(a.preview)}</div></div><div class="agency-file">${esc(a.file)}</div></div>`).join('')||'<div class="empty">No agents found. Run ./setup.sh first.</div>';
}

function filterAgency(){
  const q=el('agencySearch').value.toLowerCase();
  renderAgencyList(agencyAgents.filter(a=>a.title.toLowerCase().includes(q)||a.file.toLowerCase().includes(q)||a.preview.toLowerCase().includes(q)));
}

async function viewAgentFile(file){
  const r=await fetch(`/api/agency/${file}`);const t=await r.text();
  el('modalBody').innerHTML=`<h2>${esc(file)}</h2><pre style="white-space:pre-wrap;font-family:var(--mono);font-size:12px;color:var(--text-2);line-height:1.6;max-height:60vh;overflow-y:auto">${esc(t)}</pre>`;
  el('modal').classList.add('open');
}

// --- Design panel (Impeccable) ---
function renderDesignPanel(m){
  m.innerHTML=`
  <div style="margin-bottom:14px;font-size:13px;color:var(--text-2);line-height:1.6">
    Slash commands to use when prompting Claude Code to build or improve UI. Click any command to copy it, then paste it in a Claude Code conversation.
  </div>
  <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap">
    <button class="btn btn-sm btn-primary" onclick="filterImp('all')">All</button>
    <button class="btn btn-sm btn-ghost" onclick="filterImp('quality')">Quality</button>
    <button class="btn btn-sm btn-ghost" onclick="filterImp('simplify')">Simplify</button>
    <button class="btn btn-sm btn-ghost" onclick="filterImp('style')">Style</button>
    <button class="btn btn-sm btn-ghost" onclick="filterImp('enhance')">Enhance</button>
  </div>
  <div class="imp-grid" id="impGrid"><div class="empty">Loading...</div></div>
  <div class="card" style="margin-top:20px">
    <div class="card-title">Anti-patterns (always active via CLAUDE.md)</div>
    <div style="margin-top:10px;font-size:12px;color:var(--text-2);line-height:1.9;font-family:var(--mono)">
      Never Inter, Roboto, Arial, or system-ui as display fonts<br>
      Never purple-on-white gradient hero sections<br>
      Never uniform rounded rectangles with drop shadows everywhere<br>
      Never bounce or elastic easing on UI elements<br>
      Never pure #000 text on pure #FFF background<br>
      Never evenly distributed pastels with no dominant accent<br>
      Never card grids with no visual hierarchy
    </div>
  </div>`;
  fetch('/api/impeccable').then(r=>r.json()).then(cmds=>{
    el('impGrid').innerHTML=cmds.map(c=>`<div class="imp-card" data-cat="${c.category}" onclick="copyCmd('${c.cmd}')"><div class="imp-cmd">${c.cmd}</div><div class="imp-desc">${c.desc}</div><div class="imp-cat cat-${c.category}">${c.category}</div></div>`).join('');
  });
}

function filterImp(cat){
  document.querySelectorAll('.imp-card').forEach(c=>{c.style.display=(cat==='all'||c.dataset.cat===cat)?'block':'none'});
}

function copyCmd(cmd){
  navigator.clipboard.writeText(cmd+' ').then(()=>{
    const t=document.createElement('div');t.textContent=cmd+' copied!';t.style.cssText='position:fixed;bottom:20px;right:20px;background:var(--acc);color:var(--bg-0);padding:10px 20px;border-radius:8px;font-family:var(--mono);font-size:13px;z-index:999;animation:fadeUp .3s ease';
    document.body.appendChild(t);setTimeout(()=>t.remove(),1500);
  });
}

// --- Personas panel (MiniFish agents) ---
function renderPersonasPanel(m){
  m.innerHTML=`
  <div style="margin-bottom:14px;font-size:13px;color:var(--text-2)">Customize the analyst agents used in MiniFish predictions.</div>
  <div id="personaEditor"></div>
  <div style="display:flex;gap:8px;margin-top:16px">
    <button class="btn btn-primary btn-sm" onclick="addPersona()">+ Add Agent</button>
    <button class="btn btn-ghost btn-sm" onclick="resetPersonas()">Reset Defaults</button>
  </div>`;
  renderPersonaCards();
}

function renderPersonaCards(){
  const ed=el('personaEditor');if(!ed)return;
  ed.innerHTML=agents.map((a,i)=>`
  <div class="edit-card">
    <div class="edit-head">
      <input type="text" value="${esc(a.emoji)}" style="width:50px;text-align:center" onchange="agents[${i}].emoji=this.value;savePersonas()">
      <input type="text" value="${esc(a.name)}" onchange="agents[${i}].name=this.value;savePersonas()">
      <input type="color" class="edit-color" value="${a.color}" onchange="agents[${i}].color=this.value;savePersonas()">
      <button class="btn btn-ghost btn-sm" style="color:var(--red)" onclick="rmPersona(${i})">Remove</button>
    </div>
    <textarea onchange="agents[${i}].system=this.value;savePersonas()" style="font-size:12px;min-height:50px">${esc(a.system)}</textarea>
  </div>`).join('');
}

function addPersona(){
  if(agents.length>=10){alert('Max 10 agents');return;}
  agents.push({id:'custom_'+Date.now(),name:'New Agent',emoji:'\u2b50',color:'#6b7280',system:'You are a helpful analyst. Keep responses to 2-3 sentences.'});
  renderPersonaCards();savePersonas();
}
function rmPersona(i){
  if(agents.length<=3){alert('Minimum 3 agents');return;}
  agents.splice(i,1);renderPersonaCards();savePersonas();
}
async function savePersonas(){
  await fetch('/api/agents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(agents)});
}
async function resetPersonas(){
  if(!confirm('Reset all personas to defaults?'))return;
  await fetch('/api/agents/reset',{method:'POST'});await loadAgents();renderPersonaCards();
}

// --- Settings panel ---
function renderSettingsPanel(m){
  m.innerHTML=`<div id="settingsCard"><div class="empty">Loading...</div></div>`;
  fetch('/api/settings').then(r=>r.json()).then(s=>{
    const modelOpts=['<option value="">Auto-select</option>',...ollamaModels.map(x=>`<option value="${esc(x)}" ${x===(s.default_model||'')?'selected':''}>${esc(x)}</option>`)].join('');
    el('settingsCard').innerHTML=`
    <div class="input-group"><label class="field-label">Ollama URL</label><input type="text" id="setUrl" value="${esc(s.ollama_url||'http://localhost:11434')}"></div>
    <div class="input-group"><label class="field-label">Default Model</label><select id="setModel">${modelOpts}</select></div>
    <div class="row">
      <div class="input-group"><label class="field-label">Default Agents &nbsp;<span id="sdaD" style="color:var(--acc)">${s.default_agents||5}</span></label><div class="range-row"><input type="range" id="sda" min="3" max="7" value="${s.default_agents||5}" oninput="el('sdaD').textContent=this.value"></div></div>
      <div class="input-group"><label class="field-label">Default Rounds &nbsp;<span id="sdrD" style="color:var(--acc)">${s.default_rounds||2}</span></label><div class="range-row"><input type="range" id="sdr" min="1" max="5" value="${s.default_rounds||2}" oninput="el('sdrD').textContent=this.value"></div></div>
    </div>
    <button class="btn btn-primary" onclick="saveSettings()">Save Settings</button>
    <div style="margin-top:10px;font-size:12px;color:var(--text-3)">Ollama URL change takes effect after restarting forge.py.</div>`;
  });
}

async function saveSettings(){
  const s={
    ollama_url: el('setUrl').value.trim()||'http://localhost:11434',
    default_model: el('setModel').value,
    default_agents: +el('sda').value,
    default_rounds: +el('sdr').value,
  };
  await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)});
  appSettings=s;
  const btn=event.target;btn.textContent='Saved!';setTimeout(()=>btn.textContent='Save Settings',1500);
}

// ============================================================================
// Start
// ============================================================================
init();
</script>
</body>
</html>"""

# ============================================================================
# Server
# ============================================================================

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass

    def j(self,d,s=200):
        self.send_response(s);self.send_header("Content-Type","application/json");self.send_header("Access-Control-Allow-Origin","*");self.end_headers();self.wfile.write(json.dumps(d).encode())

    def t(self,d,s=200):
        self.send_response(s);self.send_header("Content-Type","text/plain");self.end_headers();self.wfile.write(d.encode())

    def body(self):
        cl=int(self.headers.get("Content-Length",0));return self.rfile.read(cl) if cl else b"{}"

    def do_GET(self):
        p=self.path.split("?")[0]
        if p=="/": self.send_response(200);self.send_header("Content-Type","text/html");self.end_headers();self.wfile.write(HTML.encode())
        elif p=="/api/status":
            o=ollama_get("/api/tags") is not None
            pf=get_promptfoo_status()
            ac=len(scan_agency_agents())
            self.j({"ollama":o,"promptfoo":pf["installed"],"promptfoo_version":pf.get("version"),"agents_count":ac})
        elif p=="/api/models":
            d=ollama_get("/api/tags");ms=[m.get("name","") for m in (d or{}).get("models",[])] if d else []
            self.j({"models":ms})
        elif p=="/api/agents": self.j(load_agents())
        elif p=="/api/agency": self.j(scan_agency_agents())
        elif p.startswith("/api/agency/"):
            fn=p.split("/api/agency/")[1]
            txt=read_agent_file(fn)
            if txt: self.t(txt)
            else: self.j({"error":"not found"},404)
        elif p.startswith("/api/events"):
            since=0
            if "since=" in self.path:
                try: since=int(self.path.split("since=")[1])
                except: pass
            with sim_state["lock"]: evts=sim_state["events"][since:]
            self.j(evts)
        elif p=="/api/reports":
            reps=[]
            for f in sorted(REPORTS_DIR.glob("*.json")):
                try:
                    d=json.loads(f.read_text())
                    reps.append({"id":d.get("id"),"topic":d.get("topic","")[:120],"agents":d.get("agents",[]),"rounds":d.get("rounds",0),"timestamp":d.get("timestamp")})
                except: pass
            self.j(reps)
        elif p.startswith("/api/report/"):
            rid=p.split("/api/report/")[1];rp=REPORTS_DIR/f"{rid}.json"
            if rp.exists(): self.j(json.loads(rp.read_text()))
            else: self.j({"error":"not found"},404)
        elif p=="/api/promptfoo/configs": self.j(get_promptfoo_configs())
        elif p.startswith("/api/promptfoo/config/"):
            fn=p.split("/api/promptfoo/config/")[1]
            txt=read_config_file(fn)
            if txt: self.t(txt)
            else: self.j({"error":"not found"},404)
        elif p=="/api/impeccable": self.j(IMPECCABLE_COMMANDS)
        elif p=="/api/settings": self.j(APP_SETTINGS)
        elif p=="/api/stream":
            self._sse_stream()
        else: self.send_response(404);self.end_headers()

    def do_POST(self):
        p=self.path;b=self.body()
        if p=="/api/run":
            if sim_state["running"]: self.j({"error":"already running"},409);return
            d=json.loads(b);threading.Thread(target=run_simulation,args=(d.get("topic",""),d.get("model","llama3.2"),d.get("agents",[]),min(max(int(d.get("rounds",2)),1),5)),daemon=True).start()
            self.j({"status":"started"})
        elif p=="/api/agents": save_agents(json.loads(b));self.j({"ok":True})
        elif p=="/api/agents/reset": save_agents(DEFAULT_AGENTS);self.j({"ok":True})
        elif p.startswith("/api/promptfoo/config/"):
            fn=p.split("/api/promptfoo/config/")[1];write_config_file(fn,b.decode());self.j({"ok":True})
        elif p.startswith("/api/promptfoo/run/"):
            fn=p.split("/api/promptfoo/run/")[1];cfg=str(FORGE_DIR/"configs"/"promptfoo"/fn)
            self.j(run_promptfoo_eval(cfg))
        elif p=="/api/promptfoo/view":
            pf=find_promptfoo()
            if pf:
                subprocess.Popen([pf,"view","--port","15500"],cwd=str(FORGE_DIR),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.j({"ok":True,"url":"http://localhost:15500"})
            else:
                self.j({"error":"promptfoo not found"},404)
        elif p=="/api/settings":
            try:
                d=json.loads(b);APP_SETTINGS.update(d);save_settings(APP_SETTINGS);self.j({"ok":True})
            except: self.j({"error":"invalid json"},400)
        else: self.send_response(404);self.end_headers()

    def _sse_stream(self):
        """Server-Sent Events endpoint for MiniFish simulation streaming."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_idx = 0
        try:
            for _ in range(150):
                with sim_state["lock"]:
                    if sim_state["running"] or len(sim_state["events"]) > 0:
                        break
                time.sleep(0.1)
            while True:
                with sim_state["lock"]:
                    evts = sim_state["events"][last_idx:]
                    running = sim_state["running"]
                for evt in evts:
                    data = json.dumps(evt)
                    self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    last_idx += 1
                if not running and last_idx >= len(sim_state["events"]) and last_idx > 0:
                    self.wfile.write(b'data: {"type":"stream_end"}\n\n')
                    self.wfile.flush()
                    break
                time.sleep(0.1)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def do_OPTIONS(self):
        self.send_response(200);self.send_header("Access-Control-Allow-Origin","*");self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS");self.send_header("Access-Control-Allow-Headers","Content-Type");self.end_headers()


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    print(f"""
  +=======================================+
  |           AI FORGE v1                 |
  |  Unified AI Developer Toolkit         |
  +=======================================+
  |  Server:  http://localhost:{PORT}       |
  |  Ollama:  {get_ollama_url()}       |
  +=======================================+
    """)
    with ThreadingServer(("",PORT),Handler) as s:
        try: s.serve_forever()
        except KeyboardInterrupt: print("\nShutting down.");s.shutdown()


if __name__=="__main__":
    main()
