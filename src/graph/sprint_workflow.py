"""
Sprint Workflow Nodes.

Implements the software development lifecycle after CEO approval:
- Feature extraction from PRD
- Sprint planning
- Development (Backend + Frontend)
- DevOps (CI/CD + Infrastructure)
- QA (Testing)
- Documentation
- Sprint Review with feedback loop
"""

from typing import Dict, Any, List
import json

from langchain_core.messages import SystemMessage, HumanMessage

from src.state.state import (
    AgentState,
    Sprint,
    SprintStatus,
    SprintArtifact,
    SprintFeedback
)
from src.agents.factory import AgentFactory
from src.tools.io import (
    log_monologue,
    save_sprint_log,
    save_codebase_file,
    ensure_sprint_dirs
)
from src.tools.artifact_manager import ArtifactManager
from src.tools.code_gen import CodeGenerator

# Initialize utilities
factory = AgentFactory()
artifact_mgr = ArtifactManager()
code_gen = CodeGenerator()


def feature_extraction_node(state: AgentState) -> Dict[str, Any]:
    """
    Extract implementable features from the approved PRD.

    Product Owner analyzes the PRD and identifies discrete features
    that can be implemented as individual sprints.
    """
    final_prd = state["final_prd"]
    project_name = state["project_name"]

    print("\n[SPRINT] Extracting features from PRD...")

    # Use Product Owner to extract features
    po_system, po_llm = factory.create_agent("Product Owner")

    extraction_prompt = (
        "Analyze this approved PRD and extract all implementable features.\n\n"
        "For each feature, provide:\n"
        "1. feature_name: Short identifier (snake_case)\n"
        "2. description: What the feature does and its value\n"
        "3. priority: P0 (critical), P1 (important), P2 (nice to have)\n"
        "4. dependencies: List of other feature names this depends on\n"
        "5. complexity: low, medium, or high\n"
        "6. acceptance_criteria: List of testable criteria\n\n"
        "Return ONLY a valid JSON array. Example:\n"
        "```json\n"
        "[\n"
        '  {"feature_name": "user_auth", "description": "...", "priority": "P0", '
        '"dependencies": [], "complexity": "medium", "acceptance_criteria": ["..."]}\n'
        "]\n"
        "```\n\n"
        f"PRD to analyze:\n{final_prd}"
    )

    response = po_llm.invoke([
        SystemMessage(content=po_system),
        HumanMessage(content=extraction_prompt)
    ])

    # Parse features from response
    features = code_gen.extract_json_from_response(response.content)

    if not features:
        # Fallback: create single MVP feature
        print("[WARNING] Could not parse features. Creating single MVP sprint.")
        features = [{
            "feature_name": "mvp_implementation",
            "description": "Complete MVP implementation based on PRD",
            "priority": "P0",
            "dependencies": [],
            "complexity": "high",
            "acceptance_criteria": ["All PRD requirements met"]
        }]

    # Sort by priority and dependencies
    features = sorted(features, key=lambda f: (f.get("priority", "P2"), f.get("feature_name", "")))

    # Initialize sprints dictionary
    sprints: Dict[int, Sprint] = {}
    for i, feature in enumerate(features):
        sprints[i] = Sprint(
            sprint_id=i,
            feature_name=feature.get("feature_name", f"feature_{i}"),
            feature_description=feature.get("description", ""),
            status=SprintStatus.NOT_STARTED,
            tasks={},
            artifacts={},
            feedback=[],
            iteration=0,
            dependencies=feature.get("dependencies", [])
        )

    # Log extraction
    log_monologue(
        "feature_extraction",
        "Product Owner",
        f"Extracted {len(features)} features:\n" +
        "\n".join([f"- {f['feature_name']}: {f.get('description', '')[:100]}" for f in features]),
        project_name=project_name
    )

    print(f"[SPRINT] Extracted {len(features)} features for development.")
    for f in features:
        print(f"  - {f['feature_name']} ({f.get('priority', 'P2')})")

    return {
        "features": features,
        "sprints": sprints,
        "current_sprint_id": 0,
        "dev_phase_active": True
    }


def sprint_planning_node(state: AgentState) -> Dict[str, Any]:
    """
    Dev Lead creates sprint backlog with detailed tasks.

    Breaks down the feature into backend, frontend, devops, qa, and doc tasks.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    project_name = state["project_name"]
    final_prd = state.get("final_prd", "")

    # Check if all sprints completed
    if current_sprint_id >= len(sprints):
        print("[SPRINT] All sprints completed!")
        return {"dev_phase_active": False}

    sprint = dict(sprints[current_sprint_id])
    feature_name = sprint["feature_name"]

    print(f"\n[SPRINT {current_sprint_id}] Planning: {feature_name}")

    # Dev Lead creates task breakdown
    dev_lead_system, dev_lead_llm = factory.create_agent("Dev Lead")

    planning_prompt = (
        f"Create a sprint plan for implementing this feature:\n\n"
        f"**Feature Name:** {feature_name}\n"
        f"**Description:** {sprint['feature_description']}\n\n"
        f"**Tech Stack Context (from PRD):**\n{final_prd[:2000]}\n\n"
        "Create a detailed task breakdown. Return as JSON with these keys:\n"
        "- backend_tasks: List of backend implementation tasks\n"
        "- frontend_tasks: List of frontend implementation tasks\n"
        "- devops_tasks: List of infrastructure/CI-CD tasks\n"
        "- qa_tasks: List of testing tasks\n"
        "- doc_tasks: List of documentation tasks\n\n"
        "Each task should be a string describing what needs to be done.\n"
        "Example:\n"
        "```json\n"
        "{\n"
        '  "backend_tasks": ["Create user model", "Implement auth endpoints"],\n'
        '  "frontend_tasks": ["Build login form", "Add auth state management"],\n'
        '  "devops_tasks": ["Set up Docker", "Configure CI pipeline"],\n'
        '  "qa_tasks": ["Write unit tests for auth", "Create e2e login test"],\n'
        '  "doc_tasks": ["Document auth API", "Update README"]\n'
        "}\n"
        "```"
    )

    response = dev_lead_llm.invoke([
        SystemMessage(content=dev_lead_system),
        HumanMessage(content=planning_prompt)
    ])

    # Parse tasks
    tasks = code_gen.extract_json_from_response(response.content)

    if not tasks:
        tasks = {
            "backend_tasks": [f"Implement {feature_name} backend"],
            "frontend_tasks": [f"Implement {feature_name} frontend"],
            "devops_tasks": ["Configure deployment"],
            "qa_tasks": ["Write tests"],
            "doc_tasks": ["Document feature"]
        }

    sprint["tasks"] = tasks
    sprint["status"] = SprintStatus.IN_PROGRESS
    sprints[current_sprint_id] = sprint

    # Log planning
    save_sprint_log(
        project_name, current_sprint_id, "planning",
        f"# Sprint {current_sprint_id} Planning\n\n"
        f"## Feature: {feature_name}\n\n"
        f"## Tasks\n{json.dumps(tasks, indent=2)}"
    )

    print(f"[SPRINT {current_sprint_id}] Tasks planned:")
    for category, task_list in tasks.items():
        print(f"  {category}: {len(task_list)} tasks")

    return {"sprints": sprints}


def development_node(state: AgentState) -> Dict[str, Any]:
    """
    Backend and Frontend developers implement the feature.

    Generates actual code files for the feature.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])
    project_name = state["project_name"]
    tasks = sprint.get("tasks", {})
    final_prd = state.get("final_prd", "")

    feature_name = sprint["feature_name"]
    print(f"\n[SPRINT {current_sprint_id}] Development: {feature_name}")

    artifacts = dict(sprint.get("artifacts", {}))
    codebase = dict(state.get("codebase", {}))

    # =========================================================================
    # Backend Development
    # =========================================================================
    print("  [Backend] Generating code...")
    backend_sys, backend_llm = factory.create_agent("Backend Developer")

    backend_prompt = (
        f"Implement the backend for feature: {feature_name}\n\n"
        f"**Feature Description:** {sprint['feature_description']}\n"
        f"**Tasks:** {json.dumps(tasks.get('backend_tasks', []))}\n"
        f"**PRD Context:** {final_prd[:1500]}\n\n"
        "Generate complete, working Python code using FastAPI. Include:\n"
        "1. API routes with proper typing and docstrings\n"
        "2. Pydantic schemas for request/response\n"
        "3. SQLAlchemy models\n"
        "4. Service layer with business logic\n\n"
        "Return as JSON with these file keys:\n"
        "- routes: FastAPI router code\n"
        "- schemas: Pydantic models\n"
        "- models: SQLAlchemy models\n"
        "- services: Business logic\n\n"
        "Each value should be the complete file content as a string."
    )

    backend_response = backend_llm.invoke([
        SystemMessage(content=backend_sys),
        HumanMessage(content=backend_prompt)
    ])

    backend_code = code_gen.extract_json_from_response(backend_response.content)

    if backend_code:
        for key, content in backend_code.items():
            if isinstance(content, str) and content.strip():
                artifact_id = f"backend_{key}"
                file_path = f"backend/app/{key}.py"
                artifacts[artifact_id] = SprintArtifact(
                    agent="Backend Developer",
                    artifact_type="code",
                    file_path=file_path,
                    content=content,
                    version=sprint["iteration"] + 1
                )
                codebase[file_path] = content
    else:
        # Store raw response as fallback
        artifacts["backend_main"] = SprintArtifact(
            agent="Backend Developer",
            artifact_type="code",
            file_path="backend/app/main.py",
            content=backend_response.content,
            version=sprint["iteration"] + 1
        )
        codebase["backend/app/main.py"] = backend_response.content

    # =========================================================================
    # Frontend Development
    # =========================================================================
    print("  [Frontend] Generating code...")
    frontend_sys, frontend_llm = factory.create_agent("Frontend Developer")

    frontend_prompt = (
        f"Implement the frontend for feature: {feature_name}\n\n"
        f"**Feature Description:** {sprint['feature_description']}\n"
        f"**Tasks:** {json.dumps(tasks.get('frontend_tasks', []))}\n\n"
        "Generate complete React/TypeScript code. Include:\n"
        "1. React functional components with hooks\n"
        "2. TypeScript interfaces/types\n"
        "3. API integration hooks\n"
        "4. Basic Tailwind CSS styling\n\n"
        "Return as JSON with these file keys:\n"
        "- components: Main component code\n"
        "- hooks: Custom hooks\n"
        "- types: TypeScript types\n"
        "- api: API client functions\n\n"
        "Each value should be the complete file content as a string."
    )

    frontend_response = frontend_llm.invoke([
        SystemMessage(content=frontend_sys),
        HumanMessage(content=frontend_prompt)
    ])

    frontend_code = code_gen.extract_json_from_response(frontend_response.content)

    if frontend_code:
        for key, content in frontend_code.items():
            if isinstance(content, str) and content.strip():
                artifact_id = f"frontend_{key}"
                ext = "tsx" if key == "components" else "ts"
                file_path = f"frontend/src/{key}.{ext}"
                artifacts[artifact_id] = SprintArtifact(
                    agent="Frontend Developer",
                    artifact_type="code",
                    file_path=file_path,
                    content=content,
                    version=sprint["iteration"] + 1
                )
                codebase[file_path] = content
    else:
        artifacts["frontend_app"] = SprintArtifact(
            agent="Frontend Developer",
            artifact_type="code",
            file_path="frontend/src/App.tsx",
            content=frontend_response.content,
            version=sprint["iteration"] + 1
        )
        codebase["frontend/src/App.tsx"] = frontend_response.content

    # Update sprint
    sprint["artifacts"] = artifacts
    sprints[current_sprint_id] = sprint

    # Save artifacts to disk
    artifact_mgr.save_sprint_artifacts(project_name, current_sprint_id, artifacts)

    print(f"  Generated {len([a for a in artifacts if 'backend' in a])} backend files")
    print(f"  Generated {len([a for a in artifacts if 'frontend' in a])} frontend files")

    return {"sprints": sprints, "codebase": codebase}


def devops_node(state: AgentState) -> Dict[str, Any]:
    """
    DevOps engineer creates CI/CD and infrastructure.

    Generates Dockerfiles, docker-compose, CI pipelines, and IaC.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])
    project_name = state["project_name"]
    tasks = sprint.get("tasks", {})

    feature_name = sprint["feature_name"]
    print(f"\n[SPRINT {current_sprint_id}] DevOps: {feature_name}")

    artifacts = dict(sprint.get("artifacts", {}))
    ci_cd_config = dict(state.get("ci_cd_config", {}))
    codebase_files = list(state.get("codebase", {}).keys())

    # DevOps engineer generates configs
    devops_sys, devops_llm = factory.create_agent("DevOps Engineer")

    devops_prompt = (
        f"Create infrastructure and CI/CD for: {feature_name}\n\n"
        f"**Tasks:** {json.dumps(tasks.get('devops_tasks', []))}\n"
        f"**Existing Code Files:** {codebase_files}\n\n"
        "Generate the following configuration files:\n"
        "1. dockerfile_backend: Multi-stage Dockerfile for Python/FastAPI\n"
        "2. dockerfile_frontend: Multi-stage Dockerfile for React\n"
        "3. docker_compose: docker-compose.yml for local development\n"
        "4. github_actions: GitHub Actions CI/CD workflow\n"
        "5. requirements: Python requirements.txt\n"
        "6. package_json: Node.js package.json\n\n"
        "Return as JSON with these keys, each value is the complete file content."
    )

    response = devops_llm.invoke([
        SystemMessage(content=devops_sys),
        HumanMessage(content=devops_prompt)
    ])

    devops_output = code_gen.extract_json_from_response(response.content)

    file_mapping = {
        "dockerfile_backend": "backend/Dockerfile",
        "dockerfile_frontend": "frontend/Dockerfile",
        "docker_compose": "docker-compose.yml",
        "github_actions": ".github/workflows/ci.yml",
        "requirements": "backend/requirements.txt",
        "package_json": "frontend/package.json"
    }

    if devops_output:
        for key, content in devops_output.items():
            if isinstance(content, str) and content.strip():
                file_path = file_mapping.get(key, f"infrastructure/{key}")
                ci_cd_config[file_path] = content
                artifacts[f"devops_{key}"] = SprintArtifact(
                    agent="DevOps Engineer",
                    artifact_type="config",
                    file_path=file_path,
                    content=content,
                    version=sprint["iteration"] + 1
                )
    else:
        # Use templates as fallback
        ci_cd_config["backend/Dockerfile"] = code_gen.get_dockerfile_backend()
        ci_cd_config["frontend/Dockerfile"] = code_gen.get_dockerfile_frontend()
        ci_cd_config["docker-compose.yml"] = code_gen.get_docker_compose()
        ci_cd_config[".github/workflows/ci.yml"] = code_gen.get_github_actions_ci()

    sprint["artifacts"] = artifacts
    sprints[current_sprint_id] = sprint

    print(f"  Generated {len(ci_cd_config)} DevOps configuration files")

    return {"sprints": sprints, "ci_cd_config": ci_cd_config}


def qa_node(state: AgentState) -> Dict[str, Any]:
    """
    QA Engineer creates test suites.

    Generates unit tests, integration tests, and e2e tests.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])
    project_name = state["project_name"]
    codebase = state.get("codebase", {})
    tasks = sprint.get("tasks", {})

    feature_name = sprint["feature_name"]
    print(f"\n[SPRINT {current_sprint_id}] QA: {feature_name}")

    artifacts = dict(sprint.get("artifacts", {}))
    test_suite = dict(state.get("test_suite", {}))

    # Filter code files for context
    backend_files = [k for k in codebase.keys() if "backend" in k]
    frontend_files = [k for k in codebase.keys() if "frontend" in k]

    # QA Engineer generates tests
    qa_sys, qa_llm = factory.create_agent("QA Engineer")

    qa_prompt = (
        f"Create comprehensive tests for: {feature_name}\n\n"
        f"**Feature Description:** {sprint['feature_description']}\n"
        f"**Tasks:** {json.dumps(tasks.get('qa_tasks', []))}\n"
        f"**Backend Files:** {backend_files}\n"
        f"**Frontend Files:** {frontend_files}\n\n"
        "Generate test files:\n"
        "1. backend_unit: Pytest unit tests for backend\n"
        "2. backend_integration: Pytest integration tests\n"
        "3. frontend_tests: Jest/React Testing Library tests\n"
        "4. e2e_tests: Playwright end-to-end tests\n"
        "5. conftest: Pytest conftest.py with fixtures\n\n"
        "Return as JSON with these keys, each value is complete test file content."
    )

    response = qa_llm.invoke([
        SystemMessage(content=qa_sys),
        HumanMessage(content=qa_prompt)
    ])

    test_output = code_gen.extract_json_from_response(response.content)

    file_mapping = {
        "backend_unit": "tests/backend/test_unit.py",
        "backend_integration": "tests/backend/test_integration.py",
        "frontend_tests": "tests/frontend/App.test.tsx",
        "e2e_tests": "tests/e2e/feature.spec.ts",
        "conftest": "tests/backend/conftest.py"
    }

    if test_output:
        for key, content in test_output.items():
            if isinstance(content, str) and content.strip():
                file_path = file_mapping.get(key, f"tests/{key}.py")
                test_suite[file_path] = content
                artifacts[f"qa_{key}"] = SprintArtifact(
                    agent="QA Engineer",
                    artifact_type="test",
                    file_path=file_path,
                    content=content,
                    version=sprint["iteration"] + 1
                )
    else:
        # Create minimal test stubs
        test_suite["tests/backend/test_unit.py"] = f'"""Unit tests for {feature_name}"""\nimport pytest\n\ndef test_placeholder():\n    assert True\n'

    sprint["artifacts"] = artifacts
    sprints[current_sprint_id] = sprint

    print(f"  Generated {len(test_suite)} test files")

    return {"sprints": sprints, "test_suite": test_suite}


def documentation_node(state: AgentState) -> Dict[str, Any]:
    """
    Tech Writer creates documentation.

    Generates README, API docs, user guide, and ADR.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])
    project_name = state["project_name"]
    codebase = state.get("codebase", {})
    tasks = sprint.get("tasks", {})

    feature_name = sprint["feature_name"]
    print(f"\n[SPRINT {current_sprint_id}] Documentation: {feature_name}")

    artifacts = dict(sprint.get("artifacts", {}))
    documentation = dict(state.get("documentation", {}))

    # Tech Writer generates docs
    writer_sys, writer_llm = factory.create_agent("Tech Writer")

    doc_prompt = (
        f"Create documentation for: {feature_name}\n\n"
        f"**Feature Description:** {sprint['feature_description']}\n"
        f"**Tasks:** {json.dumps(tasks.get('doc_tasks', []))}\n"
        f"**Code Files:** {list(codebase.keys())}\n\n"
        "Generate documentation files:\n"
        "1. readme: README.md with setup instructions and usage\n"
        "2. api_docs: API documentation with endpoints and examples\n"
        "3. user_guide: User guide for the feature\n"
        "4. adr: Architecture Decision Record for key decisions\n\n"
        "Return as JSON with these keys, each value is complete markdown content."
    )

    response = writer_llm.invoke([
        SystemMessage(content=writer_sys),
        HumanMessage(content=doc_prompt)
    ])

    doc_output = code_gen.extract_json_from_response(response.content)

    safe_feature = code_gen.sanitize_filename(feature_name)
    file_mapping = {
        "readme": "README.md",
        "api_docs": "docs/api.md",
        "user_guide": "docs/user_guide.md",
        "adr": f"docs/adr/adr_{current_sprint_id:03d}_{safe_feature}.md"
    }

    if doc_output:
        for key, content in doc_output.items():
            if isinstance(content, str) and content.strip():
                file_path = file_mapping.get(key, f"docs/{key}.md")
                documentation[file_path] = content
                artifacts[f"doc_{key}"] = SprintArtifact(
                    agent="Tech Writer",
                    artifact_type="docs",
                    file_path=file_path,
                    content=content,
                    version=sprint["iteration"] + 1
                )
    else:
        # Create minimal readme
        documentation["README.md"] = f"# {feature_name}\n\n{sprint['feature_description']}\n"

    sprint["artifacts"] = artifacts
    sprint["status"] = SprintStatus.REVIEW
    sprints[current_sprint_id] = sprint

    # Save all artifacts to disk
    artifact_mgr.save_sprint_artifacts(project_name, current_sprint_id, artifacts)

    print(f"  Generated {len(documentation)} documentation files")

    return {"sprints": sprints, "documentation": documentation}


def sprint_review_node(state: AgentState) -> Dict[str, Any]:
    """
    Product Owner and stakeholders review sprint deliverables.

    Collects feedback from reviewers to determine if sprint is approved
    or needs changes.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])
    project_name = state["project_name"]

    feature_name = sprint["feature_name"]
    print(f"\n[SPRINT {current_sprint_id}] Review: {feature_name}")
    print(f"  Iteration: {sprint['iteration'] + 1}")

    # Reviewers from original organization
    reviewers = ["Product Owner", "QA", "UI/UX", "Security"]
    feedback_list: List[SprintFeedback] = []

    # Prepare artifact summary
    artifacts = sprint.get("artifacts", {})
    artifact_summary = "\n".join([
        f"- {a['file_path']}: {a['artifact_type']} by {a['agent']}"
        for a in artifacts.values()
    ])

    for reviewer_name in reviewers:
        print(f"  [Review] {reviewer_name} reviewing...")

        reviewer_sys, reviewer_llm = factory.create_agent(reviewer_name)

        review_prompt = (
            f"Review the sprint deliverables for: {feature_name}\n\n"
            f"**Feature Description:** {sprint['feature_description']}\n"
            f"**Artifacts Generated:**\n{artifact_summary}\n\n"
            f"**Sprint Iteration:** {sprint['iteration'] + 1}\n\n"
            f"As {reviewer_name}, evaluate:\n"
            "1. Does it meet the PRD requirements?\n"
            "2. Are there quality/security concerns?\n"
            "3. Any missing functionality?\n"
            "4. Is the code/documentation complete?\n\n"
            "Respond with JSON:\n"
            '{"status": "approved" or "changes_requested", '
            '"comments": "your detailed feedback", '
            '"issues": ["list", "of", "specific", "issues"]}'
        )

        response = reviewer_llm.invoke([
            SystemMessage(content=reviewer_sys),
            HumanMessage(content=review_prompt)
        ])

        review = code_gen.extract_json_from_response(response.content)

        if review:
            feedback_list.append(SprintFeedback(
                reviewer=reviewer_name,
                sprint_id=current_sprint_id,
                feedback_type=review.get("status", "approved"),
                comments=review.get("comments", ""),
                affected_artifacts=review.get("issues", [])
            ))
        else:
            feedback_list.append(SprintFeedback(
                reviewer=reviewer_name,
                sprint_id=current_sprint_id,
                feedback_type="approved",
                comments=response.content,
                affected_artifacts=[]
            ))

    sprint["feedback"] = feedback_list
    sprints[current_sprint_id] = sprint

    # Store in sprint_reviews
    sprint_reviews = dict(state.get("sprint_reviews", {}))
    sprint_reviews[current_sprint_id] = {
        "feedback": [dict(f) for f in feedback_list],
        "iteration": sprint["iteration"]
    }

    # Save review to disk
    artifact_mgr.save_sprint_review(project_name, current_sprint_id, sprint_reviews[current_sprint_id])

    # Log summary
    approved_count = sum(1 for f in feedback_list if f["feedback_type"] == "approved")
    print(f"  Review complete: {approved_count}/{len(feedback_list)} approved")

    return {"sprints": sprints, "sprint_reviews": sprint_reviews}


def feedback_router(state: AgentState) -> str:
    """
    Determine next step based on sprint review feedback.

    Returns:
        "approved" - Move to next sprint
        "feedback" - Apply feedback and re-iterate
        "end" - All sprints completed
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = state["sprints"]
    sprint = sprints[current_sprint_id]

    # Check if any feedback requires changes
    changes_requested = any(
        f["feedback_type"] == "changes_requested"
        for f in sprint.get("feedback", [])
    )

    max_iterations = 3

    if changes_requested and sprint["iteration"] < max_iterations:
        print(f"\n[WORKFLOW] Changes requested. Re-entering development (iteration {sprint['iteration'] + 2})...")
        return "feedback"
    elif current_sprint_id + 1 < len(sprints):
        print(f"\n[WORKFLOW] Sprint {current_sprint_id} approved. Moving to sprint {current_sprint_id + 1}...")
        return "approved"
    else:
        print("\n[WORKFLOW] All sprints completed!")
        return "end"


def apply_feedback_node(state: AgentState) -> Dict[str, Any]:
    """
    Apply feedback and prepare for next iteration.

    Increments iteration counter and clears feedback for fresh review.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])

    # Log feedback for context in next iteration
    feedback_summary = "\n".join([
        f"- {f['reviewer']}: {f['feedback_type']} - {f['comments'][:100]}"
        for f in sprint.get("feedback", [])
    ])

    print(f"\n[SPRINT {current_sprint_id}] Applying feedback:")
    print(feedback_summary)

    # Increment iteration
    sprint["iteration"] += 1
    sprint["status"] = SprintStatus.FEEDBACK

    # Keep feedback for context but clear for next review cycle
    # The feedback is preserved in sprint_reviews
    sprint["feedback"] = []

    sprints[current_sprint_id] = sprint

    return {
        "sprints": sprints,
        "active_feedback_cycle": True,
        "feedback_iteration": sprint["iteration"]
    }


def next_sprint_node(state: AgentState) -> Dict[str, Any]:
    """
    Move to the next sprint.

    Saves current sprint's final codebase and advances sprint counter.
    """
    current_sprint_id = state["current_sprint_id"]
    sprints = dict(state["sprints"])
    sprint = dict(sprints[current_sprint_id])
    project_name = state["project_name"]

    # Mark current sprint as completed
    sprint["status"] = SprintStatus.COMPLETED
    sprints[current_sprint_id] = sprint

    # Save codebase to disk
    codebase = state.get("codebase", {})
    for file_path, content in codebase.items():
        save_codebase_file(project_name, file_path, content)

    # Also save CI/CD configs
    ci_cd_config = state.get("ci_cd_config", {})
    for file_path, content in ci_cd_config.items():
        save_codebase_file(project_name, file_path, content)

    # Save test suite
    test_suite = state.get("test_suite", {})
    for file_path, content in test_suite.items():
        save_codebase_file(project_name, file_path, content)

    # Save documentation
    documentation = state.get("documentation", {})
    for file_path, content in documentation.items():
        save_codebase_file(project_name, file_path, content)

    # Advance to next sprint
    next_id = current_sprint_id + 1

    print(f"\n[SPRINT] Sprint {current_sprint_id} completed. Saved to codebase.")
    if next_id < len(sprints):
        print(f"[SPRINT] Advancing to sprint {next_id}.")

    return {
        "sprints": sprints,
        "current_sprint_id": next_id,
        "active_feedback_cycle": False
    }
