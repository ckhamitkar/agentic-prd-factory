
import os
import json
import uuid
import threading
import queue
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables before any other imports
load_dotenv()

from urllib.parse import quote
import mimetypes
from flask import Flask, render_template, request, jsonify, Response, send_from_directory, make_response

from src.main import run_pipeline
from src.tools.io import load_portfolio, PROJECTS_DIR

app = Flask(__name__)

# In-memory job tracking: {job_id: {"status": str, "queue": Queue, "result": dict}}
_jobs = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    """Start a pipeline run in a background thread."""
    data = request.get_json()
    opportunity = data.get("opportunity", "").strip()
    project_name = data.get("project_name", "").strip()
    mode = data.get("mode", "prd_only")
    skip_ceo = data.get("skip_ceo", False)

    if not opportunity:
        return jsonify({"error": "Opportunity text is required."}), 400
    if not project_name:
        return jsonify({"error": "Project name is required."}), 400

    # Sanitize project name for filesystem — strip quotes, dashes, special chars
    import re as _re
    safe_name = _re.sub(r'[^a-zA-Z0-9_\-]', '_', project_name)
    safe_name = _re.sub(r'_+', '_', safe_name).strip('_')

    job_id = str(uuid.uuid4())[:8]
    log_queue = queue.Queue()
    _jobs[job_id] = {"status": "running", "queue": log_queue, "result": None}

    def log_callback(msg):
        log_queue.put({"type": "log", "message": msg})

    def worker():
        try:
            result = run_pipeline(
                opportunity_text=opportunity,
                project_name=safe_name,
                mode=mode,
                skip_ceo=skip_ceo,
                log_callback=log_callback,
            )
            # Serialize result for JSON (convert enums, etc.)
            serializable = _serialize_result(result)
            _jobs[job_id]["result"] = serializable
            _jobs[job_id]["status"] = "done"
            log_queue.put({"type": "done", "result": serializable})
        except Exception as e:
            _jobs[job_id]["status"] = "error"
            log_queue.put({"type": "error", "message": str(e)})

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    """SSE endpoint that streams log messages for a running job."""
    if job_id not in _jobs:
        return jsonify({"error": "Job not found"}), 404

    def stream():
        q = _jobs[job_id]["queue"]
        while True:
            try:
                msg = q.get(timeout=120)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("type") in ("done", "error"):
                    break
            except queue.Empty:
                # Send keepalive
                yield f"data: {json.dumps({'type': 'log', 'message': '... still running ...'})}\n\n"

    return Response(stream(), mimetype="text/event-stream")


@app.route("/portfolio")
def portfolio():
    """Return portfolio data as JSON."""
    data = load_portfolio()
    return jsonify(data)


@app.route("/projects")
def projects():
    """Return list of project names."""
    if not os.path.exists(PROJECTS_DIR):
        return jsonify([])
    dirs = [
        d for d in sorted(os.listdir(PROJECTS_DIR))
        if os.path.isdir(os.path.join(PROJECTS_DIR, d))
    ]
    return jsonify(dirs)


@app.route("/files/<path:filepath>")
def serve_file(filepath):
    """Serve files from the projects directory."""
    full_path = os.path.join(PROJECTS_DIR, filepath)

    # If it's a directory, list contents as links
    if os.path.isdir(full_path):
        files = []
        for item in sorted(os.listdir(full_path)):
            item_path = os.path.join(filepath, item)
            is_dir = os.path.isdir(os.path.join(PROJECTS_DIR, item_path))
            files.append({"name": item + ("/" if is_dir else ""), "path": item_path})

        html = f"<html><head><title>{filepath}</title>"
        html += "<style>body{font-family:monospace;padding:20px;} a{color:#2c5282;}</style>"
        html += f"</head><body><h2>{filepath}</h2><ul>"
        for f in files:
            encoded_path = quote(f["path"], safe='/')
            html += f'<li><a href="/files/{encoded_path}">{f["name"]}</a></li>'
        html += "</ul></body></html>"
        return html

    # Serve the file directly (avoids send_from_directory issues with special chars)
    if not os.path.exists(full_path):
        return "File not found", 404

    mime_type, _ = mimetypes.guess_type(full_path)
    if mime_type and mime_type.startswith("text") or full_path.endswith(".md"):
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        resp = make_response(content)
        resp.headers["Content-Type"] = "text/plain; charset=utf-8"
        return resp
    else:
        with open(full_path, "rb") as f:
            content = f.read()
        resp = make_response(content)
        resp.headers["Content-Type"] = mime_type or "application/octet-stream"
        return resp


def _serialize_result(result):
    """Convert workflow result to JSON-serializable dict."""
    out = {}
    for key, val in result.items():
        if hasattr(val, "value"):  # Enum
            out[key] = val.value
        elif isinstance(val, (str, int, float, bool, list, dict, type(None))):
            out[key] = val
        else:
            out[key] = str(val)
    return out


if __name__ == "__main__":
    print("=" * 50)
    print("Agentic PRD Factory - Web UI")
    print("Open http://localhost:5000 in your browser")
    print("=" * 50)
    app.run(debug=False, port=5000)
