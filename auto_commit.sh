#!/usr/bin/env bash
# auto_commit.sh - Automatically commits and pushes workspace changes to GitHub
set -e
export PATH="$HOME/.local/bin:$PATH"

PROJECT_DIR="/config/Desktop/BuildWithGemini/my-agent"
if [ -d "$PROJECT_DIR" ]; then
    cd "$PROJECT_DIR"
fi

# Ensure git user info is set
if ! git config user.email >/dev/null 2>&1; then
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        login="$(gh api user -q .login 2>/dev/null || echo "")"
        if [ -n "$login" ]; then
            git config user.name "$login"
            git config user.email "${login}@users.noreply.github.com"
        fi
    fi
fi

git add -A

if ! git diff --cached --quiet; then
    TIMESTAMP="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    git commit -m "Auto-commit: update workspace at ${TIMESTAMP}"
    gh auth setup-git >/dev/null 2>&1 || true
    git push origin main
    echo "Successfully committed and pushed changes at ${TIMESTAMP}."
else
    echo "No uncommitted changes detected."
fi
