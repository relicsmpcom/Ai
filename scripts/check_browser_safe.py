#!/usr/bin/env python3
"""Fail if the engine grows a dependency the browser build cannot satisfy.

The static, serverless build works for exactly one reason: everything under
``wia/`` except the API layer imports only the Python standard library. That
property is easy to break by accident and invisible until the page dies in
somebody's browser, so it is checked in CI.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "wia"

#: The API layer is allowed third-party imports; it is excluded from the
#: browser bundle. ``llm`` may import ``anthropic``, but only lazily, inside a
#: function — which the module-level check below already enforces.
EXEMPT = {PACKAGE / "api"}


def module_level_imports(path: Path) -> set[str]:
    """Only top-level imports matter — a lazy import inside a function is fine."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def main() -> int:
    stdlib = set(sys.stdlib_module_names)
    problems: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if any(exempt in path.parents for exempt in EXEMPT):
            continue
        for module in sorted(module_level_imports(path)):
            if module not in stdlib and module != "wia":
                problems.append(f"{path.relative_to(ROOT)}: imports {module!r} at module level")

    if problems:
        print("The engine must stay standard-library-only for the browser build:\n")
        for line in problems:
            print("  -", line)
        print("\nMove the import inside the function that needs it, or keep the "
              "feature in wia/api/.")
        return 1
    print("engine is standard-library-only — the browser build will work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
