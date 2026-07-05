"""
CEO Approval CLI Interface.

Provides a command-line interface for the CEO (human-in-the-loop)
to review executive summaries and make approval decisions.
"""

from typing import Tuple, Optional
from src.state.state import CEODecision
from src.agents.prompts import AGENT_PROMPTS


def display_executive_summary(summary: str, max_length: int = 5000) -> None:
    """Display the executive summary for CEO review."""
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY FOR CEO REVIEW")
    print("=" * 70)

    if len(summary) > max_length:
        print(summary[:max_length])
        print(f"\n... [Truncated - {len(summary) - max_length} more characters]")
        print("(Full summary available in project output directory)")
    else:
        print(summary)

    print("=" * 70)


def display_options() -> None:
    """Display decision options to the CEO."""
    print("\n" + "-" * 50)
    print("CEO DECISION OPTIONS")
    print("-" * 50)
    print("  [1] APPROVE  - Proceed to software development phase")
    print("  [2] REJECT   - Terminate project (provide reason)")
    print("  [3] CLARIFY  - Request clarification from a specific agent")
    print("-" * 50)


def get_agent_selection() -> Optional[str]:
    """Let CEO select an agent for clarification."""
    agent_names = list(AGENT_PROMPTS.keys())

    print("\nAvailable agents for clarification:")
    for i, name in enumerate(agent_names, 1):
        config = AGENT_PROMPTS[name]
        print(f"  [{i:2d}] {name:<20} - {config['focus']}")

    while True:
        choice = input("\nSelect agent number (or 'c' to cancel): ").strip().lower()

        if choice == 'c':
            return None

        try:
            agent_idx = int(choice) - 1
            if 0 <= agent_idx < len(agent_names):
                return agent_names[agent_idx]
            else:
                print(f"Invalid selection. Please enter 1-{len(agent_names)} or 'c' to cancel.")
        except ValueError:
            print("Please enter a valid number or 'c' to cancel.")


def get_ceo_input(skip_approval: bool = False) -> Tuple[CEODecision, str, Optional[str]]:
    """
    CLI interface for CEO to make approval decision.

    Args:
        skip_approval: If True, auto-approve (for testing)

    Returns:
        Tuple of (decision, comments, agent_name_for_clarification)
    """
    if skip_approval:
        print("\n[AUTO-APPROVE MODE] Skipping CEO approval for testing.")
        return (CEODecision.APPROVED, "Auto-approved for testing", None)

    display_options()

    while True:
        choice = input("\nYour decision (1/2/3): ").strip()

        if choice == "1":
            # APPROVE
            comments = input("Any additional comments or conditions (optional, press Enter to skip): ").strip()
            print("\n[CEO DECISION] Project APPROVED for development phase.")
            return (CEODecision.APPROVED, comments, None)

        elif choice == "2":
            # REJECT
            print("\nPlease provide a reason for rejection.")
            comments = input("Reason for rejection (required): ").strip()

            if not comments:
                print("Rejection reason is required. Please try again.")
                continue

            confirm = input(f"Confirm rejection with reason: '{comments}'? (y/n): ").strip().lower()
            if confirm == 'y':
                print("\n[CEO DECISION] Project REJECTED.")
                return (CEODecision.REJECTED, comments, None)
            else:
                print("Rejection cancelled. Please make a new selection.")
                continue

        elif choice == "3":
            # CLARIFY
            agent_name = get_agent_selection()

            if agent_name is None:
                print("Clarification cancelled. Please make a new selection.")
                continue

            print(f"\nYou selected: {agent_name}")
            question = input(f"Your question for {agent_name}: ").strip()

            if not question:
                print("Question is required for clarification. Please try again.")
                continue

            print(f"\n[CEO DECISION] Requesting clarification from {agent_name}.")
            return (CEODecision.CLARIFICATION_REQUESTED, question, agent_name)

        else:
            print("Invalid choice. Please enter 1, 2, or 3.")


def display_clarification_response(agent_name: str, response: str) -> None:
    """Display clarification response from an agent."""
    print("\n" + "-" * 50)
    print(f"CLARIFICATION RESPONSE FROM: {agent_name}")
    print("-" * 50)
    print(response)
    print("-" * 50)
    print("\nYou may now make another decision based on this clarification.")
