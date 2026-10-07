"""Observation / Perspective must not project technique catalogs or genealogy DAGs."""

from __future__ import annotations

import logging

from agents.cognition.contracts import Perspective
from agents.cognition.practical_knowledge import empty_practical_knowledge_ledger
from agents.models import AgentId
from world.observations import Observation

_LOG = logging.getLogger("tests.practical_knowledge_observation_isolation")

_FORBIDDEN_OBSERVATION_FIELDS = frozenset(
    {
        "practical_knowledge",
        "knowledge_genealogy",
        "technique_catalog",
        "technique_pack",
        "knowledge_pack",
        "global_technique_registry",
        "society_encyclopedia",
        "true_method_catalog",
        "genealogy_dag",
        "knowledge_ledger",
    }
)

_FORBIDDEN_PERSPECTIVE_CATALOG_FIELDS = frozenset(
    {
        "technique_catalog",
        "technique_pack",
        "knowledge_pack",
        "global_technique_registry",
        "society_encyclopedia",
        "true_method_catalog",
        "genealogy_dag",
        "knowledge_genealogy",
    }
)


def test_observation_has_no_technique_catalog_or_genealogy_fields() -> None:
    _LOG.debug("case_id=observation_no_catalog")
    fields = set(Observation.__dataclass_fields__)
    assert fields.isdisjoint(_FORBIDDEN_OBSERVATION_FIELDS)


def test_perspective_has_no_technique_catalog_or_genealogy_dag_fields() -> None:
    _LOG.debug("case_id=perspective_no_catalog")
    fields = set(Perspective.__dataclass_fields__)
    assert fields.isdisjoint(_FORBIDDEN_PERSPECTIVE_CATALOG_FIELDS)


def test_perspective_may_carry_owner_practical_knowledge_ledger() -> None:
    """Ledger carry is owner-scoped subjective state — not a society catalog."""
    _LOG.debug("case_id=perspective_plumb_practical_knowledge")
    assert "practical_knowledge" in Perspective.__dataclass_fields__
    owner = AgentId("bob")
    ledger = empty_practical_knowledge_ledger(owner)
    assert ledger.owner_id == owner
    assert ledger.entries == ()
    assert "genealogy_dag" not in Perspective.__dataclass_fields__
