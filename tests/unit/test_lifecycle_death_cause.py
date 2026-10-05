"""Unit tests for DeathCause.LIFESPAN and SystemEffectFamily.LIFECYCLE pins."""

from __future__ import annotations

import logging

import pytest

from world.effects import DeathCause, SystemCause, SystemEffectFamily
from world.identifiers import EntityId, RequestId
from world.models import non_lethal_physical_rules

_LOG = logging.getLogger("tests.lifecycle_death_cause")


def test_death_cause_includes_lifespan() -> None:
    _LOG.debug("case_id=death_cause_lifespan")
    assert list(DeathCause) == [
        DeathCause.ATTACK,
        DeathCause.COMBINED_NEEDS,
        DeathCause.EXPOSURE,
        DeathCause.LIFESPAN,
    ]
    assert {cause.value for cause in DeathCause} == {
        "attack",
        "combined_needs",
        "exposure",
        "lifespan",
    }


def test_system_effect_family_includes_lifecycle() -> None:
    _LOG.debug("case_id=system_effect_family_lifecycle")
    names = [family.value for family in SystemEffectFamily]
    assert "lifecycle" in names
    assert SystemEffectFamily.LIFECYCLE is SystemEffectFamily("lifecycle")
    cause = SystemCause(
        RequestId("sys-lifecycle-1"),
        SystemEffectFamily.LIFECYCLE,
        EntityId("body-1"),
        0,
    )
    assert cause.effect_family is SystemEffectFamily.LIFECYCLE


def test_system_cause_rejects_non_family() -> None:
    _LOG.debug("case_id=system_cause_reject_family")
    with pytest.raises(TypeError, match="effect_family"):
        SystemCause(
            RequestId("sys-bad"),
            "lifecycle",  # type: ignore[arg-type]
            EntityId("body-1"),
            0,
        )


def test_non_lethal_rules_still_construct_with_lifespan_cause() -> None:
    _LOG.debug("case_id=non_lethal_covers_lifespan")
    rules = non_lethal_physical_rules()
    assert rules.attack_damage_min == 0
    assert rules.hunger_damage == 0.0
