"""Enforces the Clean Architecture dependency rule (SRS 7.1, AR-01 to AR-06).

Reads every file under app/ with `ast` (without running it) and checks each import:

    domain          -> standard library + app.domain only
    application     -> standard library + app.domain + app.application only
    infrastructure  -> anything except app.interfaces, app.container, app.main
    interfaces      -> anything except app.infrastructure (adapters come from the container)
    app/*.py        -> anything (main.py, config.py, container.py are the composition root)
"""

import ast
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
STDLIB = set(sys.stdlib_module_names)


def layer_of(rel_path: str) -> str:
    """'app/domain/x.py' -> 'domain'; 'app/main.py' -> 'root'."""
    parts = Path(rel_path).parts
    return parts[1] if len(parts) > 2 else "root"


def imported_modules(rel_path: str, source: str) -> list[tuple[int, str]]:
    """(line number, absolute module name) for every import, with relative imports resolved."""
    package = list(Path(rel_path).parts[:-1])  # the folder the file lives in
    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import: from . / .. import x
                base = package[: len(package) - (node.level - 1)]
                name = ".".join(base + ([node.module] if node.module else []))
            else:
                name = node.module or ""
            found.append((node.lineno, name))
    return found


def is_allowed(layer: str, module: str) -> bool:
    top = module.split(".")[0]
    is_stdlib = top in STDLIB
    in_app = top == "app"

    def under(*prefixes: str) -> bool:
        return any(module == p or module.startswith(p + ".") for p in prefixes)

    if layer == "domain":
        return is_stdlib or under("app.domain")
    if layer == "application":
        return is_stdlib or under("app.domain", "app.application")
    if layer == "infrastructure":
        return not (in_app and under("app.interfaces", "app.container", "app.main"))
    if layer == "interfaces":
        return not (in_app and under("app.infrastructure"))
    return True  # root: composition root may import anything


def find_violations(rel_path: str, source: str) -> list[str]:
    layer = layer_of(rel_path)
    return [
        f"{rel_path}:{line} ({layer}) must not import {module}"
        for line, module in imported_modules(rel_path, source)
        if not is_allowed(layer, module)
    ]


def app_files() -> list[Path]:
    return sorted(APP_DIR.rglob("*.py"))


# ---------------------------------------------------------------- the real check


def test_app_follows_the_dependency_rule() -> None:
    violations: list[str] = []
    for path in app_files():
        rel = path.relative_to(APP_DIR.parent).as_posix()
        violations += find_violations(rel, path.read_text(encoding="utf-8"))
    assert not violations, "Clean Architecture violations:\n" + "\n".join(violations)


def test_the_check_actually_sees_files() -> None:
    layers = {layer_of(p.relative_to(APP_DIR.parent).as_posix()) for p in app_files()}
    assert {"domain", "application"} <= layers


# ---------------------------------------------------------------- the checker catches mistakes


@pytest.mark.parametrize(
    ("rel_path", "source"),
    [
        ("app/domain/x.py", "import fastapi"),
        ("app/domain/x.py", "from app.application.ports.llm import LLM"),
        ("app/domain/x.py", "import numpy as np"),
        ("app/application/x.py", "from app.infrastructure.llm.gemini_llm import GeminiLLM"),
        ("app/application/x.py", "from pydantic import BaseModel"),
        ("app/application/x.py", "import langgraph"),
        ("app/application/use_cases/x.py", "from ...infrastructure.db import models"),
        ("app/interfaces/api/x.py", "from app.infrastructure.sms.textbee_sms import TextbeeSms"),
        ("app/infrastructure/x.py", "from app.interfaces.api import schemas"),
    ],
)
def test_checker_catches_forbidden_imports(rel_path: str, source: str) -> None:
    assert find_violations(rel_path, source), f"should be forbidden: {source} in {rel_path}"


@pytest.mark.parametrize(
    ("rel_path", "source"),
    [
        ("app/domain/x.py", "import re\nfrom dataclasses import dataclass\nfrom app.domain.errors import X"),
        ("app/application/x.py", "from app.domain.entities import Answer\nfrom typing import Protocol"),
        ("app/application/use_cases/x.py", "from ..ports.llm import LLM"),
        ("app/infrastructure/x.py", "import chromadb\nfrom app.application.ports.retrieval import Passage"),
        ("app/interfaces/api/x.py", "from fastapi import APIRouter\nfrom app.container import Container"),
        ("app/container.py", "from app.infrastructure.sms.console_sms import ConsoleSms"),
    ],
)
def test_checker_allows_legal_imports(rel_path: str, source: str) -> None:
    assert find_violations(rel_path, source) == []
