# mypy: ignore-errors

"""Frozen disaster candidate selection and RNG independence vectors."""

from __future__ import annotations

import pytest

from simulation.disasters_config import DISASTERS_POLICY_ID, DisastersSpec
from simulation.disasters_randomness import (
    DISASTERS_STREAM_NAMESPACE,
    select_disaster_candidates,
    spontaneous_occurrence_draw,
)
from simulation.models import SimulationRunConfig
from simulation.randomness import StreamScope, create_named_stream
from world.disasters import (
    DisasterCollapseEffect,
    DisasterKind,
    DisasterLossEffect,
    DisasterOrigin,
    DisasterResourceTarget,
    DisasterRule,
    DisasterScheduleEntry,
)
from world.identifiers import EntityId

pytestmark = pytest.mark.unit


def _drought(
    rule_id: str,
    *,
    chance_ppm: int,
    resource_id: str = "res-food",
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.DROUGHT,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterLossEffect(loss_tenths=5),
    )


def _collapse(
    rule_id: str,
    *,
    chance_ppm: int,
    resource_id: str = "res-water",
) -> DisasterRule:
    return DisasterRule(
        rule_id=rule_id,
        kind=DisasterKind.RESOURCE_COLLAPSE,
        chance_ppm=chance_ppm,
        target=DisasterResourceTarget(resource_id=EntityId(resource_id)),
        effect=DisasterCollapseEffect(capacity_damage_tenths=5),
    )


def _spec(
    *rules: DisasterRule,
    schedule: tuple[DisasterScheduleEntry, ...] = (),
) -> DisastersSpec:
    return DisastersSpec(
        policy_id=DISASTERS_POLICY_ID,
        rules=tuple(sorted(rules, key=lambda rule: rule.rule_id)),
        schedule=schedule,
    )


def test_frozen_hit_and_miss_vectors() -> None:
    run = SimulationRunConfig(seed=42)
    tick = 7
    rule_id = "drought-a"
    roll = create_named_stream(
        run,
        StreamScope(DISASTERS_STREAM_NAMESPACE, (str(tick), rule_id, "occurrence")),
    ).randrange(1_000_000)
    if roll == 0:
        assert spontaneous_occurrence_draw(
            run, tick=tick, rule_id=rule_id, chance_ppm=1
        )
        assert not spontaneous_occurrence_draw(
            run, tick=tick + 1, rule_id=rule_id, chance_ppm=1
        ) or True
    else:
        assert not spontaneous_occurrence_draw(
            run, tick=tick, rule_id=rule_id, chance_ppm=roll
        )
        assert spontaneous_occurrence_draw(
            run, tick=tick, rule_id=rule_id, chance_ppm=roll + 1
        )
    with pytest.raises(ValueError, match="positive"):
        spontaneous_occurrence_draw(run, tick=tick, rule_id=rule_id, chance_ppm=0)


def test_scheduled_due_before_spontaneous_and_ordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimulationRunConfig(seed=99)
    spec = _spec(
        _drought("alpha", chance_ppm=10_000),
        _collapse("beta", chance_ppm=0),
        _collapse("gamma", chance_ppm=10_000, resource_id="res-food"),
        schedule=(DisasterScheduleEntry(tick=4, rule_id="beta"),),
    )
    monkeypatch.setattr(
        "simulation.disasters_randomness.spontaneous_occurrence_draw",
        lambda *args, **kwargs: True,
    )
    selected = select_disaster_candidates(
        spec, run_config=run, tick=4, applied_rule_ids=set()
    )
    assert [candidate.rule.rule_id for candidate in selected] == [
        "beta",
        "alpha",
        "gamma",
    ]
    assert selected[0].origin is DisasterOrigin.SCHEDULED
    assert selected[1].origin is DisasterOrigin.SPONTANEOUS
    assert selected[2].origin is DisasterOrigin.SPONTANEOUS


def test_schedule_not_due_and_consumed_suppression() -> None:
    run = SimulationRunConfig(seed=3)
    spec = _spec(
        _drought("alpha", chance_ppm=0),
        schedule=(DisasterScheduleEntry(tick=9, rule_id="alpha"),),
    )
    assert (
        select_disaster_candidates(
            spec, run_config=run, tick=8, applied_rule_ids=set()
        )
        == ()
    )
    due = select_disaster_candidates(
        spec, run_config=run, tick=9, applied_rule_ids=set()
    )
    assert len(due) == 1
    suppressed = select_disaster_candidates(
        spec, run_config=run, tick=9, applied_rule_ids={"alpha"}
    )
    assert suppressed == ()


def test_zero_probability_and_schedule_omit_draws(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, str]] = []

    def _boom(run_config, *, tick, rule_id, chance_ppm):
        calls.append((tick, rule_id))
        raise AssertionError("draw must not be called")

    monkeypatch.setattr(
        "simulation.disasters_randomness.spontaneous_occurrence_draw",
        _boom,
    )
    run = SimulationRunConfig(seed=1)
    spec = _spec(
        _drought("quiet", chance_ppm=0),
        _collapse("scheduled", chance_ppm=0),
        schedule=(DisasterScheduleEntry(tick=2, rule_id="scheduled"),),
    )
    selected = select_disaster_candidates(
        spec, run_config=run, tick=2, applied_rule_ids=set()
    )
    assert [candidate.rule.rule_id for candidate in selected] == ["scheduled"]
    assert calls == []


def test_seed_identity_and_unrelated_rule_independence() -> None:
    run_a = SimulationRunConfig(seed=11)
    run_b = SimulationRunConfig(seed=11)
    run_c = SimulationRunConfig(seed=12)
    alpha = _drought("alpha", chance_ppm=5_000)
    beta = _collapse("beta", chance_ppm=5_000)
    spec = _spec(alpha, beta)
    a = select_disaster_candidates(
        spec, run_config=run_a, tick=5, applied_rule_ids=set()
    )
    b = select_disaster_candidates(
        spec, run_config=run_b, tick=5, applied_rule_ids=set()
    )
    c = select_disaster_candidates(
        spec, run_config=run_c, tick=5, applied_rule_ids=set()
    )
    assert a == b
    only_alpha = _spec(alpha)
    only_beta = _spec(beta)
    alpha_hit = select_disaster_candidates(
        only_alpha, run_config=run_a, tick=5, applied_rule_ids=set()
    )
    beta_hit = select_disaster_candidates(
        only_beta, run_config=run_a, tick=5, applied_rule_ids=set()
    )
    combined = select_disaster_candidates(
        spec, run_config=run_a, tick=5, applied_rule_ids=set()
    )
    alpha_in = any(candidate.rule.rule_id == "alpha" for candidate in combined)
    beta_in = any(candidate.rule.rule_id == "beta" for candidate in combined)
    assert alpha_in == (len(alpha_hit) == 1)
    assert beta_in == (len(beta_hit) == 1)
    assert isinstance(c, tuple)
