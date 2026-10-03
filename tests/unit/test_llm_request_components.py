"""Assert every production LLMRequestContext site supplies a closed component."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COGNITION = ROOT / "src" / "agents" / "cognition"

EXPECTED: dict[str, str] = {
    "reconstruction.py": "reconstructive_memory",
    "reflection.py": "reflection",
    "consolidation.py": "offline_consolidation",
    "world_model_selection.py": "world_model",
    "prospective_selection.py": "prospective",
    "counterfactual_selection.py": "counterfactual",
    "theory_of_mind_selection.py": "theory_of_mind",
    "competence_selection.py": "competence",
    "teaching_selection.py": "teaching",
    "production_selection.py": "production",
}


def _component_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name != "LLMRequestContext":
            continue
        for keyword in node.keywords:
            if keyword.arg != "component":
                continue
            if isinstance(keyword.value, ast.Constant) and isinstance(
                keyword.value.value, str
            ):
                found.append(keyword.value.value)
    return found


@pytest.mark.parametrize("filename,expected", sorted(EXPECTED.items()))
def test_production_llm_request_context_has_closed_component(
    filename: str, expected: str
) -> None:
    path = COGNITION / filename
    assert path.is_file()
    components = _component_literals(path)
    assert components, f"{filename} must construct LLMRequestContext with component"
    assert all(item == expected for item in components)
    assert all(item.strip() for item in components)
