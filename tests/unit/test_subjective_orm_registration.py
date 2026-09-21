"""Subjective agent ORM tables register outside AUTHORITATIVE_TABLES."""

from __future__ import annotations


def test_subjective_agent_orm_registers_outside_authoritative_set() -> None:
    import persistence.subjective_orm as subjective_orm
    from infrastructure.orm import metadata
    from persistence.orm import AUTHORITATIVE_TABLES
    from persistence.subjective_orm import SUBJECTIVE_AGENT_TABLES

    assert set(SUBJECTIVE_AGENT_TABLES).isdisjoint(AUTHORITATIVE_TABLES)
    assert set(SUBJECTIVE_AGENT_TABLES) <= set(metadata.tables)
    assert hasattr(subjective_orm, "SemanticBeliefOrm")
    assert hasattr(subjective_orm, "DirectedRelationshipOrm")
    assert hasattr(subjective_orm, "SubjectiveOperationOrm")
    assert "semantic_beliefs" in SUBJECTIVE_AGENT_TABLES
    assert "directed_relationships" in SUBJECTIVE_AGENT_TABLES
    assert "subjective_operations" in SUBJECTIVE_AGENT_TABLES
