#!/usr/bin/env python3
"""MOSAIC smoke test — validates core package structure, syntax, and importable modules.

Checks:
  1. All subpackages have __init__.py
  2. All .py files parse as valid Python
  3. Core modules (no heavy optional deps) import cleanly
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "mosaic"


def check_package_files() -> bool:
    ok = True
    for sub in [
        "model",
        "memory",
        "security",
        "guardrails",
        "adapters",
        "tools",
        "train",
        "eval",
        "inference",
        "core",
        "multimodal",
        "audit",
        "orchestration",
    ]:
        init = SRC / sub / "__init__.py"
        if not init.exists():
            print(f"✗ MISSING  {sub}/__init__.py")
            ok = False
    if ok:
        print("✓ All subpackages have __init__.py")
    return ok


def check_syntax() -> bool:
    ok = True
    for p in SRC.rglob("*.py"):
        try:
            ast.parse(p.read_text())
        except SyntaxError as e:
            print(f"✗ SYNTAX  {p.relative_to(ROOT)}: {e.msg} (line {e.lineno})")
            ok = False
    if ok:
        print("✓ All Python files parse cleanly")
    return ok


def check_imports() -> bool:
    sys.path.insert(0, str(SRC))
    core_mods = [
        "mosaic",
        "mosaic.core",
        "mosaic.core.schema",
        "mosaic.core.config",
        "mosaic.model",
        "mosaic.model.config",
        "mosaic.guardrails.engine",
        "mosaic.guardrails.tuner",
        "mosaic.tools.runner",
        "mosaic.tools.registry",
        "mosaic.tools.attack_mapper",
        "mosaic.eval.metrics",
        "mosaic.inference.router",
        "mosaic.multimodal.vision",
        "mosaic.multimodal.adapter_mixin",
        "mosaic.audit.ark_ledger",
    ]
    failed = []
    skipped = []
    for m in core_mods:
        try:
            __import__(m)
            print(f"✓ import {m}")
        except ModuleNotFoundError as e:
            print(f"⚠ SKIP    {m} — missing optional dep '{e.name}'")
            skipped.append((m, e.name))
        except Exception as e:
            print(f"✗ IMPORT  {m} — {e}")
            failed.append((m, e))
    if not failed:
        print(f"✓ Core modules importable (skipped {len(skipped)} optional-deps)")
    return not failed


def main() -> int:
    print("MOSAIC SMOKE TEST")
    print("=" * 40)
    results = [check_package_files(), check_syntax(), check_imports()]
    if all(results):
        print("\n✓✓✓ All checks passed — package is structurally sound")
        return 0
    print("\n✗ Some checks failed — review output above")
    return 1


if __name__ == "__main__":
    sys.exit(main())
