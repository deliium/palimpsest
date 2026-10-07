"""KnowledgeGenealogySpec construction and nested policy validation."""

from __future__ import annotations

import pytest

from simulation.runner_models import (
    KnowledgeGenealogyLineagePolicy,
    KnowledgeGenealogyMutationPolicy,
    KnowledgeGenealogyQueryPolicy,
    KnowledgeGenealogySpec,
    KnowledgeGenealogyUptakeCompose,
    example_knowledge_genealogy_spec,
)


def test_example_knowledge_genealogy_spec_defaults() -> None:
    spec = example_knowledge_genealogy_spec()
    assert spec.knowledge_genealogy_mode == "deterministic"
    assert spec.lineage_policy.max_entries_per_owner == 64
    assert spec.lineage_policy.max_parent_ids == 4
    assert spec.lineage_policy.max_hop_depth == 16
    assert spec.lineage_policy.allow_multi_parent is True
    assert spec.mutation_policy.allow_mutation is True
    assert spec.mutation_policy.allow_combination is True
    assert spec.mutation_policy.mutation_distance_threshold == 0.15
    assert spec.query_policy.max_query_depth == 32
    assert spec.query_policy.independent_root_match == "content_key"
    assert spec.applicability == "all_live_agents"
    assert spec.max_evidence_refs == 8
    assert spec.rng_namespace == "knowledge_genealogy"
    assert "foraging_method" in spec.enabled_kinds


def test_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="knowledge_genealogy_mode_invalid"):
        KnowledgeGenealogySpec(
            enabled_kinds=("foraging_method",),
            knowledge_genealogy_mode="disabled",
        )


def test_max_hop_above_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="knowledge_genealogy_max_hop_invalid"):
        KnowledgeGenealogyLineagePolicy(max_hop_depth=33)


def test_kinds_empty_rejected() -> None:
    with pytest.raises(ValueError, match="knowledge_genealogy_kinds_empty"):
        KnowledgeGenealogySpec(enabled_kinds=())


def test_kind_duplicate_rejected() -> None:
    with pytest.raises(ValueError, match="knowledge_genealogy_kind_duplicate"):
        KnowledgeGenealogySpec(
            enabled_kinds=("foraging_method", "foraging_method")
        )


def test_kind_invalid_rejected() -> None:
    with pytest.raises(ValueError, match="knowledge_genealogy_kind_invalid"):
        KnowledgeGenealogySpec(enabled_kinds=("society_encyclopedia",))


def test_mutation_threshold_rejected() -> None:
    with pytest.raises(
        ValueError, match="knowledge_genealogy_mutation_threshold_invalid"
    ):
        KnowledgeGenealogyMutationPolicy(mutation_distance_threshold=0.0)


def test_query_depth_ceiling_rejected() -> None:
    with pytest.raises(
        ValueError, match="knowledge_genealogy_max_query_depth_invalid"
    ):
        KnowledgeGenealogyQueryPolicy(max_query_depth=64)


def test_canonical_payload_exact_keys() -> None:
    payload = example_knowledge_genealogy_spec().canonical_payload()
    assert set(payload) == {
        "applicability",
        "enabled_kinds",
        "knowledge_genealogy_mode",
        "lineage_policy",
        "max_evidence_refs",
        "mutation_policy",
        "query_policy",
        "rng_namespace",
        "uptake_compose",
    }
    assert set(payload["lineage_policy"]) == {
        "allow_multi_parent",
        "max_entries_per_owner",
        "max_hop_depth",
        "max_parent_ids",
    }
    assert set(payload["mutation_policy"]) == {
        "allow_combination",
        "allow_mutation",
        "max_token_edits",
        "min_token_overlap",
        "mutation_distance_threshold",
        "mutation_requires_evidence",
        "require_combination_distinct_roots",
    }
    assert set(payload["uptake_compose"]) == {
        "developmental",
        "imitation",
        "independent_discovery",
        "reconstruction",
        "teaching",
        "written_record",
    }
    assert set(payload["query_policy"]) == {
        "include_dead_holders",
        "independent_root_match",
        "max_query_depth",
    }


def test_uptake_compose_defaults_false() -> None:
    compose = KnowledgeGenealogyUptakeCompose()
    assert compose.teaching is False
    assert compose.independent_discovery is False
