# Project: Agentic PRD Factory Orchestrator

## Objective

Build a CLI / Web tool that automates rigorous product strategy by orchestrating 13 expert AI agents through a 3-round consensus-building process. The output is a Product Requirements Document (PRD) that has been pressure-tested across every product dimension - Product Owner mediation, Architecture, Finance, Marketing, Sales, Business Analysis, Engineering, QA, UI/UX, Security, Voice-of-Customer, Legal, Data/Analytics - before any commitment to build is made.

The orchestrator's job is to make sure the right *opportunity* gets built the right *way*, before scarce build-time goes into the wrong direction. It supersedes single-thread strategic decisions; for any directional product call, the factory's output is the canonical answer.

## Operating Principles

### 1. Explore before constraining

The biggest failure mode of any agent system is **assuming an answer the moment a question is asked**. Agents must FIRST exercise the design space (research alternatives, name what's been tried elsewhere, surface options the prompt didn't suggest) BEFORE settling on a recommendation. Pattern-matching to the first plausible answer is forbidden.

**Concretely:** for every architectural / scope / monetization / GTM question, the responsible agent must produce at minimum 3 candidate options with honest pros/cons before recommending one. If only one option is named, the agent has not done the work.

### 2. Priorities, not blockers

The priorities defined in your product context are **strong defaults**, not absolute blockers. An agent may propose options that violate a priority IF AND ONLY IF the agent has first explored alternatives that honor the priority and shown why they fall short. Naked priority-violation without exploration is rejected; well-reasoned priority-override is welcomed.

### 3. Multi-agent consensus over single-agent authority

No single agent owns any decision outright. The Product Owner mediates; the 3-round consensus surfaces disagreement; the conflict matrix resolves it. Even when one agent is the natural lead (e.g., Architect on tech stack), other agents' dissents must be heard and recorded.

### 4. Dissents and alternatives are first-class outputs

The PRD output captures not just the recommended path but also the alternatives considered and the reasons they lost. Future iterations or strategy shifts can re-read these and re-evaluate. "Decisions" without recorded alternatives are forbidden - they make future re-evaluation impossible.

### 5. The trump filter (above all priorities)

Every recommendation must pass two tests:
- **Strategic fit:** does it serve the product's actual goal? Vanity metrics don't count; real progress toward the stated objective does.
- **Viability:** is it sustainable and affordable for the organization building it? Ideas the org cannot fund or operate fail this test regardless of how exciting they sound.

If either test fails, the recommendation is rejected regardless of other agent enthusiasm.

## Strategic Priorities (EXAMPLE - replace with your own in `product_context.md`)

The section below is an illustrative example only. Define your own audience, positioning, delivery, infrastructure, monetization, and methodology priorities in `product_context.md` - the factory reads that file and injects it into every agent.

### Audience (example)
People who need to understand medication labels and instructions in plain language, plus the caregivers and helpers who support them.

### Positioning (example)
An educational tool that explains what a label or instruction says in clearer terms. It is EDUCATIONAL only - not diagnosis, screening, or medical advice. Never use regulated verbs (diagnose, screen, treat, prescribe); always direct the user to a licensed professional for actual decisions.

### Delivery, infrastructure, monetization (example)
Choose the surface, infrastructure, and business model that fit the audience and the org's constraints. Validate before committing to an expensive build; prefer the cheapest reachable form that reaches real users first.

## Conflict Resolution

See `conflict_matrix.md` for the explicit rules (UX vs Security -> PO Decides, Sales vs Engineering -> MVP wins, etc.). When the matrix doesn't cover a conflict, escalate to the Product Owner agent's mediation, then if still unresolved, surface to the human decision-maker.

## Output Format

Each pipeline run produces:
1. A scored opportunity assessment (does this pass the trump filter? what's the LTV/CAC math? what's the regulatory exposure?)
2. A PRD covering the 13 dimensions (see `prd_template.md`)
3. Recorded alternatives + reasons-lost for major decisions
4. A confidence-tagged recommendation: GO / NO-GO / NEEDS-MORE-VALIDATION

## When NOT to use the factory

The factory is for direction-setting decisions (new product evaluation, major architecture choice, monetization model, GTM strategy). For tactical work (writing copy, responding to a support ticket within existing strategy, fixing a specific bug), single-agent (or single-developer) execution is fine. Rigor should be proportional to reversibility - irreversible direction-setting decisions get full factory treatment; small reversible tactical work doesn't.
