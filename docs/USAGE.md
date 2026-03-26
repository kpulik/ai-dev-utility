# AI Dev Utility Usage Guide

How to get the most out of each tool in your daily workflow.

## Using agent personas (The Agency)

Installed agent personas live in `~/.claude/agents/` (count depends on upstream; typically around 180). You don't invoke them manually; they're always available as context. Reference the role you need in your prompt:

```text
I need to design the database schema for a multi-tenant billing system.
Think like a backend architect. Use Supabase with Row Level Security.
```

```text
Review this auth flow for security vulnerabilities.
Think like a security engineer. Check for CSRF, session fixation, privilege escalation.
```

```text
Build the dashboard page. Think like a frontend developer and UX designer.
Follow the design rules in CLAUDE.md.
```

The agent personas give Claude Code specific deliverables, quality standards, and domain vocabulary for each role.

## Frontend design that doesn't look like AI slop (Impeccable)

Impeccable's rules are embedded in CLAUDE.md so they're always active. Claude Code will automatically avoid the common pitfalls: Inter font, purple gradients, generic card layouts, bounce animations.

When you want to push further, use these concepts directly in your prompts:

**Simplify:** "This page is too complex. Distill it down. Progressive disclosure, hide advanced options, reduce cognitive load."

**Brand it:** "Apply our brand colors: Navy #1B2B4B primary, Coral #FF6B6B accent, Cream #FFF8F0 background. Use the accent sparingly for CTAs only."

**Add personality:** "Add one memorable micro-interaction: when the user completes onboarding, stagger-animate the dashboard elements in from the edges."

**Quality check:** "Audit this component for accessibility (contrast ratios, keyboard nav, screen reader labels), responsive breakpoints, and missing states (loading, error, empty)."

The slash commands in the Configure > Design tab (e.g. `/colorize`, `/audit`, `/wow`) are shorthand for these concepts. Click any to copy it.

## Testing LLM prompts before shipping (PromptFoo)

Only relevant if your app makes LLM calls. Edit `configs/promptfoo/eval-config.yaml` with your actual prompts, then run evals to catch regressions. Red-team scans run via `./scripts/redteam.sh`.

To use Ollama as the judge (no API key needed), set this in the config:

```yaml
defaultTest:
  options:
    provider: ollama:chat:llama3.2
```

## When to use MiniFish

Use MiniFish when you want structured multi-perspective analysis on a question, idea, or decision. It's more useful than asking a single AI because the agents actively disagree with each other, which surfaces assumptions and blind spots. Good for:

- "Is this product idea worth building?"
- "How will this technology trend play out?"
- "What are the risks of this technical approach?"

Run it from the MiniFish tab in the dashboard, or via CLI: `python minifish/minifish.py "your question"`.

## Customizing CLAUDE.md for a project

When applying AI Dev Utility to a project with `./scripts/new-project.sh`, customize the generated `CLAUDE.md` with your project-specific details. The more specific it is, the better every AI interaction becomes:

```markdown
## What this project is
A task management SaaS for remote teams.

## Tech stack
Next.js 15, Supabase, Tailwind, deployed on Vercel.

## Design direction
Minimal and editorial. Dark mode primary. Monospace headings.
Accent color: electric blue #0066FF.
```

## Recommended companion stack

| Layer | Recommended |
| --- | --- |
| AI coding | Claude Code ($20/mo) |
| Frontend | Next.js + Tailwind |
| Backend | Next.js API routes or Hono |
| Database | Supabase (free tier) |
| Auth | Supabase Auth (free tier) |
| Hosting | Vercel (free tier) |
| AI in your app | Claude Haiku (paid) or Ollama (local) |
| Local LLM | Ollama with llama3.2 |
