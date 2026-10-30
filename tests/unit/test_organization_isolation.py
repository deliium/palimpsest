"""Organization authority isolation: owner-only inputs, no world or peer reads."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from agents.cognition import (
    OrganizationConceptError,
    OrganizationConceptLedger,
    apply_organization_concept_update,
    default_organization_concept_policy,
    empty_organization_concept_ledger,
    organization_communication,
)
from agents.models import AgentId
from world.identifiers import EntityId, WorldId, WorldRevision
from world.observations import Observation

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
ORGANIZATION_MODULES = (
    SRC / "agents" / "cognition" / "organization_concepts.py",
    SRC / "agents" / "cognition" / "organization_communication.py",
)

FORBIDDEN_SYMBOLS = (
    "WorldState",
    "WorldEngine",
    "ActionSubmission",
    "AgentCommand",
    "MetricDocument",
    "PhysicalRules",
    "AgentBody",
)


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            roots.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
    return roots


@pytest.mark.parametrize("path", ORGANIZATION_MODULES)
def test_organization_modules_hold_no_world_authority(path: Path) -> None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    class_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    assert class_names & set(FORBIDDEN_SYMBOLS) == set()
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not any(
        name.startswith(("world._", "world.events"))
        or name.startswith(("simulation", "analysis", "experiments"))
        for name in imported
    )


@pytest.mark.parametrize("path", ORGANIZATION_MODULES)
def test_organization_modules_do_not_import_outer_layers(path: Path) -> None:
    roots = _imported_roots(path)
    assert (
        roots
        & {
            "analysis",
            "experiments",
            "persistence",
            "api",
            "infrastructure",
            "observer",
        }
        == set()
    )
    assert "simulation" not in roots


def test_update_signature_accepts_only_owner_local_inputs() -> None:
    signature = inspect.signature(apply_organization_concept_update)
    parameters = set(signature.parameters)
    assert parameters == {
        "owner_id",
        "tick",
        "observation",
        "prior",
        "institution_concepts",
        "offices",
        "group_formation",
        "collective_decisions",
        "structured_commitments",
        "social_conventions",
        "policy",
    }
    for name in signature.parameters:
        assert "peer" not in name
        assert "world" not in name
        assert "engine" not in name


def test_no_command_or_event_is_created() -> None:
    for path in ORGANIZATION_MODULES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert not node.name.endswith(("Command", "Event")), node.name
            if isinstance(node, ast.ImportFrom) and node.module == "world.actions":
                imported = {alias.name for alias in node.names}
                assert imported <= {"Talk", "Tell"}
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                assert node.module != "world.events"


def test_world_authority_objects_are_rejected() -> None:
    class WorldState:
        pass

    WorldState.__module__ = "world._state"
    with pytest.raises(Exception) as excinfo:
        apply_organization_concept_update(
            owner_id="ada",
            tick=3,
            observation=WorldState(),
            prior=None,
            institution_concepts=None,
            offices=None,
            group_formation=None,
            collective_decisions=None,
            structured_commitments=None,
            social_conventions=None,
            policy=default_organization_concept_policy(),
        )
    assert "organization_invalid_status" in str(excinfo.value)


def test_peer_ledgers_cannot_be_supplied() -> None:
    with pytest.raises(Exception) as excinfo:
        apply_organization_concept_update(
            owner_id="ada",
            tick=3,
            observation=Observation(
                world_id=WorldId("world-isolation"),
                observer_id=EntityId("body-ada"),
                revision=WorldRevision(1),
                tick=3,
            ),
            prior=empty_organization_concept_ledger(AgentId("ben")),
            institution_concepts=None,
            offices=None,
            group_formation=None,
            collective_decisions=None,
            structured_commitments=None,
            social_conventions=None,
            policy=default_organization_concept_policy(),
        )
    assert getattr(excinfo.value, "code", None) == "organization_foreign_ledger"


def test_communication_module_holds_no_delivery_authority() -> None:
    source = Path(organization_communication.__file__).read_text(encoding="utf-8")
    assert "WorldState" not in source
    assert "ActionSubmission" not in source
    assert "recipient_id=" in source  # preserves the selected recipient only


def test_ledger_owner_must_match_the_update_owner() -> None:
    ledger = OrganizationConceptLedger(owner_id=AgentId("ada"))
    assert ledger.owner_id == AgentId("ada")
    with pytest.raises(OrganizationConceptError):
        apply_organization_concept_update(
            owner_id="ben",
            tick=1,
            observation=None,
            prior=ledger,
            institution_concepts=None,
            offices=None,
            group_formation=None,
            collective_decisions=None,
            structured_commitments=None,
            social_conventions=None,
            policy=default_organization_concept_policy(),
        )
