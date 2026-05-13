#!/bin/bash
set -euo pipefail

# MOSAIC push helper — runs release pipeline + GitHub Actions
# Usage: ./scripts/push.sh [patch|minor|major]

if [ -z "${1:-}" ]; then
    echo "Usage: $0 [patch|minor|major]"
    echo "  patch — x.x.N  → x.x.(N+1)"
  echo "  minor — x.N.x  → x.(N+1).0"
  echo "  major — N.x.x  → (N+1).0.0"
  exit 1
fi

BUMP=$1

# Ensure we're on main with no pending changes
if [ "$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then
  echo "Error: Must be on 'main' branch"
  exit 1
fi
if [ -n "$(git status --porcelain)" ]; then
  echo "Error: Working tree not clean — commit or stash first"
  exit 1
fi

# Run release automation (commits + tags)
python3 scripts/release.py "$BUMP"

# Push to GitHub (triggers CI + subsequent workflows)
git push origin main
git push origin --tags

echo "✅ Push complete — GitHub Actions will: lint → test → build wheel → (optionally) publish"
echo "   To create a GitHub Release automatically, ensure the 'Publish' workflow has 'on: push: tags: 'v*'' enabled."
