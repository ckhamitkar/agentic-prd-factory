
from typing import Dict, List, Any
import json
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from src.state.state import AgentState, CEODecision
from src.agents.factory import AgentFactory
from src.agents.prompts import AGENT_PROMPTS
from src.tools.io import (
    save_draft, save_prd, log_monologue, convert_to_pdf, get_project_dirs,
    save_portfolio_entry, generate_portfolio_view, load_product_context
)
import os
import re as _re
from datetime import datetime

# Import CEO workflow nodes
from src.graph.ceo_workflow import (
    ceo_approval_node,
    handle_clarification_node,
    ceo_decision_router
)

# Import sprint workflow nodes
from src.graph.sprint_workflow import (
    feature_extraction_node,
    sprint_planning_node,
    development_node,
    devops_node,
    qa_node,
    documentation_node,
    sprint_review_node,
    feedback_router,
    apply_feedback_node,
    next_sprint_node
)

# Initialize Factory
factory = AgentFactory()


def drafting_node(state: AgentState):
    """Round 1: Each agent drafts their section based on the opportunity."""
    opportunity = state["opportunity"]
    project_name = state["project_name"]
    drafts = {}

    # In a full production system, these might be parallel nodes.
    # For simplicity, we iterate here.
    for agent_name in AGENT_PROMPTS.keys():
        if agent_name == "Product Owner":
            continue # PO synthesizes later

        system_prompt, llm = factory.create_agent(agent_name)
        user_msg = f"Opportunity: {opportunity}\n\nPlease draft your section for the PRD."

        # Invoke LLM
        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_msg)])
        content = response.content

        drafts[agent_name] = content
        save_draft(agent_name, content, round_num=1, project_name=project_name)

    return {"drafts": drafts, "round": 1}

def consensus_node(state: AgentState):
    """Round 2: Conflict Detection & Negotiation (Internal Monologue)."""
    drafts = state["drafts"]
    opportunity = state["opportunity"]
    project_name = state["project_name"]

    # 1. Product Owner analyzes drafts for conflicts
    po_system, po_llm = factory.create_agent("Product Owner")

    # Prepare a consolidated view for the PO
    all_drafts_text = "\n\n".join([f"--- {k} ---\n{v}" for k, v in drafts.items()])

    analysis_prompt = (
        f"You are the Product Owner. Review the following drafts for the opportunity: '{opportunity}'.\n"
        "Identify any contradictions or conflicts (e.g. Sales wanting high price vs Marketing wanting freemium).\n"
        "Also identify missing critical info.\n"
        "Think step-by-step. Log your internal reasoning."
    )

    # We want to capture the reasoning (Internal Monologue)
    # We can ask the model to output a specific format or just capture the full output
    response = po_llm.invoke([
        SystemMessage(content=po_system),
        HumanMessage(content=f"{analysis_prompt}\n\nDRAFTS:\n{all_drafts_text}")
    ])

    reasoning = response.content
    log_monologue("consensus_analysis", "Product Owner", reasoning, project_name=project_name)

    # Check if there are conflicts (Simple heuristic or LLM parsing)
    # For this implementation, we'll assume the PO provides a 'resolution' or 'merged_draft'
    # In a more complex Agentic system, we would trigger sub-dialogues.
    # Here, we will ask the PO to synthesize the V2 PRD directly based on the analysis.

    synthesis_prompt = (
        "Based on your analysis and the drafts, create a cohesive, resolved V2 PRD.\n"
        "Resolve all conflicts according to your best judgment as PO.\n"
        "Output the full PRD in Markdown format."
    )

    synthesis_response = po_llm.invoke([
         SystemMessage(content=po_system),
         HumanMessage(content=f"{analysis_prompt}\n\nDRAFTS:\n{all_drafts_text}\n\nYou analyzed it used this reasoning:\n{reasoning}\n\n{synthesis_prompt}")
    ])

    final_prd = synthesis_response.content
    save_prd(final_prd, round_num=2, project_name=project_name)

    # Also save as PDF for the full V2 PRD
    output_dir, _ = get_project_dirs(project_name)
    pdf_path = os.path.join(output_dir, "prd_full_v2.pdf")
    convert_to_pdf(final_prd, pdf_path)

    # Log the decision process
    log_monologue("final_synthesis", "Product Owner", "I have synthesized the drafts into a V2 PRD, resolving conflicts as noted in the analysis logs.", project_name=project_name)

    return {"final_prd": final_prd, "round": 2}

def signoff_node(state: AgentState):
    """Round 3: Stakeholder Final Review & Risk Assessment."""
    project_name = state["project_name"]
    final_prd_v2 = state["final_prd"]

    signoffs = {}

    # Iterate all agents for sign-off
    for agent_name in AGENT_PROMPTS.keys():
        if agent_name == "Product Owner": continue

        system_prompt, llm = factory.create_agent(agent_name)

        signoff_prompt = (
            f"Review the following V2 Consensus PRD:\n{final_prd_v2[:20000]}\n"
            "Provide your formal 'Sign-off Comment'.\n"
            "Explicitly state if your domain risks are mitigated (Green), At Risk (Yellow), or Critical (Red).\n"
            "Be concise."
        )

        response = llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=signoff_prompt)])
        signoffs[agent_name] = response.content

        log_monologue("round3_signoff", agent_name, response.content, project_name=project_name)

    return {"signoffs": signoffs, "round": 3}

def financial_node(state: AgentState):
    """Round 4: Financial Reconciliation & ROI Calculation."""
    project_name = state["project_name"]
    signoffs = state["signoffs"]
    opportunity = state["opportunity"]

    po_system, po_llm = factory.create_agent("Product Owner")

    # 1. Ask Engineering for estimates
    eng_sys, eng_llm = factory.create_agent("Engineering")
    eng_est = eng_llm.invoke([
        SystemMessage(content=eng_sys),
        HumanMessage(content=f"Based on the opportunity '{opportunity}', estimate the total 'Dev Hours' and monthly 'Infrastructure Cost' to build the MVP. Return JSON format.")
    ]).content

    # 2. Ask Finance for revenue
    fin_sys, fin_llm = factory.create_agent("Finance")
    fin_rev = fin_llm.invoke([
        SystemMessage(content=fin_sys),
        HumanMessage(content=f"Based on the opportunity '{opportunity}', estimate the 'first year revenue'. Return JSON format.")
    ]).content

    log_monologue("financial_inputs", "System", f"Eng Est: {eng_est}\nFin Rev: {fin_rev}", project_name=project_name)

    # 3. PO Synthesis & ROI Calculation
    financial_prompt = (
        "You are the Product Owner. Create the 'v3_executive_summary.md'.\n"
        "1. Summarize the Product Vision.\n"
        "2. Include a 'Financial Viability' section.\n"
        f"   - Use these Engineering Estimates: {eng_est}\n"
        f"   - Use these Finance Projections: {fin_rev}\n"
        "   - Calculate ROI = (First Year Revenue - (Dev Hours * $150/hr + Infra Cost * 12)).\n"
        "3. List the 'Sign-off Status' for each stakeholder based on Round 3:\n" +
        "\n".join([f"   - {k}: {v[:2000]}" for k, v in signoffs.items()]) + "\n"
        "4. Conclude with a clear GO / NO-GO recommendation."
    )

    response = po_llm.invoke([SystemMessage(content=po_system), HumanMessage(content=financial_prompt)])
    final_report = response.content

    # Check project dir to find output path for PDF
    output_dir, _ = get_project_dirs(project_name)

    # Save MD
    md_path = os.path.join(output_dir, "v3_executive_summary.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(final_report)

    # Convert to PDF
    pdf_path = os.path.join(output_dir, "prd.pdf")
    convert_to_pdf(final_report, pdf_path)

    # === Priority Score Calculation ===
    product_context = load_product_context()

    scoring_prompt = (
        "You are the Product Owner. Based on the opportunity, all agent drafts, "
        "financial analysis, and this product context:\n\n"
        f"{product_context}\n\n"
        "Score this idea on the ROI Scorecard. For EACH dimension, provide a score from 1-10:\n"
        "1. **Reach** (weight 40%): Size of the target user population.\n"
        "2. **Technical Feasibility** (weight 30%): How difficult is it to implement?\n"
        "3. **Business Viability** (weight 30%): Is there a willing buyer / sustainable model?\n\n"
        f"Opportunity: {opportunity}\n\n"
        "Return ONLY valid JSON in this exact format:\n"
        '{"reach": <1-10>, "technical_feasibility": <1-10>, "enterprise_buyin": <1-10>, '
        '"reach_rationale": "<one sentence>", "feasibility_rationale": "<one sentence>", '
        '"buyin_rationale": "<one sentence>"}'
    )

    score_response = po_llm.invoke([
        SystemMessage(content=po_system),
        HumanMessage(content=scoring_prompt)
    ])

    # Parse the JSON score response
    score_text = score_response.content.strip()
    json_match = _re.search(r'\{[^}]+\}', score_text, _re.DOTALL)
    try:
        score_data = json.loads(json_match.group() if json_match else score_text)
    except (json.JSONDecodeError, AttributeError):
        score_data = {"reach": 5, "technical_feasibility": 5, "enterprise_buyin": 5}

    reach = score_data.get("reach", 5)
    feasibility = score_data.get("technical_feasibility", 5)
    buyin = score_data.get("enterprise_buyin", 5)
    composite = reach * 0.4 + feasibility * 0.3 + buyin * 0.3

    log_monologue(
        "priority_score", "Product Owner",
        f"Reach={reach}, Feasibility={feasibility}, Viability={buyin}, Composite={composite:.1f}\n"
        f"Rationale: {json.dumps(score_data, indent=2)}",
        project_name=project_name
    )

    # Persist to portfolio
    save_portfolio_entry({
        "project_name": project_name,
        "opportunity_summary": opportunity[:200],
        "priority_score": round(composite, 1),
        "score_breakdown": {
            "reach": reach,
            "technical_feasibility": feasibility,
            "enterprise_buyin": buyin
        },
        "rationale": {
            "reach": score_data.get("reach_rationale", ""),
            "feasibility": score_data.get("feasibility_rationale", ""),
            "buyin": score_data.get("buyin_rationale", "")
        },
        "date": datetime.now().isoformat()
    })

    # Regenerate the portfolio view
    generate_portfolio_view()

    return {
        "financial_report": final_report,
        "round": 4,
        "priority_score": round(composite, 1),
        "score_breakdown": {
            "reach": reach,
            "technical_feasibility": feasibility,
            "enterprise_buyin": buyin
        }
    }

def marketing_plan_node(state: AgentState):
    """Generate a comprehensive, standalone marketing plan."""
    project_name = state["project_name"]
    opportunity = state["opportunity"]
    final_prd = state.get("final_prd", "")
    financial_report = state.get("financial_report", "")

    product_context = load_product_context()
    output_dir, _ = get_project_dirs(project_name)

    # Step 1: Marketing agent drafts the full plan
    mkt_system, mkt_llm = factory.create_agent("Marketing")
    draft_prompt = (
        "Create a comprehensive, actionable Marketing Plan for this product.\n\n"
        f"## Opportunity\n{opportunity}\n\n"
        f"## Finalized PRD (summary)\n{final_prd[:3000]}\n\n"
        f"## Financial Context\n{financial_report[:2000]}\n\n"
        f"## Product Context\n{product_context}\n\n"
        "Produce a FULL marketing plan in Markdown with ALL 10 sections:\n"
        "1. Target Audience & Segmentation (specific personas)\n"
        "2. Positioning & Value Proposition\n"
        "3. Distribution Channels\n"
        "4. Pricing Strategy\n"
        "5. Launch Playbook (phased rollout with timelines)\n"
        "6. Partnership & Ecosystem\n"
        "7. Growth Engine (referrals, retention loops)\n"
        "8. Budget & Unit Economics (CAC, LTV, specific numbers)\n"
        "9. KPIs & Milestones (weekly/monthly targets)\n"
        "10. Risk Mitigation\n\n"
        "Every section must contain ACTIONABLE items: who does what, by when, at what cost. "
        "No vague statements. Include specific numbers, timelines, and responsible roles."
    )

    mkt_draft = mkt_llm.invoke([
        SystemMessage(content=mkt_system),
        HumanMessage(content=draft_prompt)
    ]).content

    log_monologue("marketing_plan_draft", "Marketing", "Initial marketing plan drafted.", project_name=project_name)

    # Step 2: Sales agent reviews and enriches
    sales_system, sales_llm = factory.create_agent("Sales")
    sales_review = sales_llm.invoke([
        SystemMessage(content=sales_system),
        HumanMessage(content=(
            "Review this marketing plan and ADD specific sales-side details:\n"
            "- Who is the paying buyer?\n"
            "- What does the sales pitch look like?\n"
            "- What are the deal sizes and sales cycle timelines?\n"
            "- What pricing tiers and revenue projections do you recommend?\n\n"
            f"## Marketing Plan Draft\n{mkt_draft[:4000]}\n\n"
            f"## Opportunity\n{opportunity[:1000]}\n\n"
            "Return your additions and corrections in Markdown."
        ))
    ]).content

    # Step 3: BA reviews and adds market sizing
    ba_system, ba_llm = factory.create_agent("Business Analyst")
    ba_review = ba_llm.invoke([
        SystemMessage(content=ba_system),
        HumanMessage(content=(
            "Review this marketing plan and ADD specific market data:\n"
            "- TAM/SAM/SOM with population numbers and sources\n"
            "- Adoption/penetration rates for the target demographic\n"
            "- Comparable products that succeeded in similar markets\n"
            "- Competitive landscape analysis\n"
            "- KPI benchmarks from comparable product launches\n\n"
            f"## Marketing Plan Draft\n{mkt_draft[:4000]}\n\n"
            f"## Opportunity\n{opportunity[:1000]}\n\n"
            "Return your additions and corrections in Markdown."
        ))
    ]).content

    # Step 4: Marketing synthesizes final version
    final_plan = mkt_llm.invoke([
        SystemMessage(content=mkt_system),
        HumanMessage(content=(
            "Synthesize the final Marketing Plan by incorporating the Sales and BA feedback.\n"
            "Produce the COMPLETE final plan in Markdown. Keep all 10 sections.\n"
            "Ensure every section has specific, actionable items with numbers and timelines.\n\n"
            f"## Your Draft\n{mkt_draft}\n\n"
            f"## Sales Feedback\n{sales_review}\n\n"
            f"## Business Analyst Feedback\n{ba_review}\n\n"
            "Output the final comprehensive marketing plan in Markdown."
        ))
    ]).content

    log_monologue("marketing_plan_final", "Marketing", "Final marketing plan synthesized with Sales and BA input.", project_name=project_name)

    # Save as standalone files
    md_path = os.path.join(output_dir, "marketing_plan.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(final_plan)

    pdf_path = os.path.join(output_dir, "marketing_plan.pdf")
    convert_to_pdf(final_plan, pdf_path)

    return {"marketing_plan": final_plan}


def dev_phase_router(state: AgentState) -> str:
    """Route based on dev_phase_active flag."""
    if state.get("dev_phase_active", False):
        return "continue_dev"
    else:
        return "end"


def sprint_complete_router(state: AgentState) -> str:
    """Route after moving to next sprint - check if more sprints exist."""
    current_sprint_id = state.get("current_sprint_id", 0)
    sprints = state.get("sprints", {})

    if current_sprint_id < len(sprints):
        return "next_sprint"
    else:
        return "all_done"


def define_graph(include_dev_phase: bool = True):
    """
    Define the full Agentic PRD Factory workflow.

    Args:
        include_dev_phase: If True, include Round 5 (CEO) and development phase.
                          If False, only run Rounds 1-4 (PRD generation).
    """
    workflow = StateGraph(AgentState)

    # =========================================================================
    # PRD Phase Nodes (Rounds 1-4) - Existing
    # =========================================================================
    workflow.add_node("drafting", drafting_node)
    workflow.add_node("consensus", consensus_node)
    workflow.add_node("signoff", signoff_node)
    workflow.add_node("financial", financial_node)
    workflow.add_node("marketing_plan", marketing_plan_node)

    # =========================================================================
    # CEO Approval Phase (Round 5) - New
    # =========================================================================
    workflow.add_node("ceo_approval", ceo_approval_node)
    workflow.add_node("clarification", handle_clarification_node)

    # =========================================================================
    # Development Phase Nodes - New
    # =========================================================================
    workflow.add_node("feature_extraction", feature_extraction_node)
    workflow.add_node("sprint_planning", sprint_planning_node)
    workflow.add_node("development", development_node)
    workflow.add_node("devops", devops_node)
    workflow.add_node("qa", qa_node)
    workflow.add_node("documentation", documentation_node)
    workflow.add_node("sprint_review", sprint_review_node)
    workflow.add_node("apply_feedback", apply_feedback_node)
    workflow.add_node("next_sprint", next_sprint_node)

    # =========================================================================
    # PRD Phase Edges (Rounds 1-4)
    # =========================================================================
    workflow.set_entry_point("drafting")
    workflow.add_edge("drafting", "consensus")
    workflow.add_edge("consensus", "signoff")
    workflow.add_edge("signoff", "financial")
    workflow.add_edge("financial", "marketing_plan")

    if include_dev_phase:
        # =====================================================================
        # Round 5: CEO Approval Edges
        # =====================================================================
        workflow.add_edge("marketing_plan", "ceo_approval")

        # Conditional: CEO decision routing
        workflow.add_conditional_edges(
            "ceo_approval",
            ceo_decision_router,
            {
                "approved": "feature_extraction",
                "rejected": END,
                "clarification": "clarification"
            }
        )
        # Loop back after clarification
        workflow.add_edge("clarification", "ceo_approval")

        # =====================================================================
        # Development Phase Edges
        # =====================================================================
        # Feature extraction leads to dev phase check
        workflow.add_conditional_edges(
            "feature_extraction",
            dev_phase_router,
            {
                "continue_dev": "sprint_planning",
                "end": END
            }
        )

        # Sprint cycle
        workflow.add_edge("sprint_planning", "development")
        workflow.add_edge("development", "devops")
        workflow.add_edge("devops", "qa")
        workflow.add_edge("qa", "documentation")
        workflow.add_edge("documentation", "sprint_review")

        # Feedback loop conditional
        workflow.add_conditional_edges(
            "sprint_review",
            feedback_router,
            {
                "approved": "next_sprint",
                "feedback": "apply_feedback",
                "end": END
            }
        )

        # After applying feedback, re-enter development
        workflow.add_edge("apply_feedback", "development")

        # After moving to next sprint, check if more sprints or done
        workflow.add_conditional_edges(
            "next_sprint",
            sprint_complete_router,
            {
                "next_sprint": "sprint_planning",
                "all_done": END
            }
        )
    else:
        # Without dev phase, end after marketing plan
        workflow.add_edge("marketing_plan", END)

    return workflow.compile()


def define_prd_only_graph():
    """
    Define a PRD-only workflow (Rounds 1-4 only).

    Useful for testing or when development phase is not needed.
    """
    return define_graph(include_dev_phase=False)
