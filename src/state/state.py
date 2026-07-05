
from typing import TypedDict, List, Dict, Any, Annotated, Optional
from enum import Enum
import operator


class CEODecision(str, Enum):
    """CEO approval decision states."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLARIFICATION_REQUESTED = "clarification_requested"


class SprintStatus(str, Enum):
    """Sprint lifecycle states."""
    NOT_STARTED = "not_started"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    FEEDBACK = "feedback"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class SprintArtifact(TypedDict):
    """Individual artifact produced by a dev agent."""
    agent: str
    artifact_type: str  # "code", "test", "config", "docs"
    file_path: str
    content: str
    version: int


class SprintFeedback(TypedDict):
    """Feedback from stakeholder review."""
    reviewer: str
    sprint_id: int
    feedback_type: str  # "approved", "changes_requested", "blocked"
    comments: str
    affected_artifacts: List[str]


class Sprint(TypedDict):
    """Represents a single development sprint."""
    sprint_id: int
    feature_name: str
    feature_description: str
    status: SprintStatus
    tasks: Dict[str, List[str]]  # Task breakdown from Dev Lead
    artifacts: Dict[str, SprintArtifact]  # key: artifact_id
    feedback: List[SprintFeedback]
    iteration: int  # Number of feedback cycles
    dependencies: List[str]  # Feature dependencies


class AgentState(TypedDict):
    # === Existing PRD Phase Fields ===
    project_name: str
    opportunity: str
    # Drafts: key is agent name, value is their drafted content
    drafts: Dict[str, str]
    # Feedback/Critique logs
    critiques: List[str]
    # Conflict list
    conflicts: List[str]
    # The current round of the protocol
    round: int
    # Logic logs for internal monologue
    logs: List[str]
    # Round 3: Sign-off comments from all agents
    signoffs: Dict[str, str]
    # Round 4: Financial Calculation Data
    roi_data: Dict[str, Any]
    # Final Output
    final_prd: str
    # Round 4 Financial Report
    financial_report: str

    # === Round 4: Priority Score ===
    priority_score: float          # Composite 1-10 score
    score_breakdown: Dict[str, Any]  # {reach, technical_feasibility, enterprise_buyin}

    # === Marketing Plan ===
    marketing_plan: str  # Standalone comprehensive marketing plan

    # === Round 5: CEO Approval ===
    ceo_decision: CEODecision
    ceo_comments: str
    clarification_requests: List[Dict[str, str]]  # [{agent: str, question: str}]
    clarification_responses: Dict[str, str]

    # === Development Phase ===
    dev_phase_active: bool
    features: List[Dict[str, Any]]  # Extracted from PRD
    current_sprint_id: int
    sprints: Dict[int, Sprint]  # key: sprint_id

    # === Sprint Artifacts ===
    codebase: Dict[str, str]  # file_path: content
    test_suite: Dict[str, str]  # test_file_path: content
    ci_cd_config: Dict[str, str]  # config_file_path: content
    documentation: Dict[str, str]  # doc_file_path: content

    # === Feedback Loop ===
    sprint_reviews: Dict[int, Dict[str, Any]]  # sprint_id: review_data
    active_feedback_cycle: bool
    feedback_iteration: int
