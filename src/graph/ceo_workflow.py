"""
CEO Approval Workflow Nodes.

Implements Round 5: CEO Human-in-the-Loop approval process.
"""

from typing import Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage

from src.state.state import AgentState, CEODecision
from src.cli.ceo_approval import (
    display_executive_summary,
    get_ceo_input,
    display_clarification_response
)
from src.agents.factory import AgentFactory
from src.tools.io import log_monologue

# Initialize factory for agent creation
factory = AgentFactory()


def ceo_approval_node(state: AgentState) -> Dict[str, Any]:
    """
    Round 5: CEO reviews executive summary and makes decision.

    This is a Human-in-the-Loop (HITL) node that pauses execution
    and waits for CEO input via CLI.
    """
    project_name = state["project_name"]

    # Get the executive summary (prefer financial_report, fallback to final_prd)
    executive_summary = state.get("financial_report", state.get("final_prd", ""))

    if not executive_summary:
        print("\n[WARNING] No executive summary found. Using opportunity text.")
        executive_summary = state.get("opportunity", "No content available.")

    # Display summary for CEO review
    display_executive_summary(executive_summary)

    # Check if there are clarification responses to show first
    clarification_responses = state.get("clarification_responses", {})
    if clarification_responses:
        print("\n" + "=" * 70)
        print("PREVIOUS CLARIFICATION RESPONSES")
        print("=" * 70)
        for agent_name, response in clarification_responses.items():
            display_clarification_response(agent_name, response)

    # Check for skip_ceo flag in state (for testing)
    skip_approval = state.get("skip_ceo", False)

    # Get CEO decision via CLI
    decision, comments, clarification_agent = get_ceo_input(skip_approval=skip_approval)

    # Log the CEO decision
    log_monologue(
        "ceo_decision",
        "CEO",
        f"Decision: {decision.value}\nComments: {comments}\nClarification Agent: {clarification_agent}",
        project_name=project_name
    )

    # Build update dictionary
    updates: Dict[str, Any] = {
        "ceo_decision": decision,
        "ceo_comments": comments,
        "round": 5
    }

    # If clarification requested, add to requests
    if decision == CEODecision.CLARIFICATION_REQUESTED and clarification_agent:
        existing_requests = state.get("clarification_requests", [])
        updates["clarification_requests"] = existing_requests + [
            {"agent": clarification_agent, "question": comments}
        ]

    return updates


def handle_clarification_node(state: AgentState) -> Dict[str, Any]:
    """
    Handle clarification requests from CEO.

    Invokes the requested agent to answer the CEO's question
    and stores the response.
    """
    project_name = state["project_name"]
    requests = state.get("clarification_requests", [])
    responses = dict(state.get("clarification_responses", {}))
    final_prd = state.get("final_prd", "")
    financial_report = state.get("financial_report", "")

    # Context for the agent
    context = financial_report if financial_report else final_prd

    for request in requests:
        agent_name = request["agent"]
        question = request["question"]

        print(f"\n[CLARIFICATION] Getting response from {agent_name}...")

        # Create the agent
        system_prompt, llm = factory.create_agent(agent_name)

        # Build clarification prompt
        clarification_prompt = (
            f"The CEO has requested clarification on the following topic:\n\n"
            f"**CEO's Question:** {question}\n\n"
            f"**Context (Executive Summary/PRD):**\n{context[:3000]}\n\n"
            f"Please provide a clear, concise, and helpful response from your "
            f"perspective as the {agent_name}. Focus on addressing the specific "
            f"question while considering your domain expertise."
        )

        # Get response
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=clarification_prompt)
        ])

        # Store response
        responses[agent_name] = response.content

        # Log the clarification
        log_monologue(
            "ceo_clarification",
            agent_name,
            f"Question: {question}\n\nResponse:\n{response.content}",
            project_name=project_name
        )

        # Display to CEO
        display_clarification_response(agent_name, response.content)

    return {
        "clarification_responses": responses,
        "clarification_requests": []  # Clear processed requests
    }


def ceo_decision_router(state: AgentState) -> str:
    """
    Route based on CEO decision.

    Returns:
        "approved" - Proceed to development phase
        "rejected" - End workflow
        "clarification" - Handle clarification request
    """
    decision = state.get("ceo_decision", CEODecision.PENDING)

    if decision == CEODecision.APPROVED:
        print("\n[WORKFLOW] CEO approved. Proceeding to development phase...")
        return "approved"

    elif decision == CEODecision.REJECTED:
        print("\n[WORKFLOW] CEO rejected. Ending workflow.")
        print(f"Rejection reason: {state.get('ceo_comments', 'No reason provided')}")
        return "rejected"

    elif decision == CEODecision.CLARIFICATION_REQUESTED:
        print("\n[WORKFLOW] CEO requested clarification. Processing...")
        return "clarification"

    else:
        # Default to rejected for safety
        print("\n[WORKFLOW] Unknown decision state. Ending workflow.")
        return "rejected"
