"""FastAPI Dashboard Server for Blog Curator Agent.
Provides REST API endpoints and serves an interactive web dashboard for viewing tool reports and post analytics.
"""

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.cloud import firestore

from app.agent import (
    PROJECT_ID,
    assess_posts,
    fetch_posts,
    get_posts_by_score,
    get_posts_by_tag,
    get_recent_posts,
    summarize_posts,
)

app = FastAPI(title="Blog Curator Agent Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORTS_DIR = Path(__file__).parent.parent / "reports"


@app.get("/api/metrics")
def get_metrics():
    """Return collection-wide metrics from Firestore."""
    try:
        db = firestore.Client(project=PROJECT_ID)
        docs = [d.to_dict() for d in db.collection("posts").stream()]
        total = len(docs)
        if total == 0:
            return {
                "total_posts": 0,
                "average_score": 0,
                "strong_count": 0,
                "average_count": 0,
                "weak_count": 0,
                "missing_tags_count": 0,
            }

        weak_count = sum(1 for d in docs if d.get("content_strength") == "weak")
        strong_count = sum(1 for d in docs if d.get("content_strength") == "strong")
        average_count = sum(1 for d in docs if d.get("content_strength") == "average")
        missing_tags_count = sum(1 for d in docs if d.get("missing_tags") is True)
        avg_score = round(sum(d.get("score", 0) for d in docs) / total, 2)

        return {
            "total_posts": total,
            "average_score": avg_score,
            "strong_count": strong_count,
            "average_count": average_count,
            "weak_count": weak_count,
            "missing_tags_count": missing_tags_count,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/reports")
def list_reports():
    """Return all available markdown reports in the reports/ directory."""
    if not REPORTS_DIR.exists():
        return {"reports": []}

    reports = []
    for file in sorted(REPORTS_DIR.glob("*.md")):
        content = file.read_text(encoding="utf-8")
        mtime = os.path.getmtime(file)
        reports.append({
            "name": file.stem,
            "filename": file.name,
            "modified_timestamp": mtime,
            "content": content,
        })
    return {"reports": reports}


@app.get("/api/reports/{report_name}")
def get_report(report_name: str):
    """Return specific report content."""
    filename = f"{report_name}.md" if not report_name.endswith(".md") else report_name
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Report {filename} not found.")
    return {
        "name": filepath.stem,
        "filename": filepath.name,
        "content": filepath.read_text(encoding="utf-8"),
    }


@app.get("/api/posts")
def list_posts():
    """Return all assessed posts stored in Firestore."""
    try:
        db = firestore.Client(project=PROJECT_ID)
        docs = [d.to_dict() for d in db.collection("posts").stream()]
        docs.sort(key=lambda x: x.get("published_date", ""), reverse=True)
        return {"posts": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/run-tool")
def run_tool(tool_name: str, param: Optional[str] = None):
    """Dynamically execute a tool and return the output."""
    try:
        if tool_name == "summarize_posts":
            result = summarize_posts()
        elif tool_name == "get_posts_by_score":
            order = param if param in ("best", "worst") else "best"
            result = get_posts_by_score(order=order, limit=10)
        elif tool_name == "get_recent_posts":
            limit = int(param) if param and param.isdigit() else 10
            result = get_recent_posts(limit=limit)
        elif tool_name == "get_posts_by_tag":
            tag = param if param else "Japanese"
            result = get_posts_by_tag(tag=tag)
        elif tool_name == "assess_posts":
            result = assess_posts()
        elif tool_name == "fetch_posts":
            result = fetch_posts()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")

        return {"tool": tool_name, "param": param, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve static HTML UI
DASHBOARD_HTML_PATH = Path(__file__).parent.parent / "dashboard" / "index.html"


@app.get("/", response_class=HTMLResponse)
def index():
    if not DASHBOARD_HTML_PATH.exists():
        return HTMLResponse("<h1>Dashboard HTML not found</h1>", status_code=404)
    return HTMLResponse(content=DASHBOARD_HTML_PATH.read_text(encoding="utf-8"))
