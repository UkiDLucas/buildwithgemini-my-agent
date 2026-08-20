# ruff: noqa
import datetime
import glob
import html
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.cloud import firestore
from google.genai import types

from .a2ui_utils import a2ui_callback

MODEL = "gemini-2.5-flash"
PROJECT_ID = "qwiklabs-gcp-03-001b5a0cda08"


def _write_tool_report(tool_name: str, params: dict, content_markdown: str) -> None:
    """Helper to write a Markdown report file in reports/<tool_name>.md."""
    os.makedirs("reports", exist_ok=True)
    filepath = f"reports/{tool_name}.md"
    now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    param_str = ", ".join(f"{k}={repr(v)}" for k, v in params.items()) if params else "none"

    report_text = f"""# Report: {tool_name}

**Timestamp**: {now_str}  
**Parameters**: {param_str}  

{content_markdown}
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report_text)


def fetch_posts() -> str:
    """Fetches up to 10 recent posts from ukidlucas.blogspot.com (Atom XML feed),
    parses title, date, URL, tags, plain text content, and writes each new post
    to posts/YYYY-MM-DD-slug.md. Skips files that already exist. Also writes a report
    to reports/fetch_posts.md.

    Returns:
        A message describing newly created markdown post files.
    """
    url = "https://ukidlucas.blogspot.com/feeds/posts/default?max-results=10"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        xml_data = resp.read()

    root = ET.fromstring(xml_data)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)

    os.makedirs("posts", exist_ok=True)
    new_files = []
    fetched_records = []

    for entry in entries:
        title = entry.findtext("atom:title", default="Untitled", namespaces=ns).strip()
        published = entry.findtext("atom:published", default="", namespaces=ns)[:10]

        link_elem = entry.find("atom:link[@rel='alternate']", ns)
        post_url = link_elem.attrib.get("href", "") if link_elem is not None else ""

        categories = [
            c.attrib["term"]
            for c in entry.findall("atom:category", ns)
            if "term" in c.attrib
        ]

        content_html = entry.findtext(
            "atom:content", default="", namespaces=ns
        ) or entry.findtext("atom:summary", default="", namespaces=ns)
        content_text = re.sub(r"<[^>]+>", "", content_html)
        content_text = html.unescape(content_text).strip()

        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        if not slug:
            slug = "post"

        filename = f"posts/{published}-{slug}.md"
        is_new = not os.path.exists(filename)

        if is_new:
            tags_str = ", ".join(categories)
            markdown_content = f"""---
title: {title}
published_date: {published}
url: {post_url}
tags: [{tags_str}]
---

{content_text}
"""
            with open(filename, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            new_files.append(filename)

        fetched_records.append({
            "title": title,
            "published": published,
            "url": post_url,
            "file": filename,
            "status": "Created" if is_new else "Existing (Skipped)",
        })

    # Generate Markdown report table
    report_rows = ["| Published Date | Title | Status | Saved File | URL |", "|---|---|---|---|---|"]
    for r in fetched_records:
        report_rows.append(f"| {r['published']} | {r['title']} | {r['status']} | `{r['file']}` | [{r['url']}]({r['url']}) |")

    report_md = "## Fetched Feed Entries\n\n" + "\n".join(report_rows)
    _write_tool_report("fetch_posts", {}, report_md)

    if not new_files:
        return "No new posts to fetch; all posts already exist in posts/."
    return f"Fetched and wrote {len(new_files)} new post(s): {', '.join(new_files)}"


def assess_posts() -> str:
    """Reads post markdown files from posts/, assesses each post for topic tags,
    grammar issues, content strength, word count, and score, then stores one document
    per post in the Firestore collection 'posts'. Writes a report to reports/assess_posts.md.

    Returns:
        A message summarizing the assessment results and Firestore saves.
    """
    db = firestore.Client(project=PROJECT_ID)
    files = glob.glob("posts/*.md")
    if not files:
        _write_tool_report("assess_posts", {}, "No markdown files found in `posts/`.")
        return "No markdown files found in posts/. Call fetch_posts first."

    assessed_records = []

    for filepath in files:
        filename = os.path.basename(filepath)
        doc_id = filename.replace(".md", "")

        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        parts = raw.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body_text = parts[2].strip()
        else:
            fm_text = ""
            body_text = raw.strip()

        title = ""
        published_date = ""
        url = ""
        tags = []

        for line in fm_text.splitlines():
            if line.startswith("title:"):
                title = line.split("title:", 1)[1].strip()
            elif line.startswith("published_date:"):
                published_date = line.split("published_date:", 1)[1].strip()
            elif line.startswith("url:"):
                url = line.split("url:", 1)[1].strip()
            elif line.startswith("tags:"):
                tags_raw = line.split("tags:", 1)[1].strip().strip("[]")
                if tags_raw:
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

        word_count = len(body_text.split())
        missing_tags = len(tags) == 0

        grammar_issues = []
        if re.search(r"[a-zA-Z]\d|\d[a-zA-Z]", body_text):
            grammar_issues.append("Missing spaces between words and numbers (e.g., flour182g)")
        if len(body_text.split(".")) < 3 and word_count > 30:
            grammar_issues.append("Long run-on text with few sentence delimiters")

        if word_count > 150 and not missing_tags:
            content_strength = "strong"
            reason = "Comprehensive, detailed post with clear structure and topic tagging."
            score = 5
        elif word_count >= 50 and not missing_tags:
            content_strength = "average"
            reason = "Provides useful information with clear presentation, though concise."
            score = 3
        else:
            content_strength = "weak"
            if missing_tags and word_count < 50:
                reason = "Very short content lacking both depth and topic tags."
            elif missing_tags:
                reason = "Missing topic tags for classification and discoverability."
            else:
                reason = "Content is short and lacks detailed exposition."
            score = 2 if missing_tags else 1

        doc_data = {
            "id": doc_id,
            "title": title,
            "published_date": published_date,
            "url": url,
            "tags": tags,
            "missing_tags": missing_tags,
            "grammar_issues": grammar_issues,
            "content_strength": content_strength,
            "content_strength_reason": reason,
            "word_count": word_count,
            "score": score,
            "snippet": body_text[:200],
        }

        db.collection("posts").document(doc_id).set(doc_data)
        assessed_records.append(doc_data)

    # Generate Markdown report table
    report_rows = ["| ID | Title | Published Date | Content Strength | Score | Missing Tags | Word Count | Grammar Issues |", "|---|---|---|---|---|---|---|---|"]
    for d in assessed_records:
        g_issues = ", ".join(d["grammar_issues"]) if d["grammar_issues"] else "None"
        report_rows.append(f"| `{d['id']}` | {d['title']} | {d['published_date']} | {d['content_strength']} | {d['score']} | {d['missing_tags']} | {d['word_count']} | {g_issues} |")

    report_md = "## Assessed Posts in Firestore\n\n" + "\n".join(report_rows)
    _write_tool_report("assess_posts", {}, report_md)

    return f"Assessed and saved {len(assessed_records)} post(s) into Firestore collection 'posts'."


def get_posts_by_tag(tag: str) -> str:
    """Queries Firestore collection 'posts' for posts with a specific topic tag.
    Writes a report to reports/get_posts_by_tag.md.

    Args:
        tag: The tag to search for (e.g., 'Japanese', 'book', 'karate').

    Returns:
        JSON string list of matching posts.
    """
    db = firestore.Client(project=PROJECT_ID)
    docs = db.collection("posts").where(filter=firestore.FieldFilter("tags", "array_contains", tag)).stream()
    results = [d.to_dict() for d in docs]
    if not results:
        all_docs = [d.to_dict() for d in db.collection("posts").stream()]
        results = [d for d in all_docs if any(tag.lower() in t.lower() for t in d.get("tags", []))]

    # Generate report
    report_rows = ["| Title | Published Date | Score | Tags | URL |", "|---|---|---|---|---|"]
    for r in results:
        tags_str = ", ".join(r.get("tags", [])) or "None"
        report_rows.append(f"| {r.get('title')} | {r.get('published_date')} | {r.get('score')} | {tags_str} | [{r.get('url')}]({r.get('url')}) |")

    report_md = f"## Posts Matching Tag '{tag}' ({len(results)} found)\n\n" + "\n".join(report_rows)
    _write_tool_report("get_posts_by_tag", {"tag": tag}, report_md)

    return json.dumps(results, indent=2)


def get_posts_by_score(order: str = "best", limit: int = 10) -> str:
    """Queries Firestore collection 'posts' for posts ordered by score (best or worst).
    Writes a report to reports/get_posts_by_score.md.

    Args:
        order: Sort order, either 'best' (highest score first) or 'worst' (lowest score first). Default is 'best'.
        limit: Maximum number of posts to retrieve (default 10).

    Returns:
        JSON string list of matching posts sorted by score.
    """
    db = firestore.Client(project=PROJECT_ID)
    all_docs = [d.to_dict() for d in db.collection("posts").stream()]

    order_clean = order.lower().strip() if isinstance(order, str) else "best"

    if order_clean == "worst":
        # Sort by score ascending (lowest score first), then published_date ascending
        all_docs.sort(key=lambda x: (x.get("score", 5), x.get("published_date", "")))
    else:
        # 'best' -> sort by score descending (highest score first), then published_date descending
        all_docs.sort(key=lambda x: (x.get("score", 0), x.get("published_date", "")), reverse=True)

    results = all_docs[:limit]

    # Generate Markdown report
    report_rows = [
        "| Title | Published Date | Score | Content Strength | Missing Tags | Reason | URL |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in results:
        report_rows.append(
            f"| {p.get('title')} | {p.get('published_date')} | {p.get('score')} | {p.get('content_strength')} | {p.get('missing_tags')} | {p.get('content_strength_reason')} | [{p.get('url')}]({p.get('url')}) |"
        )

    report_md = f"## Posts Ordered by Score ({order_clean.upper()}, Limit: {limit})\n\n" + "\n".join(report_rows)
    _write_tool_report("get_posts_by_score", {"order": order, "limit": limit}, report_md)

    return json.dumps(results, indent=2)


def get_recent_posts(limit: int = 10) -> str:
    """Queries Firestore collection 'posts' for recent posts sorted by published date.
    Writes a report to reports/get_recent_posts.md.

    Args:
        limit: Maximum number of recent posts to retrieve (default 10).

    Returns:
        JSON string list of recent posts.
    """
    db = firestore.Client(project=PROJECT_ID)
    docs = list(
        db.collection("posts")
        .order_by("published_date", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    results = [d.to_dict() for d in docs]
    if not results:
        all_docs = [d.to_dict() for d in db.collection("posts").stream()]
        all_docs.sort(key=lambda x: x.get("published_date", ""), reverse=True)
        results = all_docs[:limit]

    # Generate report
    report_rows = ["| Published Date | Title | Score | Content Strength | Tags | URL |", "|---|---|---|---|---|---|"]
    for r in results:
        tags_str = ", ".join(r.get("tags", [])) or "None"
        report_rows.append(f"| {r.get('published_date')} | {r.get('title')} | {r.get('score')} | {r.get('content_strength')} | {tags_str} | [{r.get('url')}]({r.get('url')}) |")

    report_md = f"## Recent Posts (Limit: {limit})\n\n" + "\n".join(report_rows)
    _write_tool_report("get_recent_posts", {"limit": limit}, report_md)

    return json.dumps(results, indent=2)


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description="You are a Blog Curator Agent. You fetch, assess, and manage blog posts from ukidlucas.blogspot.com stored in Firestore.",
    workflow_description=(
        "Use your tools (fetch_posts, assess_posts, get_posts_by_tag, get_posts_by_score, get_recent_posts) to fulfill user requests. "
        "IMPORTANT CHAT RESPONSE RULE: After every tool call, ALWAYS reply in the chat with a conversational summary digest of the result. "
        "Keep the chat text digest to a MAXIMUM OF 50 WORDS, specifically formatted for a human skimming: include key counts, standouts, and one suggested next action. "
        "The full detailed table or list is automatically written to disk in the reports/ Markdown file; the chat gets only this 50-word digest."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows or Row components. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="blog_curator_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[fetch_posts, assess_posts, get_posts_by_tag, get_posts_by_score, get_recent_posts],
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)




