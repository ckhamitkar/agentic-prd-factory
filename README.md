# Agentic PRD Factory

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

An agentic product-definition factory: a multi-agent LangGraph pipeline that pressure-tests an opportunity across 13 expert lenses - 3 rounds of consensus, a conflict matrix, and a human sign-off gate - and produces a decision-ready PRD before anything gets built.

> This is a sanitized release of the internal factory used at [Axion AI](https://www.axionaiapps.com) to turn product opportunities into vetted PRDs. The engine is intact; the private business context it scores against has been replaced with a generic, illustrative example (see [`product_context.md`](product_context.md)).

## How it works

The pipeline runs a panel of 13 role-agents (Product Owner, Architect, Engineering, QA, Finance, Marketing, Sales, Business Analyst, UI/UX, Security, Legal, User Proxy, Data/Analytics) through a structured protocol:

1. **Round 1 - Drafting.** Each agent drafts its section of the PRD from its own expertise.
2. **Round 2 - Consensus.** The Product Owner surfaces contradictions across the drafts and synthesizes a resolved V2 PRD.
3. **Round 3 - Sign-off.** Every agent formally reviews the consensus PRD and flags its domain risks Green / Yellow / Red.
4. **Round 4 - Financials and score.** Engineering and Finance estimates feed an ROI calculation and a composite Priority Score (Reach, Technical Feasibility, Business Viability), recorded to a running portfolio.

Conflicts are resolved through an explicit `conflict_matrix.md`; anything it doesn't cover escalates to the Product Owner, then to a human.

A **human sign-off gate** ("CEO approval") sits between the PRD and any build: the pipeline pauses for an approve / reject / request-clarification decision. On approval, an optional **development phase** breaks the PRD into features and runs dev, DevOps, QA, and documentation agents across sprints.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then add your API key(s)

# Run the factory on the included example (PRD only)
python -m src.main --opportunity examples/medication_guide_opportunity.txt --prd-only
```

Outputs land under `projects/<name>/` (drafts, PRD, executive summary, logs, and a portfolio view). A minimal web UI is also available via `python -m src.web`.

Two LLM providers are supported: Anthropic (`--provider anthropic`) and Google Gemini (`--provider gemini`). Set the corresponding key in `.env`.

## Define your own product context

Every agent evaluates ideas against the context in [`product_context.md`](product_context.md). The version in this repo is a generic, illustrative example (a plain-language, educational medication-information assistant). Replace it with your own - the goals, constraints, and priorities the factory should score opportunities against - and the whole panel reorients around it. `system_orchestrator.md` describes the operating principles the agents follow.

## License

MIT. The method is open; the business model you score against is yours.
