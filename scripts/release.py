#!/usr/bin/env python3
"""Release automation — version bump, changelog, tag, build, push.

Workflow:
  1. Bump version in pyproject.toml (patch/minor/major)
  2. Insert new changelog section; reset [Unreleased]
  3. Commit + tag v{x.y.z}
  4. Build wheel
  5. Print instructions for GitHub release or PyPI upload

Requires: python >=3.12, twine (for PyPI), gh (for GitHub CLI release)
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
PYPROJECT = ROOT / "pyproject.toml"

BUMP_MAP = {"patch": 2, "minor": 1, "major": 0}


def read_version() -> str:
    data = tomllib.loads(PYPROJECT.read_text())
    return data["project"]["version"]


def bump_version(version: str, mode: str) -> str:
    parts = list(map(int, version.split(".")))
    idx = BUMP_MAP[mode]
    parts[idx] += 1
    for i in range(idx + 1, 3):
        parts[i] = 0
    return ".".join(map(str, parts))


def update_pyproject(old: str, new: str):
    text = PYPROJECT.read_text()
    text = re.sub(
        r'version\s*=\s*["\']' + re.escape(old) + r'["\']', f'version = "{new}"', text
    )
    PYPROJECT.write_text(text)


def update_changelog(old: str, new: str):
    text = CHANGELOG.read_text()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    text = text.replace(
        "## [Unreleased] — Current",
        f"## [{new}] — {today}\\n\\n### Changed\\n- version bump: {old} → {new}\\n\\n---\\n\\n## [Unreleased] — Current",
    )
    CHANGELOG.write_text(text)


def run_cmd(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(result.stdout)
        print(result.stderr)
        sys.exit(result.returncode)
    return result


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in BUMP_MAP:
        print("Usage: python scripts/release.py [patch|minor|major]")
        sys.exit(1)

    mode = sys.argv[1]
    old_version = read_version()
    new_version = bump_version(old_version, mode)

    print(f"Bumping version: {old_version} → {new_version}")

    update_pyproject(old_version, new_version)
    print(f"✓ Updated pyproject.toml")

    update_changelog(old_version, new_version)
    print(f"✓ Updated CHANGELOG.md")

    run_cmd(["git", "add", "pyproject.toml", "CHANGELOG.md"])
    run_cmd(["git", "commit", "-m", f"Release v{new_version}"])
    run_cmd(["git", "tag", f"v{new_version}"])
    run_cmd(["python", "-m", "build", "--wheel", "--outdir", "dist/"])

    wheel = next(ROOT.glob("dist/mosaic-*.whl"))
    print(f"✓ Built {wheel.name}")

    print("\nNext steps:")
    print(f"  git push origin main --tags")
    print(f"  # Or create a GitHub release via:")
    print(
        f"  gh release create v{new_version} {wheel} --notes-format=markdown --notes='See CHANGELOG.md'"
    )
    print(f"  # Or upload to PyPI:")
    print(f"  twine upload {wheel}")


if __name__ == "__main__":
    main()
