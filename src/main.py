
import os
import argparse
from dotenv import load_dotenv

# Load environment variables (API Keys) - MUST BE FIRST
load_dotenv()

from src.graph.workflow import define_graph, define_prd_only_graph
from src.tools.io import read_opportunity, generate_portfolio_view
from src.state.state import CEODecision
from src.agents.factory import set_provider, DEFAULT_MODELS


def run_pipeline(
    opportunity_text,
    project_name,
    mode="prd_only",
    skip_ceo=False,
    provider="gemini",
    model=None,
    log_callback=None
):
    """Run the PRD Factory pipeline programmatically.

    Args:
        opportunity_text: The raw opportunity/idea text.
        project_name: Name for the project (used for output directories).
        mode: One of "prd_only", "prd_ceo", "full_dev".
        skip_ceo: Auto-approve CEO decision.
        provider: LLM provider ("anthropic" or "gemini").
        model: Specific model name, or None for provider default.
        log_callback: Optional callable(str) invoked with progress messages.

    Returns:
        dict with workflow result state.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    # Set the global LLM provider
    resolved_model = model or DEFAULT_MODELS.get(provider)
    set_provider(provider, resolved_model)

    log(f"Project: {project_name}")
    log(f"Provider: {provider.upper()} ({resolved_model})")
    log(f"Mode: {mode}")

    dev_mode = mode == "full_dev"
    prd_only = mode == "prd_only"

    # Initialize State with all fields
    initial_state = {
        # === Existing PRD Phase Fields ===
        "opportunity": opportunity_text,
        "project_name": project_name,
        "drafts": {},
        "critiques": [],
        "conflicts": [],
        "round": 0,
        "logs": [],
        "final_prd": "",
        "signoffs": {},
        "roi_data": {},
        "financial_report": "",

        # === Round 4: Priority Score ===
        "priority_score": 0.0,
        "score_breakdown": {},

        # === Marketing Plan ===
        "marketing_plan": "",

        # === Round 5: CEO Approval ===
        "ceo_decision": CEODecision.PENDING,
        "ceo_comments": "",
        "clarification_requests": [],
        "clarification_responses": {},
        "skip_ceo": skip_ceo,

        # === Development Phase ===
        "dev_phase_active": dev_mode,
        "features": [],
        "current_sprint_id": 0,
        "sprints": {},

        # === Sprint Artifacts ===
        "codebase": {},
        "test_suite": {},
        "ci_cd_config": {},
        "documentation": {},

        # === Feedback Loop ===
        "sprint_reviews": {},
        "active_feedback_cycle": False,
        "feedback_iteration": 0
    }

    # Select and run appropriate graph
    if prd_only:
        app = define_prd_only_graph()
    else:
        app = define_graph(include_dev_phase=dev_mode or not prd_only)

    log("Starting workflow...")
    result = app.invoke(initial_state)

    # Regenerate portfolio view after workflow completes
    generate_portfolio_view()
    log("Workflow completed.")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Agentic PRD Factory - Transform ideas into PRDs and working code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # PRD generation only (Rounds 1-4) with Anthropic (default)
  python -m src.main --opportunity my_idea.txt

  # Full development lifecycle with Anthropic Claude
  python -m src.main --opportunity my_idea.txt --dev-mode

  # Use Google Gemini instead
  python -m src.main --opportunity my_idea.txt --provider gemini

  # Use a specific model
  python -m src.main --opportunity my_idea.txt --provider anthropic --model claude-opus-4-0-20250514

  # Auto-approve CEO for testing
  python -m src.main --opportunity my_idea.txt --dev-mode --skip-ceo
        """
    )
    parser.add_argument(
        "--opportunity",
        type=str,
        default="opportunity_template.txt",
        help="Path to opportunity/idea file"
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["anthropic", "gemini"],
        default="gemini",
        help="LLM provider to use (default: gemini)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Specific model to use (default: claude-sonnet-4-20250514 for anthropic, gemini-2.0-flash-exp for gemini)"
    )
    parser.add_argument(
        "--dev-mode",
        action="store_true",
        help="Enable full development phase (Round 5 CEO approval + Sprint development)"
    )
    parser.add_argument(
        "--skip-ceo",
        action="store_true",
        help="Auto-approve CEO decision (for testing purposes)"
    )
    parser.add_argument(
        "--prd-only",
        action="store_true",
        help="Run only PRD generation (Rounds 1-4), no CEO or development phase"
    )
    args = parser.parse_args()

    if not os.path.exists(args.opportunity):
        print(f"Error: Opportunity file '{args.opportunity}' not found.")
        return 1

    # Derive project name from filename
    base_name = os.path.basename(args.opportunity)
    project_name = os.path.splitext(base_name)[0]

    opp_text = read_opportunity(args.opportunity)

    # Determine mode
    if args.prd_only:
        mode = "prd_only"
    elif args.dev_mode:
        mode = "full_dev"
    else:
        mode = "prd_ceo"

    print("=" * 60)
    print("AGENTIC PRD FACTORY")
    print("=" * 60)
    print(f"\nReading opportunity from: {args.opportunity}")

    result = run_pipeline(
        opportunity_text=opp_text,
        project_name=project_name,
        mode=mode,
        skip_ceo=args.skip_ceo,
        provider=args.provider,
        model=args.model,
    )

    # Print completion summary
    print("\n" + "=" * 60)
    print("WORKFLOW COMPLETED")
    print("=" * 60)

    print(f"\nProject: {project_name}")
    print(f"Final Round: {result.get('round', 'Unknown')}")

    # CEO decision if applicable
    ceo_decision = result.get("ceo_decision")
    if ceo_decision and ceo_decision != CEODecision.PENDING:
        print(f"CEO Decision: {ceo_decision.value.upper()}")
        if result.get("ceo_comments"):
            print(f"CEO Comments: {result.get('ceo_comments')}")

    # Development phase summary
    if result.get("dev_phase_active") is False and result.get("sprints"):
        sprints = result.get("sprints", {})
        completed = sum(1 for s in sprints.values() if s.get("status") == "completed")
        print(f"Sprints Completed: {completed}/{len(sprints)}")

    print(f"\nOutput Directory: projects/{project_name}/")
    print("  - output/     : PRD documents and executive summary")
    if result.get("marketing_plan"):
        print("                  marketing_plan.md + marketing_plan.pdf")
    print("  - logs/       : Agent reasoning and decision logs")

    if result.get("codebase"):
        print("  - codebase/   : Generated application code")
        print(f"                  ({len(result.get('codebase', {}))} files)")

    if result.get("sprints"):
        print("  - sprints/    : Sprint artifacts and reviews")

    # Priority Score
    score = result.get("priority_score", 0)
    if score:
        breakdown = result.get("score_breakdown", {})
        print(f"\n  Priority Score: {score:.1f}/10")
        print(f"    Reach:          {breakdown.get('reach', 'N/A')}/10")
        print(f"    Feasibility:    {breakdown.get('technical_feasibility', 'N/A')}/10")
        print(f"    Viability:      {breakdown.get('enterprise_buyin', 'N/A')}/10")

    print(f"\n  Portfolio View: projects/portfolio_view.md")
    print(f"                  projects/portfolio_view.pdf")

    print("\n" + "=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
