# Blog Curator Agent — Project Memory & Architecture Notes

## Overview
This project is a Blog Curator Agent built on the Google Agent Development Kit (ADK) and Gemini 2.5 Flash (`gemini-2.5-flash`), with Firestore storage and A2UI surface rendering in `adk web`.

## Key Specifications & Implementation Details

1. **Blog Post Fetcher (`fetch_posts`)**:
   - Source URL: `https://ukidlucas.blogspot.com/feeds/posts/default?max-results=10` (Atom XML).
   - Local directory: `posts/` (e.g. `posts/YYYY-MM-DD-slug.md`).
   - Parsed fields: `title`, `published_date`, `url`, `tags`, plain text `content` (HTML stripped & unescaped).
   - Skips writing files if `posts/YYYY-MM-DD-slug.md` already exists.

2. **Blog Post Assessor (`assess_posts`)**:
   - Iterates through all `.md` files in `posts/`.
   - Hardcoded GCP Project ID: `qwiklabs-gcp-03-001b5a0cda08`.
   - Firestore Client: `firestore.Client(project="qwiklabs-gcp-03-001b5a0cda08")`.
   - Collection: `"posts"`.
   - Document ID: Filename stem (e.g. `2026-08-11-overnight-pizza-sourdough-12-inch`).
   - Assessment metrics stored:
     - `title` (string)
     - `published_date` (string)
     - `url` (string)
     - `tags` (list of strings)
     - `missing_tags` (boolean)
     - `grammar_issues` (list of string descriptions of worst offenses)
     - `content_strength` ("strong", "average", or "weak")
     - `content_strength_reason` (one sentence explanation)
     - `word_count` (integer)
     - `score` (integer rating 1-5)

3. **Query Tools**:
   - `get_posts_by_tag(tag: str)`: Filters Firestore `posts` collection by tag.
   - `get_weakest_posts()`: Returns posts with weak content strength, missing tags, or low scores.
   - `get_recent_posts(limit: int = 10)`: Returns recent posts ordered by `published_date` descending.

4. **A2UI Integration**:
   - `A2uiSchemaManager` version `0.8` with `BasicCatalog` config `"0.8"`.
   - `after_model_callback`: `a2ui_callback` from `app/a2ui_utils.py`.
   - Renders post listings as tables (built with Rows & Columns of Text) and individual post details as Cards.

5. **GitHub & Deployment**:
   - Project repository: `https://github.com/UkiDLucas/buildwithgemini-my-agent`
