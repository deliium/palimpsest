"""KnowledgeRepositoriesSpec construction and nested policy validation."""

from __future__ import annotations

import pytest

from simulation.runner_models import (
    KnowledgeRepositoriesSpec,
    KnowledgeRepositoryAccessPolicy,
    KnowledgeRepositoryCapacityPolicy,
    KnowledgeRepositoryIndexPolicy,
    KnowledgeRepositoryMaintenancePolicy,
    example_knowledge_repositories_spec,
)


def test_example_knowledge_repositories_spec_defaults() -> None:
    spec = example_knowledge_repositories_spec()
    assert spec.knowledge_repositories_mode == "deterministic"
    assert spec.access_policy.default_access_mode == "open"
    assert spec.access_policy.deposit_requires_colocation is True
    assert spec.capacity_policy.max_repositories == 8
    assert spec.capacity_policy.max_members_per_repository == 32
    assert spec.maintenance_policy.neglect_ticks == 24
    assert spec.index_policy.index_optional is True
    assert spec.perception_mode == "container_and_meta"
    assert spec.rng_namespace == "knowledge_repositories"


def test_mode_disabled_rejected() -> None:
    with pytest.raises(ValueError, match="knowledge_repositories_mode_invalid"):
        KnowledgeRepositoriesSpec(knowledge_repositories_mode="disabled")


def test_unknown_access_mode_rejected() -> None:
    with pytest.raises(
        ValueError, match="knowledge_repositories_access_mode_invalid"
    ):
        KnowledgeRepositoryAccessPolicy(default_access_mode="librarian")


def test_capacity_must_be_positive() -> None:
    with pytest.raises(
        ValueError, match="knowledge_repositories_capacity_invalid"
    ):
        KnowledgeRepositoryCapacityPolicy(max_repositories=0)


def test_neglect_ticks_must_be_positive() -> None:
    with pytest.raises(
        ValueError, match="knowledge_repositories_neglect_ticks_invalid"
    ):
        KnowledgeRepositoryMaintenancePolicy(neglect_ticks=0)


def test_index_op_must_be_positive() -> None:
    with pytest.raises(
        ValueError, match="knowledge_repositories_index_op_invalid"
    ):
        KnowledgeRepositoryIndexPolicy(max_entries_per_index_op=0)


def test_unknown_perception_mode_rejected() -> None:
    with pytest.raises(
        ValueError, match="knowledge_repositories_perception_mode_invalid"
    ):
        KnowledgeRepositoriesSpec(perception_mode="library_chrome")


def test_canonical_payload_exact_keys() -> None:
    payload = example_knowledge_repositories_spec().canonical_payload()
    assert set(payload) == {
        "access_policy",
        "capacity_policy",
        "index_policy",
        "knowledge_repositories_mode",
        "maintenance_policy",
        "perception_mode",
        "rng_namespace",
    }
    assert set(payload["access_policy"]) == {
        "default_access_mode",
        "deposit_requires_colocation",
        "founder_list_survives_death",
        "retrieve_requires_colocation",
    }
    assert set(payload["capacity_policy"]) == {
        "max_index_entries",
        "max_members_per_repository",
        "max_repositories",
    }
    assert set(payload["maintenance_policy"]) == {
        "allow_destruction",
        "inaccessible_blocks_access",
        "neglect_corrupts_index",
        "neglect_ticks",
    }
    assert set(payload["index_policy"]) == {
        "allow_corrupt_entries",
        "index_optional",
        "max_entries_per_index_op",
    }


def test_founder_list_access_example() -> None:
    spec = example_knowledge_repositories_spec(
        default_access_mode="founder_list", neglect_ticks=3
    )
    assert spec.access_policy.default_access_mode == "founder_list"
    assert spec.maintenance_policy.neglect_ticks == 3
