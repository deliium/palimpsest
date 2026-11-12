"""Canonical credit relationship snapshot records and caps."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from simulation.credit_relationships_models import (
    CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES,
    CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS,
    CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
    CreditRelationshipsSnapshot,
    empty_credit_relationships_snapshot,
)
from tests.unit.credit_relationships_snapshot_helpers import (
    distribution,
    relationship,
    snapshot,
)

pytestmark = pytest.mark.unit


def test_valid_snapshot_round_trips_its_fields() -> None:
    value = snapshot()
    assert value.run_id == "run-credit-1"
    assert value.schema_version == CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION
    assert value.relationships[0].relationship_id == "credo-0123456789abcdef"
    assert value.distributions[0].bin_shares_milli == (250, 0, 500, 0, 250)
    assert value.summary.coverage == "complete"


def test_empty_snapshot_is_missing() -> None:
    value = empty_credit_relationships_snapshot("run-credit-1")
    assert value.coverage if hasattr(value, "coverage") else value.summary.coverage
    assert value.summary.coverage == "missing"
    assert value.relationships == ()
    assert value.claims == ()
    assert CREDIT_RELATIONSHIPS_ARTIFACT_MAX_BYTES == 8_388_608


def test_relationship_cap_is_enforced() -> None:
    rows = tuple(
        relationship(relationship_id=f"credo-{index:016x}")
        for index in range(CREDIT_RELATIONSHIPS_MAX_RELATIONSHIPS + 1)
    )
    with pytest.raises(ValueError):
        CreditRelationshipsSnapshot(
            run_id="run-credit-1",
            schema_version=CREDIT_RELATIONSHIPS_SNAPSHOT_VERSION,
            policy_version="credit-relationships.v1",
            summary=snapshot().summary,
            relationships=rows,
            claims=(),
            performances=(),
            distributions=(),
            counterparties=(),
            alignments=(),
        )


def test_duplicate_row_ids_are_rejected() -> None:
    value = snapshot()
    with pytest.raises(ValueError):
        CreditRelationshipsSnapshot(
            run_id=value.run_id,
            schema_version=value.schema_version,
            policy_version=value.policy_version,
            summary=value.summary,
            relationships=(value.relationships[0], value.relationships[0]),
            claims=(),
            performances=(),
            distributions=(),
            counterparties=(),
            alignments=(),
        )


def test_available_distribution_bins_must_sum_to_one_thousand() -> None:
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(distribution(), bin_shares_milli=(100, 0, 100, 0, 100))


def test_available_distribution_quantiles_must_be_ordered() -> None:
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(distribution(), median_ratio_milli=1)


def test_wall_clock_fields_do_not_exist() -> None:
    fields = set(snapshot().__dataclass_fields__)
    assert "created_at" not in fields
    assert "published_at" not in fields
    assert "wall_clock" not in fields
