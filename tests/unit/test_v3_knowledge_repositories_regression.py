"""Knowledge-repositories regression pins: SEMANTIC 53 + metrics 62."""

from __future__ import annotations

import pytest

from analysis.specifications import METRIC_FAMILY_COUNT, MetricFamilyId
from observer.version import SEMANTIC_EVENT_TYPES
from world.actions import (
    DepositRecord,
    EstablishRepository,
    IndexRepository,
    MaintainRepository,
    RetrieveRecord,
)

pytestmark = pytest.mark.unit


def test_semantic_event_count_is_53() -> None:
    assert len(SEMANTIC_EVENT_TYPES) == 53
    assert "REPOSITORY_ESTABLISHED" in SEMANTIC_EVENT_TYPES
    assert "REPOSITORY_NEGLECTED" in SEMANTIC_EVENT_TYPES


def test_metric_family_count_is_62() -> None:
    assert METRIC_FAMILY_COUNT == 62
    assert MetricFamilyId.KNOWLEDGE_REPOSITORY_SURVIVAL.value == (
        "knowledge_repository_survival"
    )
    assert MetricFamilyId.KNOWLEDGE_REPOSITORY_ACCESS.value == (
        "knowledge_repository_access"
    )
    assert MetricFamilyId.KNOWLEDGE_REPOSITORY_ORGANIZATION.value == (
        "knowledge_repository_organization"
    )


def test_repository_command_types_present() -> None:
    # Full 29→34 command count pin lands in Task 21; types must exist now.
    assert EstablishRepository is not None
    assert DepositRecord is not None
    assert RetrieveRecord is not None
    assert MaintainRepository is not None
    assert IndexRepository is not None
