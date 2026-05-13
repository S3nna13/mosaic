# MOSAIC — Git Push & Release Guide

This guide assumes you have a GitHub repository for MOSAIC and want to push code, build Docker images, and publish releases.

---

## 1. Initial Setup (One-Time)

### 1.1 Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `mosaic`
3. Choose public or private
4. **Don't** initialize with README, .gitignore, or license (you already have these)
5. Click "Create repository"

### 1.2 Connect Local Repo to GitHub

```bash
cd /Users/christienantonio/Desktop/mosaic

# If you already have a remote called 'origin' pointing elsewhere, remove it first:
git remote remove origin  # (optional)

# Add your GitHub repo (replace <username>)
git remote add origin git@github.com:<username>/mosaic.git

# Verify
git remote -v
```

### 1.3 Enable GitHub Container Registry (GHCR)

No setup needed — it's automatically available. Just ensure you have `docker` CLI installed and logged in when pushing images (GitHub Actions logs in automatically via `GITHUB_TOKEN`).

---

## 2. First Commit & Push

If you haven't committed anything yet:

```bash
git add .
git commit -m "Initial commit — MOSAIC unified framework"
git branch -M main
git push -u origin main
```

This triggers the CI workflow immediately.

---

## 3. Making a Release (Standard Workflow)

### Option A — Automated (Recommended)

Use the helper script:

```bash
# Make sure you're on main and everything is committed
git status

# Bump version and push
./scripts/push.sh patch   # for bugfixes  (0.1.0 → 0.1.1)
./scripts/push.sh minor   # for features  (0.1.0 → 0.2.0)
./scripts/push.sh major   # for breaking  (0.1.0 → 1.0.0)
```

The script:
1. Bumps version in `pyproject.toml`
2. Updates `CHANGELOG.md` with today's date
3. Commits with message `Release v{x.y.z}`
4. Tags commit as `v{x.y.z}`
5. Builds wheel into `dist/`
6. Pushes `main` + tags to GitHub
7. GitHub Actions runs:
   - **CI** — lint, type-check, tests
   - **Docker** — builds & pushes `ghcr.io/<you>/mosaic:v{x.y.z}` + `:latest`
   - **Publish** — wheel to PyPI (if tag matches `v*` and `publish.yml` enabled)

### Option B — Manual

```bash
# 1. Bump version (edit pyproject.toml) and document changes in CHANGELOG.md
vim pyproject.toml
vim CHANGELOG.md

# 2. Commit + tag
git add pyproject.toml CHANGELOG.md
git commit -m "Release v0.3.1"
git tag v0.3.1

# 3. Push
git push origin main
git push origin --tags
```

---

## 4. Verify Deployment

After pushing:

### 4.1 Check CI status

Visit: `https://github.com/<you>/mosaic/actions`

All jobs should be green:
- lint-test (Python 3.12)
- docker (Build & Push) — only on tags

### 4.2 Confirm Docker image

```bash
docker pull ghcr.io/<you>/mosaic:latest
docker run --rm -it ghcr.io/<you>/mosaic:latest --help
```

### 4.3 Download wheel

```bash
# From the GitHub Releases page:
# https://github.com/<you>/mosaic/releases/tag/v0.3.1
# Download mosaic-0.3.1-py3-none-any.whl

pip install mosaic-0.3.1-py3-none-any.whl
```

---

## 5. Post-Release Chores

- [ ] Announce on relevant channels (Discord, Twitter, mailing list)
- [ ] Update any dependent projects that pin to a branch
- [ ] Delete old Docker images from GHCR if needed to save storage
- [ ] Create a new `[Unreleased]` section in `CHANGELOG.md` for upcoming work

---

## 6. Troubleshooting

| Problem | Command/Action |
|---------|---------------|
| CI fails on formatting | `black src/mosaic tests && git commit -am "fix format" && git push` |
| CI fails on type-check | Fix missing type hints or add `# type: ignore` sparingly |
| Docker build fails | Check Dockerfile syntax; test locally: `docker build .` |
| GitHub Actions not triggering | Ensure tag pattern is `v*` (e.g., `v0.3.1`, not `0.3.1`) |
| `publish.yml` skipped | Confirm `on: push: tags:` pattern matches; manual trigger via `workflow_dispatch` |

---

## 7. Reference — File Map

```
mosaic/
├── .github/
│   └── workflows/
│       ├── ci.yml          — lint + test on every push
│       ├── docker.yml      — build+push Docker to GHCR on tags
│       └── publish.yml     — upload wheel to PyPI on tags
├── scripts/
│   ├── release.py          — version bump + changelog + tag + wheel build
│   ├── push.sh             — one-command push helper
│   └── pre_push.py         — local validation before pushing
├── pyproject.toml          — single-source version, dependencies, build config
├── CHANGELOG.md            — human-readable release notes
├── Dockerfile              — multi-stage container build
├── docker-compose.yml      — local dev orchestration
├── k8s/                    — Kubernetes manifests
├── Makefile                — developer workflow shortcuts
└── PUSH.md                 — this document
```

---

## Done

Your project is now fully configured for:
- Automated CI on every commit
- Docker image publishing to GHCR on every release tag
- PyPI wheel publishing on every release tag (optional)
- One-command version bump + push workflow

**All that remains:** run `./scripts/push.sh [patch|minor|major]` and watch the pipelines turn green.
