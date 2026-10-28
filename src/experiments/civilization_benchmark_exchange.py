"""Bounded v55 compositions for benchmark cases 12-15 (succession, exchange).

These recipes declare physical inventories, a corpse-custody channel, public
commitment speech and a private valuation channel. They never install an
inheritance law, enforce a debt, seed a valuation ledger, or name money.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.civilization_benchmark_base import (
    V3BenchmarkScenarioBuild,
    build_v3_benchmark_scenario,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_models import (
    V3BenchmarkCheck,
    V3BenchmarkCheckStatus,
    V3BenchmarkCoverage,
    V3BenchmarkError,
    V3BenchmarkEvidenceAvailability,
    V3BenchmarkLane,
    V3BenchmarkProfile,
    V3BenchmarkSourceKind,
    V3BenchmarkSourceReference,
)
from experiments.civilization_benchmark_suite import (
    V3_BENCH_12_INHERITANCE_PRACTICES,
    V3_BENCH_13_LONG_TERM_COMMITMENTS,
    V3_BENCH_14_SUBJECTIVE_BARTER,
    V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    CommunicationStrategyMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_possession_succession_spec,
    example_resource_exchange_profile_spec,
    example_structured_commitments_spec,
    example_subjective_valuation_spec,
)
from world.actions import (
    AssertPossessionClaim,
    DeclareCommitment,
    Give,
    NegotiateExchange,
    Take,
    Wait,
)
from world.identifiers import EntityId
from world.models import AgentBody, Item, LifeStatus
from world.values import (
    CarryCapacity,
    Fatigue,
    Health,
    Hunger,
    ItemKind,
    ItemLoad,
    TemperatureCelsius,
    Thirst,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_exchange"
)

EXCHANGE_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_12_INHERITANCE_PRACTICES,
    V3_BENCH_13_LONG_TERM_COMMITMENTS,
    V3_BENCH_14_SUBJECTIVE_BARTER,
    V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM,
)

_ORIGIN_AGENT_ID: Final[str] = "agent-origin"
_ORIGIN_BODY_ID: Final[str] = "body-origin"
_EXTRA_1_AGENT_ID: Final[str] = "agent-extra-1"
_EXTRA_1_BODY_ID: Final[str] = "body-extra-1"
_EXTRA_2_AGENT_ID: Final[str] = "agent-extra-2"
_EXTRA_2_BODY_ID: Final[str] = "body-extra-2"
_LOCATION_ID: Final[str] = "loc-origin"

_ORIGIN_SHELL_ID: Final[str] = "item-bench-origin-shell"
_EXTRA_1_BEAD_ID: Final[str] = "item-bench-extra-1-bead"
_EXTRA_1_TOKEN_ID: Final[str] = "item-bench-extra-1-token"
_EXTRA_2_TOKEN_ID: Final[str] = "item-bench-extra-2-token"


def _item(item_id: str, *, holder_id: str) -> Item:
    return Item(
        entity_id=EntityId(item_id),
        name=f"Bench exchange item {item_id}",
        kind=ItemKind.MATERIAL,
        load=ItemLoad(1),
        holder_id=EntityId(holder_id),
    )


def _extra_body(body_id: str, *, inventory: tuple[str, ...]) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(body_id),
        location_id=EntityId(_LOCATION_ID),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=tuple(EntityId(item) for item in inventory),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(12),
    )


def _extra_cognition(agent_id: AgentId) -> AgentCognitionSpec:
    return AgentCognitionSpec(
        agent_id=agent_id,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
    )


def _extra_agent(agent_id: str, body_id: str) -> AgentRunnerSpec:
    return AgentRunnerSpec(
        agent_id=AgentId(agent_id),
        entity_id=EntityId(body_id),
        cognition=_extra_cognition(AgentId(agent_id)),
        initial_goals=(),
    )


def _with_exchange_setup(
    config: SimulationRunnerConfig, *, extras: tuple[str, ...]
) -> SimulationRunnerConfig:
    """Declare co-located holders and named items; seed no belief or price."""
    scenario = config.scenario
    bodies = []
    for body in scenario.bodies:
        if body.entity_id.value == _ORIGIN_BODY_ID:
            bodies.append(
                replace(
                    body,
                    location_id=EntityId(_LOCATION_ID),
                    hunger=Hunger(0.0),
                    thirst=Thirst(0.0),
                    inventory=(EntityId(_ORIGIN_SHELL_ID),),
                )
            )
        else:
            bodies.append(body)
    existing = {body.entity_id.value for body in bodies}
    if "extra-1" in extras and _EXTRA_1_BODY_ID not in existing:
        bodies.append(
            _extra_body(
                _EXTRA_1_BODY_ID,
                inventory=(_EXTRA_1_BEAD_ID, _EXTRA_1_TOKEN_ID),
            )
        )
    if "extra-2" in extras and _EXTRA_2_BODY_ID not in existing:
        bodies.append(_extra_body(_EXTRA_2_BODY_ID, inventory=(_EXTRA_2_TOKEN_ID,)))
    items = list(scenario.items)
    present = {item.entity_id.value for item in items}
    declarations = [(_ORIGIN_SHELL_ID, _ORIGIN_BODY_ID)]
    if "extra-1" in extras:
        declarations.extend(
            (
                (_EXTRA_1_BEAD_ID, _EXTRA_1_BODY_ID),
                (_EXTRA_1_TOKEN_ID, _EXTRA_1_BODY_ID),
            )
        )
    if "extra-2" in extras:
        declarations.append((_EXTRA_2_TOKEN_ID, _EXTRA_2_BODY_ID))
    for item_id, holder_id in declarations:
        if item_id not in present:
            items.append(_item(item_id, holder_id=holder_id))
    agents = list(config.agents)
    known = {agent.agent_id.value for agent in agents}
    if "extra-1" in extras and _EXTRA_1_AGENT_ID not in known:
        agents.append(_extra_agent(_EXTRA_1_AGENT_ID, _EXTRA_1_BODY_ID))
    if "extra-2" in extras and _EXTRA_2_AGENT_ID not in known:
        agents.append(_extra_agent(_EXTRA_2_AGENT_ID, _EXTRA_2_BODY_ID))
    return replace(
        config,
        scenario=replace(scenario, bodies=tuple(bodies), items=tuple(items)),
        agents=tuple(agents),
    )


def _exchange_config(
    scenario_id: str, base: SimulationRunnerConfig
) -> SimulationRunnerConfig:
    if scenario_id == V3_BENCH_12_INHERITANCE_PRACTICES:
        return replace(base, possession_succession=example_possession_succession_spec())
    if scenario_id == V3_BENCH_13_LONG_TERM_COMMITMENTS:
        return replace(
            base, structured_commitments=example_structured_commitments_spec()
        )
    if scenario_id == V3_BENCH_14_SUBJECTIVE_BARTER:
        return replace(base, subjective_valuation=example_subjective_valuation_spec())
    if scenario_id == V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM:
        return replace(
            base,
            subjective_valuation=example_subjective_valuation_spec(),
            resource_exchange_profile=example_resource_exchange_profile_spec(),
        )
    raise V3BenchmarkError(
        "unknown_scenario", f"not an exchange benchmark: {scenario_id!r}"
    )


def build_exchange_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 4 succession/commitment/exchange case."""
    if scenario_id not in EXCHANGE_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not an exchange benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    extras: tuple[str, ...] = ()
    if scenario_id in {
        V3_BENCH_13_LONG_TERM_COMMITMENTS,
        V3_BENCH_14_SUBJECTIVE_BARTER,
    }:
        extras = ("extra-1",)
    elif scenario_id == V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM:
        extras = ("extra-1", "extra-2")
    base = _with_exchange_setup(build.arms[0].config, extras=extras)
    config = _exchange_config(scenario_id, base)
    founder_ids = tuple(agent.agent_id.value for agent in config.agents)
    arms = tuple(
        replace(arm, config=config, founder_ids=founder_ids) for arm in build.arms
    )
    result = replace(build, arms=arms)
    _LOG.debug(
        "exchange_benchmark_built scenario_id=%s lane=%s profile=%s "
        "succession=%s commitments=%s valuation=%s profile_channel=%s",
        scenario_id,
        lane.value,
        profile.value,
        config.possession_succession is not None,
        config.structured_commitments is not None,
        config.subjective_valuation is not None,
        config.resource_exchange_profile is not None,
    )
    return result


def _lifespan(config: SimulationRunnerConfig) -> int:
    lifecycle = config.population_lifecycle
    if lifecycle is None:
        return 4
    return lifecycle.lifespan_ticks


def _wait(agent_id: str, tick: int, label: str) -> MilestoneOverride:
    return MilestoneOverride(
        milestone_id=f"v3-bench-{label}-wait-{tick:04d}",
        tick=tick,
        agent_id=AgentId(agent_id),
        build_command=lambda: Wait(),
    )


def _succession_milestones(config: SimulationRunnerConfig) -> list[MilestoneOverride]:
    lifespan = _lifespan(config)
    lifecycle = config.population_lifecycle
    params = None if lifecycle is None else lifecycle.demographic_policy_params
    raw = {} if params is None else dict(params)
    interval_raw = raw.get("interval_ticks", 8)
    interval = interval_raw if type(interval_raw) is int and interval_raw >= 1 else 8
    claimant = AgentId(f"entrant-{interval:04d}-00")
    milestones: list[MilestoneOverride] = []
    for tick in range(lifespan + 1):
        milestones.append(_wait(_ORIGIN_AGENT_ID, tick, "succession-decedent"))
    first_claim = max(lifespan + 1, interval + 1)
    milestones.append(
        MilestoneOverride(
            milestone_id="v3-bench-succession-claim",
            tick=first_claim,
            agent_id=claimant,
            build_command=lambda: AssertPossessionClaim(
                decedent_id=EntityId(_ORIGIN_BODY_ID),
                doctrine="children_should_inherit",
                item_id=EntityId(_ORIGIN_SHELL_ID),
            ),
        )
    )
    milestones.append(
        MilestoneOverride(
            milestone_id="v3-bench-succession-rival-claim",
            tick=first_claim + 1,
            agent_id=claimant,
            build_command=lambda: AssertPossessionClaim(
                decedent_id=EntityId(_ORIGIN_BODY_ID),
                doctrine="first_claimant_owns",
                item_id=EntityId(_ORIGIN_SHELL_ID),
            ),
        )
    )
    milestones.append(
        MilestoneOverride(
            milestone_id="v3-bench-succession-take",
            tick=first_claim + 2,
            agent_id=claimant,
            build_command=lambda: Take(item_id=EntityId(_ORIGIN_SHELL_ID)),
        )
    )
    return milestones


def _commitment_milestones() -> list[MilestoneOverride]:
    return [
        _wait(_EXTRA_1_AGENT_ID, 0, "commitment-counterparty"),
        _wait(_EXTRA_1_AGENT_ID, 1, "commitment-counterparty"),
        _wait(_EXTRA_1_AGENT_ID, 2, "commitment-counterparty"),
        MilestoneOverride(
            milestone_id="v3-bench-commitment-declare-fulfilled",
            tick=0,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: DeclareCommitment(
                counterparty_id=EntityId(_EXTRA_1_BODY_ID),
                commitment_kind="promise",
                act="propose",
                owed_by="self",
                service="none",
                quantity=1,
                due_kind="by_tick",
                item_kind=ItemKind.MATERIAL,
                due_tick=2,
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-commitment-declare-violated",
            tick=1,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: DeclareCommitment(
                counterparty_id=EntityId(_EXTRA_1_BODY_ID),
                commitment_kind="debt",
                act="propose",
                owed_by="self",
                service="none",
                quantity=1,
                due_kind="by_tick",
                item_kind=ItemKind.MATERIAL,
                due_tick=3,
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-commitment-fulfil",
            tick=2,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: Give(
                recipient_id=EntityId(_EXTRA_1_BODY_ID),
                item_id=EntityId(_ORIGIN_SHELL_ID),
            ),
        ),
    ]


def _barter_milestones() -> list[MilestoneOverride]:
    return [
        MilestoneOverride(
            milestone_id="v3-bench-barter-offer",
            tick=0,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_EXTRA_1_BODY_ID),
                act="offer",
                give_item_ids=(EntityId(_ORIGIN_SHELL_ID),),
                take_item_ids=(EntityId(_EXTRA_1_BEAD_ID),),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-barter-accept",
            tick=0,
            agent_id=AgentId(_EXTRA_1_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_ORIGIN_BODY_ID),
                act="accept",
                give_item_ids=(EntityId(_EXTRA_1_BEAD_ID),),
                take_item_ids=(EntityId(_ORIGIN_SHELL_ID),),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-barter-stale-offer",
            tick=1,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_EXTRA_1_BODY_ID),
                act="offer",
                give_item_ids=(EntityId(_EXTRA_1_TOKEN_ID),),
                take_item_ids=(EntityId(_EXTRA_2_TOKEN_ID),),
            ),
        ),
    ]


def _medium_milestones() -> list[MilestoneOverride]:
    return [
        MilestoneOverride(
            milestone_id="v3-bench-medium-offer-0",
            tick=0,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_EXTRA_1_BODY_ID),
                act="offer",
                give_item_ids=(EntityId(_ORIGIN_SHELL_ID),),
                take_item_ids=(EntityId(_EXTRA_1_BEAD_ID),),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-medium-accept-0",
            tick=0,
            agent_id=AgentId(_EXTRA_1_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_ORIGIN_BODY_ID),
                act="accept",
                give_item_ids=(EntityId(_EXTRA_1_BEAD_ID),),
                take_item_ids=(EntityId(_ORIGIN_SHELL_ID),),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-medium-gather",
            tick=0,
            agent_id=AgentId(_EXTRA_2_AGENT_ID),
            build_command=lambda: Wait(),
        ),
        _wait(_ORIGIN_AGENT_ID, 1, "medium-holder-origin"),
        _wait(_EXTRA_2_AGENT_ID, 1, "medium-holder-extra-2"),
        MilestoneOverride(
            milestone_id="v3-bench-medium-offer-1",
            tick=2,
            agent_id=AgentId(_ORIGIN_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_EXTRA_2_BODY_ID),
                act="offer",
                give_item_ids=(EntityId(_EXTRA_1_BEAD_ID),),
                take_item_ids=(EntityId(_EXTRA_2_TOKEN_ID),),
            ),
        ),
        MilestoneOverride(
            milestone_id="v3-bench-medium-accept-1",
            tick=2,
            agent_id=AgentId(_EXTRA_2_AGENT_ID),
            build_command=lambda: NegotiateExchange(
                counterparty_id=EntityId(_ORIGIN_BODY_ID),
                act="accept",
                give_item_ids=(EntityId(_EXTRA_2_TOKEN_ID),),
                take_item_ids=(EntityId(_EXTRA_1_BEAD_ID),),
            ),
        ),
    ]


def exchange_benchmark_arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Schedule ordinary admitted commands; no ledger or price is installed."""
    if scenario_id not in EXCHANGE_BENCHMARK_IDS:
        return None
    if scenario_id == V3_BENCH_12_INHERITANCE_PRACTICES:
        milestones = _succession_milestones(config)
    elif scenario_id == V3_BENCH_13_LONG_TERM_COMMITMENTS:
        milestones = _commitment_milestones()
    elif scenario_id == V3_BENCH_14_SUBJECTIVE_BARTER:
        milestones = _barter_milestones()
    else:
        milestones = _medium_milestones()
    _LOG.debug(
        "exchange_benchmark_arbiter_ready scenario_id=%s milestone_count=%s",
        scenario_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )


def required_exchange_milestones(scenario_id: str) -> tuple[str, ...]:
    """Milestone ids whose APPLIED acknowledgement the fixture requires."""
    if scenario_id == V3_BENCH_12_INHERITANCE_PRACTICES:
        return (
            "v3-bench-succession-claim",
            "v3-bench-succession-rival-claim",
            "v3-bench-succession-take",
        )
    if scenario_id == V3_BENCH_13_LONG_TERM_COMMITMENTS:
        return (
            "v3-bench-commitment-declare-fulfilled",
            "v3-bench-commitment-declare-violated",
            "v3-bench-commitment-fulfil",
        )
    if scenario_id == V3_BENCH_14_SUBJECTIVE_BARTER:
        return ("v3-bench-barter-offer", "v3-bench-barter-accept")
    if scenario_id == V3_BENCH_15_CANDIDATE_EXCHANGE_MEDIUM:
        return (
            "v3-bench-medium-offer-0",
            "v3-bench-medium-accept-0",
            "v3-bench-medium-offer-1",
            "v3-bench-medium-accept-1",
        )
    return ()


def _window_complete(probe: BenchmarkBoundaryProbe, boundary_end_tick: int) -> bool:
    observations = probe.observations
    return (
        bool(observations)
        and observations[-1].boundary_tick == boundary_end_tick
        and not probe.failures
    )


def _owner_ref(owner_id: str) -> V3BenchmarkSourceReference:
    return V3BenchmarkSourceReference(
        source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
        reference_id=owner_id,
        owner_id=owner_id,
    )


def _event_ref(probe: BenchmarkBoundaryProbe, kind: str) -> V3BenchmarkSourceReference:
    return V3BenchmarkSourceReference(
        source_kind=V3BenchmarkSourceKind.OBJECTIVE_INSPECTION,
        reference_id=f"event-kind:{kind}",
        tick=(probe.observations[-1].boundary_tick if probe.observations else None),
    )


def _unavailable(selector: str, reason: str) -> V3BenchmarkCheck:
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.UNEXECUTED,
        reason_code=reason,
        evidence=V3BenchmarkEvidenceAvailability.UNAVAILABLE,
        coverage=V3BenchmarkCoverage.NOT_EXERCISED,
        source_references=(),
    )


def _measured(
    selector: str,
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    reason_code: str,
    numerator: int,
    denominator: int,
    owner_ids: tuple[str, ...],
    event_kinds: tuple[str, ...],
) -> V3BenchmarkCheck:
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=reason_code,
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=(
            tuple(_owner_ref(owner) for owner in owner_ids)
            + tuple(_event_ref(probe, kind) for kind in event_kinds)
        ),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=numerator,
        denominator=denominator,
    )


def _store_measured(probe: BenchmarkBoundaryProbe, store: str) -> tuple[str, ...]:
    if not probe.observations:
        return ()
    return tuple(
        owner.owner_id
        for owner in probe.observations[-1].owners
        if (owner.count(store) or 0) > 0
    )


def evaluate_possession_succession(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Claims and corpse takes are separate objective/practice evidence."""
    if not mechanism_available:
        return _unavailable(
            "possession_succession_evidence", "possession_succession_disabled"
        )
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id="possession_succession_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    claims = probe.event_total("PossessionClaimAsserted")
    custody = probe.event_total("CorpseCustodyOpened")
    takes = probe.event_total("TakenFromCorpse")
    if claims < 1 or custody < 1:
        return V3BenchmarkCheck(
            selector_id="possession_succession_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_custody_or_claim_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=claims,
            denominator=claims,
        )
    owners = _store_measured(probe, "possession_legitimacy")
    reason = (
        "succession_claim_and_transfer_observed"
        if takes > 0
        else "succession_claim_without_transfer_observed"
    )
    return _measured(
        "possession_succession_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        reason_code=reason,
        numerator=min(takes, claims),
        denominator=claims,
        owner_ids=owners,
        event_kinds=(
            "PossessionClaimAsserted",
            "CorpseCustodyOpened",
            "TakenFromCorpse",
        ),
    )


def evaluate_commitments(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Count declared promises and observed transfers; do not adjudicate terms."""
    if not mechanism_available:
        return _unavailable("commitment_evidence", "structured_commitments_disabled")
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id="commitment_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    promises = probe.commitment_promises
    if not promises:
        return V3BenchmarkCheck(
            selector_id="commitment_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_commitment_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    transfers = probe.given_transfers

    resolved = sorted(
        (
            promise
            for promise in promises
            if promise[2] is not None and promise[2] < boundary_end_tick
        ),
        key=lambda item: (item[2] or 0, item[0], item[1]),
    )
    unresolved = [promise for promise in promises if promise not in resolved]
    used: set[int] = set()
    fulfilled: list[tuple[str, str, int | None]] = []
    violated: list[tuple[str, str, int | None]] = []
    for promise in resolved:
        actor, recipient, due = promise
        match = None
        for index, (tick, giver, receiver) in enumerate(transfers):
            if index in used or giver != actor or receiver != recipient:
                continue
            if due is not None and tick > due:
                continue
            match = index
            break
        if match is None:
            violated.append(promise)
        else:
            used.add(match)
            fulfilled.append(promise)
    if fulfilled and violated:
        reason = "commitment_fulfilment_and_violation_observed"
    elif fulfilled:
        reason = "commitment_fulfilment_observed"
    elif violated:
        reason = "commitment_violation_observed"
    else:
        reason = "commitment_unresolved_observed"
    denominator = len(resolved) if resolved else len(unresolved)
    return _measured(
        "commitment_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        reason_code=reason,
        numerator=len(fulfilled),
        denominator=denominator,
        owner_ids=_store_measured(probe, "structured_commitments"),
        event_kinds=("CommitmentDeclared", "Given"),
    )


def evaluate_subjective_exchange(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Measure negotiation and completed swaps without exposing reservations."""
    if not mechanism_available:
        return _unavailable(
            "subjective_exchange_evidence", "subjective_valuation_disabled"
        )
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id="subjective_exchange_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    proposed = probe.event_total("ExchangeProposed")
    if proposed < 1:
        return V3BenchmarkCheck(
            selector_id="subjective_exchange_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_exchange_negotiation_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    completed = probe.event_total("ExchangeCompleted")
    return _measured(
        "subjective_exchange_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        reason_code=(
            "exchange_completed_observed"
            if completed > 0
            else "exchange_negotiated_without_agreement"
        ),
        numerator=completed,
        denominator=proposed,
        owner_ids=_store_measured(probe, "subjective_valuations"),
        event_kinds=("ExchangeProposed", "ExchangeCompleted"),
    )


def evaluate_exchange_functions(
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Repeated acceptance of an ordinary item is measured, never called money."""
    if not mechanism_available:
        return _unavailable("exchange_function_evidence", "resource_profile_disabled")
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id="exchange_function_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    completed = probe.event_total("ExchangeCompleted")
    if completed < 1:
        return V3BenchmarkCheck(
            selector_id="exchange_function_evidence",
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="no_completed_exchange_observed",
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    return _measured(
        "exchange_function_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        reason_code=(
            "repeated_acceptance_observed"
            if completed >= 2
            else "single_acceptance_observed"
        ),
        numerator=completed,
        denominator=completed,
        owner_ids=_store_measured(probe, "acceptance_memories"),
        event_kinds=("ExchangeProposed", "ExchangeCompleted"),
    )


__all__ = [
    "EXCHANGE_BENCHMARK_IDS",
    "build_exchange_benchmark",
    "evaluate_commitments",
    "evaluate_exchange_functions",
    "evaluate_possession_succession",
    "evaluate_subjective_exchange",
    "exchange_benchmark_arbiter",
    "required_exchange_milestones",
]
