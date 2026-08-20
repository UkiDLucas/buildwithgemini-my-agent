# Current State

- **Project Name**: Blog Curator Agent (`my-agent`)
- **Repository URL**: https://github.com/UkiDLucas/buildwithgemini-my-agent
- **Model**: `gemini-2.5-flash`
- **GCP Project ID**: `qwiklabs-gcp-03-001b5a0cda08`
- **GCP Region**: `us-central1`
- **Firestore Database**: `(default)` in `us-central1`, collection `"posts"`
- **Tools**:
  - `fetch_posts()`: HTTP GET `https://ukidlucas.blogspot.com/feeds/posts/default?max-results=10`, parses Atom XML, writes `posts/YYYY-MM-DD-slug.md` (skips existing).
  - `assess_posts()`: Reads `posts/*.md`, computes word count, missing tags flag, grammar issues, content strength, and score, writes documents to Firestore collection `"posts"`.
  - `get_posts_by_tag(tag)`: Queries Firestore `posts` collection by tag (`array_contains` filter).
  - `get_weakest_posts()`: Queries Firestore `posts` collection for weak content, low score (<=3), or missing tags.
  - `get_recent_posts(limit=10)`: Queries Firestore `posts` collection ordered by `published_date` descending.
- **Data Schema (`posts` Firestore Collection)**:
  - `id` (string): post filename stem (e.g., `2026-08-11-overnight-pizza-sourdough-12-inch`)
  - `title` (string): post title
  - `published_date` (string): `YYYY-MM-DD`
  - `url` (string): post URL
  - `tags` (list[string]): topic tags/labels
  - `missing_tags` (boolean): `True` if `not tags`
  - `grammar_issues` (list[string]): list of formatting/grammar offenses
  - `content_strength` (string): `"strong"`, `"average"`, or `"weak"`
  - `content_strength_reason` (string): one-sentence reason
  - `word_count` (int): total body words
  - `score` (int): rating 1 to 5
  - `snippet` (string): first 200 characters of post body
- **Dependencies**:
  - `google-adk[gcp,otel-gcp]>=2.5.0,<3.0.0`
  - `google-cloud-firestore>=2.28.1`
  - `a2ui-agent-sdk>=0.2.4` (Imported as `a2ui`)
  - `google-genai`
- **Gotchas & Critical Constraints**:
  - **A2UI Schema Version**: MUST be version `0.8`. `a2ui_callback` in `a2ui_utils.py` keys off v0.8 messages (`beginRendering`, `surfaceUpdate`). v0.9 will not render.
  - **Playground Token Streaming**: Token Streaming MUST be turned OFF in `adk web` / Dev UI (gear icon). With streaming on, `adk web` displays raw JSON and does not render A2UI surfaces.
  - **Project ID Hardcoding**: Project ID MUST be hardcoded as a string (`"qwiklabs-gcp-03-001b5a0cda08"`) when initializing `firestore.Client(project="...")`. Do NOT use `google.auth.default()` or `GOOGLE_CLOUD_PROJECT` environment variables as they fail to resolve the proper lab project context in local venv execution.
  - **Firestore Database Initialization**: The default Firestore database must exist in `us-central1` (created via `gcloud firestore databases create --location=us-central1`).
  - **Python Execution**: Use `uv run agents-cli` or `uv run python` so the project `.venv` is used rather than system Python.

### How to Run From a Fresh Clone

1. Clone repository:
   ```bash
   git clone https://github.com/UkiDLucas/buildwithgemini-my-agent.git
   cd buildwithgemini-my-agent
   ```
2. Sync dependencies:
   ```bash
   agents-cli install   # or uv sync
   ```
3. Run CLI queries:
   ```bash
   uv run agents-cli run "fetch new posts and assess them"
   uv run agents-cli run "list my recent posts"
   ```
4. Run Playground (Dev UI):
   ```bash
   agents-cli playground --port 8080 --host 0.0.0.0
   ```
   Open `http://127.0.0.1:8080/dev-ui/?app=app` in Chrome, turn **Token Streaming OFF**, and query the agent.

---

# Log

### 2026-08-20 20:43 - Agent Setup & Model Configuration
- **What was built/changed**: Created `my-agent` ADK project using `agents-cli create my-agent --adk -y`.
- **Why**: Initial lab scaffolding.
- **Failures & Fixes**:
  - *Error*: `gemini-3.6-flash` returned `404 NOT_FOUND` in Vertex AI `us-central1`.
  - *Fix*: Changed `MODEL = "gemini-2.5-flash"` in `app/agent.py` and updated `GOOGLE_CLOUD_LOCATION=us-central1` in `.env`.

### 2026-08-20 21:10 - GitHub Publication & Device Auth
- **What was built/changed**: Authenticated to GitHub via `gh auth login --web` device flow (`A5B3-A021`), created public repository `buildwithgemini-my-agent` on user account `UkiDLucas`, and committed project code.
- **Why**: Save project permanently and obtain swag/gallery submission form link.

### 2026-08-20 21:34 - Dependencies & Firestore DB Setup
- **What was built/changed**: Installed `google-cloud-firestore` and `a2ui-agent-sdk` via `uv add google-cloud-firestore "a2ui-agent-sdk"`. Created default Firestore database in `us-central1`.
- **Why**: Required for blog post assessments storage and A2UI schema manager.
- **Failures & Fixes**:
  - *Error*: `google.api_core.exceptions.NotFound: 404 The database (default) does not exist for project qwiklabs-gcp-03-001b5a0cda08`.
  - *Fix*: Ran `gcloud firestore databases create --location=us-central1` to initialize the Firestore native database instance.
  - *Error*: `uv add "a2ui-agent-sdk>=0.4.0,<0.5.0"` failed due to version conflict with `a2a-sdk>=1.0`.
  - *Fix*: Ran `uv add a2ui-agent-sdk` which resolved cleanly to `a2ui-agent-sdk==0.2.4`.

### 2026-08-20 21:35 - Blog Curator Agent Tools & A2UI Integration
- **What was built/changed**:
  - Implemented `fetch_posts` (scrapes Atom XML feed and writes `posts/*.md`).
  - Implemented `assess_posts` (evaluates grammar, content strength, word count, missing tags, score, and writes to Firestore `"posts"` collection).
  - Implemented Firestore query tools: `get_posts_by_tag`, `get_weakest_posts`, `get_recent_posts`.
  - Copied `a2ui_utils.py` to `app/a2ui_utils.py` and configured `root_agent` with `after_model_callback=a2ui_callback` and `A2uiSchemaManager` (v0.8).
- **Why**: Full requirement set for Blog Curator Agent with structured UI display in Playground.

### 2026-08-20 21:36 - Auto-Commit Automation
- **What was built/changed**: Created `auto_commit.sh` script and set up a 15-minute recurring background schedule (`schedule` tool with cron `*/15 * * * *`).
- **Why**: Keep GitHub repository automatically synchronized with all local changes.

### 2026-08-20 21:40 - Permanent MEMORY.md Tracking System
- **What was built/changed**: Formalized `MEMORY.md` into `# Current State` and `# Log` sections with timestamp rules and gotcha records.
- **Why**: Maintain a permanent, complete record across agent sessions.
