"""Architecture gates: objective kinship stays outside social / SelfModel / beliefs."""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from agents.models import AgentId
from simulation.bootstrap import AgentRegistration, WorldBootstrap
from simulation.engine import WorldEngine
from simulation.models import RunId, SimulationRunConfig
from tests.simulation_helpers import alive_body, make_location, make_weather
from world.identifiers import WorldId, WorldRevision
from world.models import non_lethal_physical_rules

pytestmark = pytest.mark.architecture

_LOG = logging.getLogger("tests.architecture.v3_kinship_isolation")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

_SUBJECTIVE_PATHS = (
    _SRC / "social" / "relationships.py",
    _SRC / "agents" / "cognition" / "identity.py",
    _SRC / "simulation" / "subjective_projections.py",
)

_FORBIDDEN_FROM_SUBJECTIVE = frozenset(
    {
        "world.kinship",
    }
)

_FORBIDDEN_SOCIAL_FROM_KINSHIP = frozenset(
    {
        "social",
        "social.relationships",
        "social.models",
        "social.service",
        "agents.cognition.identity",
    }
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    return imported


def test_subjective_writers_do_not_import_kinship() -> None:
    _LOG.debug("case_id=subjective_no_kinship_imports")
    for path in _SUBJECTIVE_PATHS:
        assert path.is_file(), path
        imported = _imported_modules(path)
        hits = imported & _FORBIDDEN_FROM_SUBJECTIVE
        assert hits == set(), f"{path.relative_to(_REPO_ROOT)}: {sorted(hits)}"


def test_kinship_module_does_not_import_social_or_identity() -> None:
    _LOG.debug("case_id=kinship_no_social_imports")
    path = _SRC / "world" / "kinship.py"
    imported = _imported_modules(path)
    hits = imported & _FORBIDDEN_SOCIAL_FROM_KINSHIP
    assert hits == set(), sorted(hits)


def test_world_package_kinship_has_no_social_imports() -> None:
    _LOG.debug("case_id=world_kinship_surface_no_social")
    for path in (_SRC / "world").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "kinship" not in path.name and "kinship" not in text.lower():
            continue
        imported = _imported_modules(path)
        social_hits = {
            name
            for name in imported
            if name == "social" or name.startswith("social.")
        }
        assert social_hits == set(), (
            f"{path.relative_to(_REPO_ROOT)} imports {sorted(social_hits)}"
        )


def test_establish_kinship_does_not_revise_relationships() -> None:
    _LOG.debug("case_id=establish_no_relationship_side_effects")
    body_a = alive_body("body-a")
    body_b = alive_body("body-b")
    bootstrap = WorldBootstrap(
        world_id=WorldId("world-kinship-isolation"),
        revision=WorldRevision(0),
        locations=(make_location(),),
        bodies=(body_a, body_b),
        weather=(make_weather(),),
        registrations=(
            AgentRegistration(AgentId("agent-a"), body_a.entity_id),
            AgentRegistration(AgentId("agent-b"), body_b.entity_id),
        ),
    )
    # Empty bootstrap edges; establish at runtime.
    from simulation.runner_models import KinshipSpec

    engine = WorldEngine(
        config=SimulationRunConfig(
            seed=19, physical_rules=non_lethal_physical_rules()
        ),
        bootstrap=bootstrap,
        run_id=RunId("run-kinship-isolation"),
        kinship_spec=KinshipSpec(),
    )
    details = engine.establish_kinship_edge(
        parent_agent_id=AgentId("agent-a"),
        child_agent_id=AgentId("agent-b"),
    )
    assert details.kind == "kinship_edge_recorded"
    # No social relationship store on engine; establish must not create one.
    assert not hasattr(engine, "_relationships")
    assert not hasattr(engine, "_relationship_profiles")


def test_engine_documents_related_not_valence() -> None:
    _LOG.debug("case_id=engine_related_not_valence_comment")
    text = (_SRC / "simulation" / "engine.py").read_text(encoding="utf-8")
    assert "never implies trust" in text.lower() or "Relatedness never implies" in text
    kinship_text = (_SRC / "world" / "kinship.py").read_text(encoding="utf-8")
    for token in ("trust", "affection", "loyalty"):
        # Documentation may mention forbidden valence; ensure no API assigns it.
        assert f"{token}=" not in kinship_text


def test_kinship_spec_has_no_social_valence_fields() -> None:
    _LOG.debug("case_id=kinship_no_valence_fields")
    from simulation.runner_models import KinshipSpec

    fields = {item.name for item in KinshipSpec.__dataclass_fields__.values()}
    assert fields == {
        "admit_link_policy",
        "bootstrap_edges",
        "max_parents_per_child",
        "max_query_depth",
        "perception_mode",
    }
