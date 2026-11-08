# mypy: ignore-errors
"""Cause-weighted owner bias on adjacent Move futures; never a command path."""

from __future__ import annotations

import dataclasses
import math

import pytest

from agents.cognition.configuration import (
    CognitionMigrationDisplacementMode,
    build_cognitive_loop,
    production_cognition_config,
)
from agents.cognition.deliberation import CommandPlanner, MultiCriteriaIntentionSelector
from agents.cognition.migration_displacement import (
    CauseEvidenceStatus,
    MigrationCauseKind,
    MigrationCauseSource,
    MigrationIntentStatus,
    RouteBeliefBasis,
    RouteBeliefStatus,
    default_migration_displacement_policy,
    empty_migration_displacement_ledger,
    migration_displacement_action_biases,
)
from agents.cognition.models import ActionDirection, PossibleFutures
from agents.models import AgentId
from tests.unit.migration_displacement_helpers import (
    A,
    B,
    C,
    D,
    cause,
    intent,
    ledger,
    observation,
    route,
)
from tests.unit.test_regional_migration_cognition import (
    _current_observation,
    _future,
    _loop_input,
    _motivation,
)
from world.actions import Move, Wait
from world.identifiers import EntityId

pytestmark = pytest.mark.unit

POLICY = default_migration_displacement_policy()
OWNER_ID = AgentId("agent-1")
L1, L2, L4 = EntityId("loc-1"), EntityId("loc-2"), EntityId("loc-4")


def _belief(
    locations=(A, B, C),
    *,
    cause_row=None,
    route_row=None,
    status: MigrationIntentStatus = MigrationIntentStatus.PLANNED,
    tick: int = 1,
):
    cause_row = cause(tick=tick) if cause_row is None else cause_row
    route_row = route(locations, tick=tick) if route_row is None else route_row
    return ledger(
        intents=(intent(locations, causes=(cause_row,), status=status, tick=tick),),
        routes=(route_row,) if route_row is not False else (),
        causes=(cause_row,),
    )


def _biases(owner_ledger, *, at=A, known=(B,), base=None, journey=None):
    return migration_displacement_action_biases(
        owner_ledger,
        observation=observation(location=at, journey=journey),
        known_destinations=known,
        base_biases=base,
        policy=POLICY,
    )


def _futures():
    return (
        _future("move-2", ActionDirection.MOVE, "loc-2"),
        _future("move-4", ActionDirection.MOVE, "loc-4"),
    )


async def _select(owner_bias=None, futures=None):
    futures = _futures() if futures is None else futures
    selector = MultiCriteriaIntentionSelector()
    loop_input = _loop_input(OWNER_ID, _current_observation(hunger=0.0), ())
    return await selector.select(
        loop_input,
        _motivation(futures),
        PossibleFutures(OWNER_ID, futures, confidence=1.0),
        migration_displacement_bias=owner_bias,
    )


def _owner_ledger(*, causes_first: bool = True):
    first = cause(tick=1)
    second = cause(
        MigrationCauseKind.CONFLICT,
        MigrationCauseSource.CONFLICT_BELIEF,
        anchor="conflict:c-1",
        tick=2,
    )
    ordered = (first, second) if causes_first else (second, first)
    return ledger(
        intents=(
            intent(
                (L1, L4),
                causes=ordered,
                status=MigrationIntentStatus.PLANNED,
            ),
        ),
        routes=(route((L1, L4)),),
        causes=ordered,
    )


@pytest.mark.asyncio
async def test_disabled_mode_preserves_regional_candidate_order() -> None:
    baseline = await _select(None)
    assert baseline.selected_future_id == "move-2"
    # An absent, empty, or no-match bias leaves the selection byte-identical.
    assert await _select({}) == baseline
    assert await _select({"loc-9": 0.25}) == baseline
    # Disabled cognition allocates no ledger and no bias.
    loop = build_cognitive_loop()
    assert (
        loop._migration_displacement_mode is CognitionMigrationDisplacementMode.DISABLED
    )
    loop_input = _loop_input(OWNER_ID, _current_observation(), ())
    prepared = loop._prepare_migration_displacement(
        loop_input,
        organization_concepts=None,
        institution_concepts=None,
        formal_rules=None,
        disputes=None,
        evidence=None,
        diplomacy=None,
        organized_conflict=None,
        borders=None,
    )
    assert prepared is None
    assert loop._prepared_migration_displacement is None
    assert loop._prepared_migration_displacement_biases == {}
    # The candidate order of the planner output is unchanged by the empty ledger.
    empty = empty_migration_displacement_ledger(OWNER_ID)
    assert (
        migration_displacement_action_biases(
            empty,
            observation=_current_observation(),
            known_destinations=(L2, L4),
            policy=POLICY,
        )
        == {}
    )


@pytest.mark.asyncio
async def test_planned_intent_with_cause_and_route_adds_bounded_bias() -> None:
    owner_ledger = _owner_ledger()
    biases = migration_displacement_action_biases(
        owner_ledger,
        observation=_current_observation(),
        known_destinations=(L2, L4),
        policy=POLICY,
    )
    assert set(biases) == {"loc-4"}
    assert 0.0 < biases["loc-4"] <= POLICY.max_destination_bias == 0.25
    # The bias flips an otherwise tied choice to the supported destination.
    assert (await _select(None)).selected_future_id == "move-2"
    chosen = await _select(biases)
    assert chosen.selected_future_id == "move-4"
    assert await _select(biases) == chosen
    # Many intents or causes never push the bias past the bound.
    heavy = ledger(
        intents=tuple(
            intent(
                (L1, L4),
                causes=(cause(tick=index + 1),),
                status=MigrationIntentStatus.PLANNED,
                tick=index + 1,
            )
            for index in range(5)
        ),
        routes=(route((L1, L4)),),
        causes=tuple(cause(tick=index + 1) for index in range(5)),
    )
    capped = migration_displacement_action_biases(
        heavy,
        observation=_current_observation(),
        known_destinations=(L4,),
        policy=POLICY,
    )
    assert capped["loc-4"] <= POLICY.max_destination_bias
    # A departed intent contributes; an arrived or abandoned one does not.
    for status, expected in (
        (MigrationIntentStatus.DEPARTED, True),
        (MigrationIntentStatus.CONSIDERED, False),
        (MigrationIntentStatus.ARRIVED, False),
        (MigrationIntentStatus.ABANDONED, False),
        (MigrationIntentStatus.EXPIRED, False),
    ):
        result = _biases(_belief((A, B), status=status))
        assert bool(result) is expected
    # Base biases are composed by addition and never mutated.
    base = {"loc-b": 0.05, "other": 0.5}
    composed = _biases(_belief((A, B)), base=base)
    assert base == {"loc-b": 0.05, "other": 0.5}
    assert composed["other"] == 0.5
    assert composed["loc-b"] > 0.05


def test_unresolved_route_adds_no_bias() -> None:
    unresolved = route(
        (A, B, C),
        basis=RouteBeliefBasis.UNRESOLVED,
        status=RouteBeliefStatus.UNRESOLVED,
    )
    assert _biases(_belief((A, B, C), route_row=unresolved)) == {}
    blocked = route((A, B, C), status=RouteBeliefStatus.BLOCKED_BELIEF)
    assert _biases(_belief((A, B, C), route_row=blocked)) == {}
    # No route belief at all means no bias either.
    cause_row = cause()
    no_route = ledger(
        intents=(intent((A, B), causes=(cause_row,)),), causes=(cause_row,)
    )
    assert _biases(no_route) == {}
    # With an open observed route the same intent does contribute.
    assert _biases(_belief((A, B, C)))["loc-b"] > 0.0


def test_unknown_cause_adds_no_bias() -> None:
    unknown = cause(MigrationCauseKind.UNKNOWN)
    assert _biases(_belief((A, B), cause_row=unknown)) == {}
    superseded = cause(status=CauseEvidenceStatus.SUPERSEDED)
    assert _biases(_belief((A, B), cause_row=superseded)) == {}
    contradicted = cause(status=CauseEvidenceStatus.CONTRADICTED)
    assert _biases(_belief((A, B), cause_row=contradicted)) == {}
    # A stronger cause yields a larger bias than a weaker one.
    weak = _biases(_belief((A, B), cause_row=cause(confidence=0.3)))
    strong = _biases(_belief((A, B), cause_row=cause(confidence=0.9)))
    assert 0.0 < weak["loc-b"] < strong["loc-b"] <= 0.25


def test_multi_hop_route_biases_only_the_next_adjacent_step() -> None:
    owner_ledger = _belief((A, B, C, D))
    at_start = _biases(owner_ledger, at=A, known=(B, C, D))
    assert set(at_start) == {"loc-b"}
    at_middle = _biases(owner_ledger, at=B, known=(A, C, D))
    assert set(at_middle) == {"loc-c"}
    at_last = _biases(owner_ledger, at=C, known=(B, D))
    assert set(at_last) == {"loc-d"}
    # Standing on the destination or off the route biases nothing.
    assert _biases(owner_ledger, at=D, known=(A, B, C)) == {}
    assert _biases(owner_ledger, at=EntityId("loc-z"), known=(A, B, C, D)) == {}
    # A next hop that is not a visible known destination is never biased.
    assert _biases(owner_ledger, at=A, known=(C, D)) == {}
    # A traveller already in a journey takes no extra destination bias.
    journey = object()
    assert _biases(owner_ledger, at=A, known=(B,), journey=journey) == {}


@pytest.mark.asyncio
async def test_bias_never_constructs_a_command() -> None:
    biases = migration_displacement_action_biases(
        _owner_ledger(),
        observation=_current_observation(),
        known_destinations=(L2, L4),
        policy=POLICY,
    )
    assert isinstance(biases, dict)
    for key, value in biases.items():
        assert type(key) is str
        assert type(value) is float
    # The planner still compiles exactly one ordinary closed command.
    futures = _futures()
    loop_input = _loop_input(OWNER_ID, _current_observation(hunger=0.0), ())
    selection = await _select(biases)
    plan = await CommandPlanner().plan(
        loop_input, selection, PossibleFutures(OWNER_ID, futures, confidence=1.0)
    )
    assert type(plan.command) is Move
    assert plan.command.destination_id == L4
    # A bias on a non-Move future is ignored and cannot turn Wait into a move.
    wait = _future("wait", ActionDirection.WAIT, None)
    only_wait = await _select({"wait": 0.25, "loc-4": 0.25}, futures=(wait,))
    assert only_wait.selected_future_id == "wait"
    wait_plan = await CommandPlanner().plan(
        loop_input,
        only_wait,
        PossibleFutures(OWNER_ID, (wait,), confidence=1.0),
    )
    assert type(wait_plan.command) is Wait


@pytest.mark.asyncio
async def test_bias_does_not_bypass_capacity_or_fatigue() -> None:
    limit = POLICY.max_destination_bias
    assert limit == 0.25
    # The bias is bounded and applies to existing candidates only: it cannot
    # create a candidate, so a missing Move future is never selected.
    big = _biases(_belief((A, B)))
    assert max(big.values()) <= limit
    wait = _future("wait", ActionDirection.WAIT, None)
    result = await _select({"loc-4": limit, "loc-2": limit}, futures=(wait,))
    assert result.selected_future_id == "wait"
    # An unknown key is ignored; a non-finite value is rejected loudly.
    assert (await _select({"unknown-key": limit})) == await _select(None)
    for bad in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="migration_displacement: bias"):
            await _select({"loc-4": bad})
    with pytest.raises(ValueError, match="migration_displacement: bias"):
        migration_displacement_action_biases(
            _belief((A, B)),
            observation=observation(),
            known_destinations=(B,),
            base_biases={"loc-b": math.nan},
            policy=POLICY,
        )
    # A journey in progress and a non-adjacent step both stay unbiased.
    assert _biases(_belief((A, B, C)), at=A, known=(C,)) == {}
    assert _biases(_belief((A, B)), journey=object()) == {}
    # The policy cap is locked and not a runner field.
    with pytest.raises(ValueError):
        dataclasses.replace(POLICY, max_destination_bias=0.5)


@pytest.mark.asyncio
async def test_permutation_of_causes_does_not_change_selection() -> None:
    forward = _owner_ledger(causes_first=True)
    backward = _owner_ledger(causes_first=False)
    kwargs = dict(
        observation=_current_observation(),
        known_destinations=(L2, L4),
        policy=POLICY,
    )
    first = migration_displacement_action_biases(forward, **kwargs)
    second = migration_displacement_action_biases(backward, **kwargs)
    assert first == second
    assert (await _select(first)) == (await _select(second))
    assert (await _select(first)).selected_future_id == "move-4"
    # The prepared loop path builds the same bias and keeps one adjacent Move.
    config = dataclasses.replace(
        production_cognition_config(),
        migration_displacement_mode=CognitionMigrationDisplacementMode.DETERMINISTIC,
    )
    loop = build_cognitive_loop(config)
    prepared = loop._prepare_migration_displacement(
        _loop_input(OWNER_ID, _current_observation(), ()),
        organization_concepts=None,
        institution_concepts=None,
        formal_rules=None,
        disputes=None,
        evidence=None,
        diplomacy=None,
        organized_conflict=None,
        borders=None,
    )
    assert prepared is not None
    assert prepared.owner_id == OWNER_ID
    assert all(
        0.0 <= value <= POLICY.max_destination_bias
        for value in loop._prepared_migration_displacement_biases.values()
    )
