"""Closed V4-20 market institution contract: enums, policy, ids, schedules."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import pytest

from agents.cognition import market_institutions as module
from agents.cognition.market_institutions import (
    MARKET_INSTITUTION_LOCKED_POLICY,
    MARKET_INSTITUTIONS_POLICY_VERSION,
    MARKET_LABEL_PATTERN,
    MarketCadence,
    MarketExpectation,
    MarketInstitutionError,
    MarketInstitutionPolicy,
    MarketRecordKind,
    MarketRoleBasis,
    MarketRoleKind,
    MarketScheduleBelief,
    MarketScheduleSource,
    MarketVenueStatus,
    default_market_institution_policy,
    market_cluster_id,
    market_schedule_is_active,
    market_venue_analysis_id,
    market_venue_belief_id,
)

pytestmark = pytest.mark.unit

SRC = Path(__file__).resolve().parents[2] / "src"
MODULE = SRC / "agents" / "cognition" / "market_institutions.py"


def test_policy_version_and_locked_values_are_exact() -> None:
    assert MARKET_INSTITUTIONS_POLICY_VERSION == "market-institutions.v1"
    assert MARKET_LABEL_PATTERN == r"^[a-z0-9][a-z0-9_-]*$"
    policy = default_market_institution_policy()
    assert type(policy) is MarketInstitutionPolicy
    assert dict(MARKET_INSTITUTION_LOCKED_POLICY) == {
        "max_venues": 8,
        "max_observations_per_venue": 64,
        "max_schedules_per_venue": 4,
        "max_roles_per_venue": 8,
        "max_records_per_venue": 8,
        "max_counterparties_per_observation": 16,
        "max_notices": 8,
        "max_evidence_per_observation": 8,
        "decline_after_ticks": 64,
        "dormant_after_ticks": 128,
        "expected_min_observations": 2,
        "strong_min_observations": 2,
        "strong_min_confidence_milli": 500,
        "persistent_min_ticks": 3,
        "persistent_min_windows": 2,
    }


@pytest.mark.parametrize(
    ("enum_type", "expected"),
    (
        (MarketExpectation, ("none", "weak", "expected", "strong")),
        (
            MarketCadence,
            (
                "single_occurrence",
                "recurring_interval",
                "periodic_window",
                "unknown",
            ),
        ),
        (
            MarketVenueStatus,
            ("emerging", "expected", "persistent", "declining", "dormant"),
        ),
        (MarketRoleKind, ("broker", "host", "organizer", "unknown")),
        (
            MarketRoleBasis,
            ("observed_participation", "claimed", "office", "organization"),
        ),
        (
            MarketRecordKind,
            (
                "exchange_record",
                "attendance_record",
                "agreement_record",
                "unknown",
            ),
        ),
        (MarketScheduleSource, ("observed", "communicated", "self_authored")),
    ),
)
def test_enums_have_exactly_the_documented_members(
    enum_type: type[Enum], expected: tuple[str, ...]
) -> None:
    assert tuple(member.value for member in enum_type) == expected


def test_belief_ids_are_stable_and_owner_local() -> None:
    from tests.unit.market_institutions_helpers import OWNER, PEER, A

    first = market_venue_belief_id(owner_id=OWNER, location_id=A, creation_tick=3)
    again = market_venue_belief_id(owner_id=OWNER, location_id=A, creation_tick=3)
    other_owner = market_venue_belief_id(owner_id=PEER, location_id=A, creation_tick=3)
    other_tick = market_venue_belief_id(owner_id=OWNER, location_id=A, creation_tick=4)
    assert first == again
    assert first.startswith("mktb-")
    assert len(first) == 21
    assert other_owner != first
    assert other_tick != first


def test_analysis_ids_are_content_addressed() -> None:
    venue_id = market_venue_analysis_id("loc-a")
    assert venue_id.startswith("mkt-ven-")
    assert venue_id == market_venue_analysis_id("loc-a")
    assert venue_id != market_venue_analysis_id("loc-b")
    cluster = market_cluster_id((venue_id,))
    assert cluster.startswith("mktc-")
    assert cluster == market_cluster_id((venue_id,))


def test_recurring_schedule_active_rule() -> None:
    belief = MarketScheduleBelief(
        cadence=MarketCadence.RECURRING_INTERVAL,
        interval_ticks=5,
        phase_tick=3,
        window_index=None,
        confidence_milli=500,
        source=MarketScheduleSource.SELF_AUTHORED,
        first_tick=0,
        last_tick=0,
    )
    assert market_schedule_is_active(belief, 3)
    assert market_schedule_is_active(belief, 8)
    assert not market_schedule_is_active(belief, 4)


def test_periodic_window_active_rule_and_boundaries() -> None:
    belief = MarketScheduleBelief(
        cadence=MarketCadence.PERIODIC_WINDOW,
        interval_ticks=None,
        phase_tick=None,
        window_index=2,
        confidence_milli=500,
        source=MarketScheduleSource.SELF_AUTHORED,
        first_tick=0,
        last_tick=0,
    )
    assert not market_schedule_is_active(belief, 63)
    assert market_schedule_is_active(belief, 64)
    assert market_schedule_is_active(belief, 95)
    assert not market_schedule_is_active(belief, 96)


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "cadence": MarketCadence.RECURRING_INTERVAL,
            "interval_ticks": 0,
            "phase_tick": 0,
        },
        {
            "cadence": MarketCadence.RECURRING_INTERVAL,
            "interval_ticks": 5,
            "phase_tick": 512,
        },
        {
            "cadence": MarketCadence.RECURRING_INTERVAL,
            "interval_ticks": 5,
            "phase_tick": 0,
            "window_index": 1,
        },
        {
            "cadence": MarketCadence.PERIODIC_WINDOW,
            "interval_ticks": 5,
            "phase_tick": 0,
        },
        {
            "cadence": MarketCadence.SINGLE_OCCURRENCE,
            "interval_ticks": 5,
            "phase_tick": 0,
        },
    ),
)
def test_schedule_invariants_fail_closed(kwargs: dict[str, Any]) -> None:
    values = dict(kwargs)
    window_index = values.pop("window_index", None)
    with pytest.raises(MarketInstitutionError):
        MarketScheduleBelief(
            window_index=window_index,
            confidence_milli=500,
            source=MarketScheduleSource.SELF_AUTHORED,
            first_tick=0,
            last_tick=0,
            **values,
        )


def test_forbidden_field_names_are_rejected_on_a_bad_contract() -> None:
    @dataclass(frozen=True, slots=True)
    class BadContract:
        price: int = 1

    with pytest.raises(MarketInstitutionError):
        module._reject_forbidden_fields(BadContract)


def test_module_declares_no_command_or_event_type() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    assert "AgentCommand" not in classes
    assert "WorldEvent" not in classes
    assert "Move" not in classes
