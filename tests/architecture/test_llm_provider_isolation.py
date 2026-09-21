"""LLM provider package isolation and public-contract guarantees."""

from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path
from typing import get_args, get_origin, get_type_hints

import pytest

import llm
import llm.models
from llm.contracts import LLMProvider
from llm.factory import DisabledLLMProvider, create_llm_provider
from llm.models import LLMResult, LLMResultMetadata, StructuredOutput
from llm.providers import OpenAICompatibleProvider
from llm.providers.openai_compatible_codec import (
    decode_chat_completions_response,
    encode_chat_completions_body,
)
from tests.architecture.boundary_checker import (
    ALLOWED_IMPORTS,
    LLM_FORBIDDEN_BOUNDED,
    PRIVATE_WORLD_MODULES,
    PROVIDER_SDKS,
    check_tree,
    format_violations,
)

pytestmark = pytest.mark.architecture

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
LLM_ROOT = SRC_ROOT / "llm"

FORBIDDEN_SIGNATURE_TYPES = frozenset(
    {
        "World",
        "WorldState",
        "WorldEngine",
        "ActionSubmission",
        "ActionRequest",
        "WorldTransition",
        "WorldGateway",
        "ValidatedWorldOperation",
        "ObservationBatch",
    }
)
FORBIDDEN_RESULT_FIELDS = frozenset(
    {
        "raw",
        "raw_text",
        "text",
        "content",
        "body",
        "payload",
        "response",
        "headers",
        "messages",
        "schema",
        "provider_payload",
        "provider_response",
    }
)
FORBIDDEN_CONVERSION_NAMES = frozenset(
    {
        "to_agent_command",
        "as_agent_command",
        "to_command",
        "as_command",
        "to_action_submission",
        "to_action_request",
        "as_action_submission",
        "as_action_request",
        "to_submission",
        "admit",
    }
)


def test_source_tree_keeps_llm_isolated() -> None:
    violations = check_tree(SRC_ROOT)
    assert violations == [], format_violations(violations)
    assert ALLOWED_IMPORTS["llm"] == frozenset()
    assert LLM_FORBIDDEN_BOUNDED.isdisjoint(ALLOWED_IMPORTS["llm"])


def test_llm_modules_do_not_import_forbidden_or_private_targets() -> None:
    hits: list[str] = []
    for path in LLM_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    hits.extend(_forbidden_import_hits(path, node.lineno, alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    continue
                hits.extend(_forbidden_import_hits(path, node.lineno, module))
                for alias in node.names:
                    imported = f"{module}.{alias.name}" if module else alias.name
                    hits.extend(_forbidden_import_hits(path, node.lineno, imported))
    assert hits == []


def _forbidden_import_hits(path: Path, line: int, imported: str) -> list[str]:
    if not imported:
        return []
    root = imported.split(".", 1)[0]
    if root in LLM_FORBIDDEN_BOUNDED or root in PROVIDER_SDKS or root == "structlog":
        return [f"{path}:{line}:{imported}"]
    for private in PRIVATE_WORLD_MODULES:
        if imported == private or imported.startswith(f"{private}."):
            return [f"{path}:{line}:{imported}"]
    return []


def test_llm_modules_avoid_nondeterministic_clocks_and_randomness() -> None:
    violations = [
        item
        for item in check_tree(SRC_ROOT)
        if item.source_module.startswith("llm") and item.rule == "nondeterministic-call"
    ]
    assert violations == [], format_violations(violations)


def test_public_provider_signatures_reject_world_authority_types() -> None:
    targets = (
        LLMProvider.generate,
        DisabledLLMProvider.generate,
        OpenAICompatibleProvider.generate,
        OpenAICompatibleProvider.__init__,
        create_llm_provider,
        encode_chat_completions_body,
        decode_chat_completions_response,
    )
    hits: list[str] = []
    for target in targets:
        hints = get_type_hints(target)
        for name, annotation in hints.items():
            hits.extend(_annotation_hits(f"{target.__qualname__}.{name}", annotation))
    assert hits == []


def _annotation_hits(path: str, annotation: object) -> list[str]:
    found: list[str] = []
    stack: list[object] = [annotation]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        ident = id(current)
        if ident in seen:
            continue
        seen.add(ident)
        if isinstance(current, type):
            if current.__name__ in FORBIDDEN_SIGNATURE_TYPES:
                found.append(f"{path}:{current.__name__}")
            continue
        if isinstance(current, str):
            if current in FORBIDDEN_SIGNATURE_TYPES:
                found.append(f"{path}:{current}")
            continue
        origin = get_origin(current)
        if origin is not None:
            stack.extend(get_args(current))
            continue
        args = get_args(current)
        if args:
            stack.extend(args)
    return found


def test_llm_ast_signatures_omit_world_authority_names() -> None:
    hits: list[str] = []
    for path in LLM_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") and node.name != "__init__":
                continue
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                if arg.annotation is None:
                    continue
                for name in _annotation_names(arg.annotation):
                    if name in FORBIDDEN_SIGNATURE_TYPES:
                        hits.append(f"{path}:{node.lineno}:{node.name}:{name}")
            if node.returns is not None:
                for name in _annotation_names(node.returns):
                    if name in FORBIDDEN_SIGNATURE_TYPES:
                        hits.append(f"{path}:{node.lineno}:{node.name}:return:{name}")
    assert hits == []


def _annotation_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
        elif isinstance(child, ast.Constant) and isinstance(child.value, str):
            names.add(child.value)
    return names


def test_public_results_omit_raw_provider_payloads_and_conversions() -> None:
    result_field_names = {item.name for item in fields(LLMResult)}
    metadata_field_names = {item.name for item in fields(LLMResultMetadata)}
    assert result_field_names.isdisjoint(FORBIDDEN_RESULT_FIELDS)
    assert metadata_field_names.isdisjoint(FORBIDDEN_RESULT_FIELDS)
    assert result_field_names == {"output", "metadata"}

    public_names = set(llm.__all__)
    assert public_names.isdisjoint(FORBIDDEN_CONVERSION_NAMES)
    for name in FORBIDDEN_CONVERSION_NAMES:
        assert not hasattr(LLMResult, name)
        assert not hasattr(StructuredOutput, name)
        assert name not in dir(OpenAICompatibleProvider)
        assert name not in dir(DisabledLLMProvider)

    assert "to_agent_command" not in inspect.getsource(llm.models)
    assert "to_agent_command" not in inspect.getsource(OpenAICompatibleProvider)


def test_llm_logging_is_stdlib_metadata_only() -> None:
    violations = [
        item
        for item in check_tree(SRC_ROOT)
        if item.source_module.startswith("llm") and item.rule == "unsafe-logging"
    ]
    assert violations == [], format_violations(violations)

    for path in LLM_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "import infrastructure" not in source
        assert "from infrastructure" not in source
        assert "structlog" not in source
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"debug", "info", "warning", "error", "critical"}:
                continue
            for keyword in node.keywords:
                if keyword.arg != "exc_info":
                    continue
                assert (
                    isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is False
                )


def test_future_cognition_translation_remains_separate() -> None:
    """Provider adapters stop at StructuredOutput; admission stays elsewhere."""
    assert "CognitionStrategy" not in llm.__all__
    assert "AgentCommand" not in llm.__all__
    assert "ActionSubmission" not in llm.__all__
    assert "admit_agent_command" not in llm.__all__
    assert "WorldEngine" not in llm.__all__
    assert "require_agent_command" not in dir(llm)
