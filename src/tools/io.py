
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

PROJECTS_DIR = "projects"


def get_project_dirs(project_name: str) -> Tuple[str, str]:
    """Get output and logs directories for a project."""
    base = os.path.join(PROJECTS_DIR, project_name)
    return os.path.join(base, "output"), os.path.join(base, "logs")


def get_sprint_dir(project_name: str, sprint_id: int) -> str:
    """Get the directory for a specific sprint."""
    return os.path.join(PROJECTS_DIR, project_name, "sprints", f"sprint_{sprint_id}")


def get_codebase_dir(project_name: str) -> str:
    """Get the final codebase directory for a project."""
    return os.path.join(PROJECTS_DIR, project_name, "codebase")


def ensure_dirs(project_name: str) -> None:
    """Ensure output and logs directories exist."""
    out_dir, log_dir = get_project_dirs(project_name)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)


def ensure_sprint_dirs(project_name: str, sprint_id: int) -> str:
    """
    Ensure all directories for a sprint exist.

    Returns:
        Path to the sprint directory.
    """
    sprint_dir = get_sprint_dir(project_name, sprint_id)
    subdirs = ["planning", "backend", "frontend", "devops", "tests", "docs", "review"]

    for subdir in subdirs:
        os.makedirs(os.path.join(sprint_dir, subdir), exist_ok=True)

    return sprint_dir


def ensure_codebase_dirs(project_name: str) -> str:
    """
    Ensure all directories for the codebase exist.

    Returns:
        Path to the codebase directory.
    """
    codebase_dir = get_codebase_dir(project_name)
    subdirs = ["backend", "frontend", "infrastructure", "docs", "tests"]

    for subdir in subdirs:
        os.makedirs(os.path.join(codebase_dir, subdir), exist_ok=True)

    return codebase_dir

def read_opportunity(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def save_draft(agent_name: str, content: str, round_num: int, project_name: str):
    """Saves a single agent's draft."""
    ensure_dirs(project_name)
    out_dir, _ = get_project_dirs(project_name)
    safe_name = agent_name.replace(' ', '_').replace('/', '_')
    filename = f"{out_dir}/draft_r{round_num}_{safe_name}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def save_prd(content: str, round_num: int, project_name: str):
    """Saves the compiled PRD."""
    ensure_dirs(project_name)
    out_dir, _ = get_project_dirs(project_name)
    filename = f"{out_dir}/prd_round_{round_num}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)

def log_monologue(step_name: str, agent_name: str, thought_process: str, project_name: str):
    """Logs the internal monologue/reasoning of an agent."""
    ensure_dirs(project_name)
    _, log_dir = get_project_dirs(project_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = agent_name.replace(' ', '_').replace('/', '_')
    filename = f"{log_dir}/{timestamp}_{step_name}_{safe_name}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Agent: {agent_name}\nStep: {step_name}\nTimestamp: {timestamp}\n\n{thought_process}")

def convert_to_pdf(markdown_content: str, output_path: str) -> None:
    """Converts markdown content to a PDF file."""
    import markdown2
    try:
        from xhtml2pdf import pisa
    except ImportError:
        print(f"[WARNING] xhtml2pdf not installed - skipping PDF generation. Markdown saved instead.")
        md_path = output_path.replace('.pdf', '.md')
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        return
    import re

    # Strip markdown code fences if the LLM wrapped the response in them
    # This handles ```markdown ... ``` or ``` ... ``` wrappers
    content = markdown_content.strip()

    # Remove opening code fence (```markdown, ```md, or just ```)
    content = re.sub(r'^```(?:markdown|md)?\s*\n', '', content)
    # Remove closing code fence
    content = re.sub(r'\n```\s*$', '', content)

    # Professional CSS styling
    css = """
    <style>
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #333;
            margin: 40px;
        }
        h1 {
            color: #1a365d;
            border-bottom: 3px solid #2c5282;
            padding-bottom: 10px;
            font-size: 24pt;
            margin-top: 30px;
        }
        h2 {
            color: #2c5282;
            margin-top: 25px;
            border-bottom: 1px solid #cbd5e0;
            padding-bottom: 5px;
            font-size: 16pt;
        }
        h3 {
            color: #4a5568;
            margin-top: 20px;
            font-size: 13pt;
        }
        p { margin: 10px 0; }
        ul, ol { margin: 10px 0 10px 20px; }
        li { margin: 5px 0; }
        strong, b { color: #1a202c; }
        em, i { color: #4a5568; }
        pre {
            background-color: #f7fafc;
            padding: 15px;
            border: 1px solid #e2e8f0;
            border-radius: 5px;
            font-size: 9pt;
            overflow-x: auto;
        }
        code {
            background-color: #edf2f7;
            font-family: 'Courier New', Courier, monospace;
            padding: 2px 5px;
            border-radius: 3px;
            font-size: 10pt;
        }
        blockquote {
            border-left: 4px solid #4299e1;
            padding-left: 15px;
            color: #4a5568;
            margin: 15px 0;
            font-style: italic;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            margin: 15px 0;
        }
        th, td {
            border: 1px solid #e2e8f0;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #edf2f7;
            font-weight: bold;
        }
        hr {
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 20px 0;
        }
    </style>
    """

    # Convert markdown to HTML with extras
    html_content = markdown2.markdown(
        content,
        extras=["tables", "fenced-code-blocks", "header-ids", "strike", "task_list"]
    )

    full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    {css}
</head>
<body>
    {html_content}
</body>
</html>"""

    with open(output_path, "wb") as f:
        pisa.CreatePDF(full_html, dest=f)


# ============================================================================
# Sprint and Codebase I/O Functions
# ============================================================================

def save_code_artifact(
    project_name: str,
    file_path: str,
    content: str,
    target: str = "codebase"
) -> str:
    """
    Save a code artifact to the codebase or sprint directory.

    Args:
        project_name: Name of the project
        file_path: Relative path within the target directory
        content: File content to save
        target: Either "codebase" or "sprint_{id}"

    Returns:
        Full path to saved file.
    """
    if target == "codebase":
        base_dir = ensure_codebase_dirs(project_name)
    elif target.startswith("sprint_"):
        sprint_id = int(target.split("_")[1])
        base_dir = ensure_sprint_dirs(project_name, sprint_id)
    else:
        base_dir = ensure_codebase_dirs(project_name)

    full_path = os.path.join(base_dir, file_path)

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    return full_path


def save_sprint_log(
    project_name: str,
    sprint_id: int,
    phase: str,
    content: str
) -> str:
    """
    Log sprint phase activity.

    Args:
        project_name: Name of the project
        sprint_id: Sprint identifier
        phase: Phase name (e.g., "planning", "development", "review")
        content: Log content

    Returns:
        Path to saved log file.
    """
    sprint_dir = ensure_sprint_dirs(project_name, sprint_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_phase = phase.replace(' ', '_').replace('/', '_')

    filename = os.path.join(sprint_dir, f"{timestamp}_{safe_phase}.md")

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# Sprint {sprint_id} - {phase}\n")
        f.write(f"**Timestamp:** {datetime.now().isoformat()}\n\n")
        f.write(content)

    return filename


def save_codebase_file(
    project_name: str,
    file_path: str,
    content: str
) -> str:
    """
    Save a file to the final codebase directory.

    Args:
        project_name: Name of the project
        file_path: Relative path within codebase
        content: File content

    Returns:
        Full path to saved file.
    """
    codebase_dir = ensure_codebase_dirs(project_name)
    full_path = os.path.join(codebase_dir, file_path)

    # Ensure parent directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)

    return full_path


def load_codebase_file(project_name: str, file_path: str) -> Optional[str]:
    """
    Load a file from the codebase directory.

    Returns:
        File content or None if file doesn't exist.
    """
    codebase_dir = get_codebase_dir(project_name)
    full_path = os.path.join(codebase_dir, file_path)

    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    return None


def list_codebase_files(project_name: str) -> List[str]:
    """
    List all files in the codebase directory.

    Returns:
        List of relative file paths.
    """
    codebase_dir = get_codebase_dir(project_name)
    files = []

    if not os.path.exists(codebase_dir):
        return files

    for root, _, filenames in os.walk(codebase_dir):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            rel_path = os.path.relpath(full_path, codebase_dir)
            files.append(rel_path)

    return files


# ============================================================================
# Product Context Loading
# ============================================================================

def load_product_context(context_file: str = "product_context.md") -> str:
    """Load the product context the factory scores opportunities against.

    Returns the full text content so it can be injected into agent prompts.
    Falls back to a short generic summary if the file is missing.
    """
    if os.path.exists(context_file):
        with open(context_file, "r", encoding="utf-8") as f:
            return f.read()
    return (
        "This is the product context / business model the factory scores "
        "opportunities against. Replace product_context.md with your own to "
        "define the goals, constraints, and priorities every agent should "
        "evaluate ideas against."
    )


# ============================================================================
# Portfolio JSON Management
# ============================================================================

PORTFOLIO_FILE = os.path.join(PROJECTS_DIR, "portfolio.json")


def load_portfolio() -> List[Dict]:
    """Load the persistent portfolio JSON file. Returns empty list if not found."""
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_portfolio_entry(entry: Dict) -> None:
    """Append a new entry to the portfolio JSON and save."""
    portfolio = load_portfolio()
    portfolio.append(entry)
    os.makedirs(os.path.dirname(PORTFOLIO_FILE), exist_ok=True)
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(portfolio, f, indent=2, default=str)


def generate_portfolio_view() -> None:
    """Regenerate portfolio_view.md and portfolio_view.pdf from portfolio.json.

    Ranks all entries by composite priority_score descending.
    """
    portfolio = load_portfolio()
    if not portfolio:
        return

    ranked = sorted(portfolio, key=lambda x: x.get("priority_score", 0), reverse=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    md_lines = [
        "# Portfolio View - Monthly Idea Rankings",
        f"\n**Generated:** {now}",
        f"**Total Ideas Evaluated:** {len(ranked)}\n",
        "| Rank | Project | Score | Reach | Feasibility | Viability | Date |",
        "|------|---------|-------|-------|-------------|-----------|------|",
    ]

    for i, entry in enumerate(ranked, 1):
        breakdown = entry.get("score_breakdown", {})
        date_str = entry.get("date", "N/A")
        if isinstance(date_str, str) and "T" in date_str:
            date_str = date_str.split("T")[0]
        md_lines.append(
            f"| {i} | {entry.get('project_name', 'N/A')} "
            f"| **{entry.get('priority_score', 0):.1f}** "
            f"| {breakdown.get('reach', 'N/A')} "
            f"| {breakdown.get('technical_feasibility', 'N/A')} "
            f"| {breakdown.get('enterprise_buyin', 'N/A')} "
            f"| {date_str} |"
        )

    md_lines.append("\n---\n")
    md_lines.append("## Scoring Methodology")
    md_lines.append("- **Reach** (40%): Size of the target user population (1-10)")
    md_lines.append("- **Technical Feasibility** (30%): How difficult is it to implement? (1-10)")
    md_lines.append("- **Business Viability** (30%): Is there a willing buyer / sustainable model? (1-10)")
    md_lines.append("- **Composite** = Reach * 0.4 + Feasibility * 0.3 + Viability * 0.3")

    md_content = "\n".join(md_lines)

    md_path = os.path.join(PROJECTS_DIR, "portfolio_view.md")
    os.makedirs(PROJECTS_DIR, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    pdf_path = os.path.join(PROJECTS_DIR, "portfolio_view.pdf")
    convert_to_pdf(md_content, pdf_path)
