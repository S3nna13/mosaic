#!/usr/bin/env python3
"""Pre-push validation — run before pushing to GitHub.

Checks:
  - git status clean
  - smoke test passes
  - syntax of all Python files
  - version in pyproject.toml matches CHANGELOG
  - wheel can be built (dry-run if possible)
"""
from __future__ import annotations

import subprocess
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def git_clean() -> bool:
    code, out, _ = run(["git", "status", "--porcelain"])
    if code != 0:
        print("✗ Failed to check git status")
        return False
    if out.strip():
        print("✗ Working tree not clean — commit or stash changes first")
        print(out)
        return False
    print("✓ Git tree clean")
    return True


def smoke_test() -> bool:
    code, _, err = run([sys.executable, "tests/smoke.py"])
    if code == 0:
        print("✓ Smoke test passed")
        return True
    print("✗ Smoke test failed")
    print(err)
    return False


def syntax_check() -> bool:
    import ast
    ok = True
    for p in (ROOT / "src" / "mosaic").rglob("*.py"):
        try:
            ast.parse(p.read_text())
        except SyntaxError as e:
            print(f"✗ SYNTAX  {p.relative_to(ROOT)}: {e.msg} (line {e.lineno})")
            ok = False
    if ok:
        print("✓ All Python syntax valid")
    return ok


def version_consistency() -> bool:
    import tomllib
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    version = pyproject["project"]["version"]

    changelog = (ROOT / "CHANGELOG.md").read_text()
    # Should have an entry for this version
    if f"[{version}]" not in changelog:
        print(f"✗ CHANGELOG.md missing section for version {version}")
        return False
    print(f"✓ Version {version} documented in CHANGELOG.md")
    return True


def wheel_build_dry() -> bool:
    # Just verify build metadata parses
    import tomllib
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
    if "build-system" not in pyproject:
        print("✗ pyproject.toml missing [build-system] table")
        return False
    print("✓ Build system configured")
    return True


def main() -> int:
    print("MOSAIC PRE-PUSH VALIDATION")
    print("=" * 40)

    checks = [
        git_clean(),
        smoke_test(),
        syntax_check(),
        version_consistency(),
        wheel_build_dry(),
    ]

    print()
    if all(checks):
        print("✓✓✓ All checks passed — ready to push")
        return 0
    print("✗ Some checks failed — fix them before pushing")
    return 1


if __name__ == "__main__":
    sys.exit(main())
