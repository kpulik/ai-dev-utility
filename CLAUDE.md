# AI Dev Utility - Global Claude Code Rules

## Agent System

When asked to work on a specific domain, load the appropriate agent persona from ~/.claude/agents/ before proceeding. Key agents available:

- Backend work -> backend-architect
- Frontend work -> frontend-developer
- Security review -> security-engineer
- Testing -> quality-assurance
- Deployment -> devops-engineer
- Design -> ux-designer
- Mobile -> mobile-developer
- Documentation -> technical-writer
- Analytics -> data-analyst
- Marketing -> growth-hacker

## Frontend Design Rules (via Impeccable)

When building any UI or frontend code:

1. NEVER use Inter, Roboto, or Arial fonts
2. NEVER use purple gradients on white backgrounds
3. NEVER use generic card-based layouts without personality
4. ALWAYS choose a bold aesthetic direction first
5. Use OKLCH color space for perceptually uniform colors
6. Prefer CSS custom properties for theming
7. Add purposeful animations (not decorative bounces)
8. Simpler is better: remove unnecessary complexity
9. Brand colors with intentional accent palette, not evenly distributed pastels
10. One memorable micro-interaction per component, not animations on everything

## Anti-Patterns (explicitly avoid these)

- Inter, Roboto, Arial, or system-ui as display fonts
- Purple-on-white gradient hero sections
- Uniform rounded rectangles with drop shadows everywhere
- Bounce or elastic easing on UI elements
- Pure black (#000) text on pure white (#FFF) backgrounds
- Evenly distributed pastel color palettes with no dominant accent
- Card grids that all look the same with no visual hierarchy
- Gray placeholder text on colored backgrounds (poor contrast)

## Code Quality

- Write tests alongside code
- Use TypeScript for all new code
- Follow security best practices (validate inputs, sanitize outputs)
- Keep functions small and composable
- Document public APIs
