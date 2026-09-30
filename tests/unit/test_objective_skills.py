"""Objective skill contracts stay identity at level zero and quantize once."""

from __future__ import annotations

import logging
import math

import pytest

from agents.cognition.competence import CompetenceDomain
from world._skills import (
    ObjectiveSkillLedger as Ledger,
)
from world._skills import (
    SkillDomain,
    SkillGrowthChannel,
    adjusted_flee_fatigue,
    adjusted_help_gain,
    adjusted_move_fatigue,
    adjusted_search_probability,
    default_objective_skill_policy,
    growth_delta,
)
from world.identifiers import EntityId
from world.values import clamp_unit_interval


def _quantize(value: float) -> float:
    return round(value / 1e-6) * 1e-6


def test_domain_tokens_match_competence_domains() -> None:
    assert [domain.value for domain in SkillDomain] == [
        domain.value for domain in CompetenceDomain
    ]
    assert len(SkillDomain) == 8


def test_level_zero_matches_current_formulas() -> None:
    policy = default_objective_skill_policy()
    visibility = 0.5
    base = 0.25
    weight = 0.75
    search = adjusted_search_probability(
        search_base_probability=base,
        search_visibility_weight=weight,
        visibility=visibility,
        foraging_level=0.0,
        resource_detection_level=0.0,
        policy=policy,
    )
    assert search == clamp_unit_interval(base + weight * visibility)
    assert adjusted_move_fatigue(5.0, 0.0, policy) == 5.0
    assert adjusted_flee_fatigue(10.0, 0.0, policy) == 10.0
    assert adjusted_help_gain(10.0, 0.0, policy) == 10.0


def test_success_and_failure_bundles_quantize_once() -> None:
    policy = default_objective_skill_policy()
    entity = EntityId("body-1")
    ledger = Ledger.bootstrap((entity,))
    success = (
        growth_delta(SkillGrowthChannel.PRACTICE, policy)
        + growth_delta(SkillGrowthChannel.SUCCESS, policy)
    )
    failure = (
        growth_delta(SkillGrowthChannel.PRACTICE, policy)
        + growth_delta(SkillGrowthChannel.FAILURE, policy)
    )
    grown = ledger.apply_summed_deltas(
        {entity: {SkillDomain.FORAGING: success}}
    )
    missed = ledger.apply_summed_deltas(
        {entity: {SkillDomain.FORAGING: failure}}
    )
    assert grown.level(entity, SkillDomain.FORAGING) == _quantize(0.02 + 0.05)
    assert grown.level(entity, SkillDomain.FORAGING) == _quantize(0.07)
    assert missed.level(entity, SkillDomain.FORAGING) == _quantize(0.03)
    assert _quantize(0.02 + 0.05) == _quantize(0.07)


def test_policy_construction_logs_version_and_rejects_gain(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger="world._skills")
    policy = default_objective_skill_policy()
    assert policy.version == "objective-skill-v1"
    debug = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.DEBUG
    ]
    assert any("policy_version=objective-skill-v1" in line for line in debug)
    assert any("domain_count=8" in line for line in debug)
    caplog.clear()
    with pytest.raises(ValueError, match="out_of_range"):
        type(policy)(probability_gain=1.5)
    assert any(
        "reason_code=out_of_range" in record.getMessage()
        and record.levelno == logging.ERROR
        for record in caplog.records
    )


def test_non_finite_rate_logs_reason_code(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="world._skills")
    with pytest.raises(ValueError, match="not_finite"):
        default_objective_skill_policy().__class__(practice_rate=math.nan)
    assert "field=practice_rate" in caplog.text
    assert "reason_code=not_finite" in caplog.text


def test_unknown_domain_is_rejected(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="world._skills")
    entity = EntityId("body-1")
    ledger = Ledger.bootstrap((entity,))
    with pytest.raises(ValueError, match="unknown_domain"):
        ledger.level(entity, "foraging")  # type: ignore[arg-type]
    assert "reason_code=unknown_domain" in caplog.text
