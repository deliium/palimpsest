"""Bounded v55 compositions for benchmark cases 24-28 (narratives and roles).

Owners may retain historical narratives, role concepts, office claims,
institutional memory and decay history. Every channel is owner-local: no
objective office, institution type, global successor registry or narrative
truth exists. Controlled fixtures schedule ordinary speech and record
opportunities; a candidate that fails to form remains a valid outcome.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from experiments.civilization_benchmark_base import (
    V3BenchmarkScenarioBuild,
    build_v3_benchmark_scenario,
)
from experiments.civilization_benchmark_evidence import (
    BenchmarkBoundaryProbe,
    content_count,
)
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
    V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
    V3_BENCH_25_PERSISTENT_ROLE,
    V3_BENCH_26_OFFICE_SUCCESSION,
    V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
    V3_BENCH_28_INSTITUTIONAL_DECAY,
)
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.new_agent_initialization import (
    SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    NewAgentInitializationSpec,
    default_new_agent_initialization_spec,
)
from simulation.runner_models import (
    AgentCognitionSpec,
    AgentRunnerSpec,
    ArtifactInterpretationMode,
    CommunicationStrategyMode,
    CulturalNarrativeMode,
    InstitutionalDecayMode,
    InstitutionalMemoryMode,
    InstitutionConceptMode,
    OfficeSuccessionMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    TeachingInteractionMode,
    example_generational_narratives_spec,
)
from world.actions import Inscribe, Talk, Wait
from world.artifacts import ArtifactContent, ArtifactKind
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId
from world.models import AgentBody, LifeStatus
from world.values import (
    CarryCapacity,
    DayPhase,
    Fatigue,
    Health,
    Hunger,
    TemperatureCelsius,
    Thirst,
)

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.civilization_benchmark_institutions"
)

INSTITUTIONS_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_24_NARRATIVE_AFTER_WITNESSES,
    V3_BENCH_25_PERSISTENT_ROLE,
    V3_BENCH_26_OFFICE_SUCCESSION,
    V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
    V3_BENCH_28_INSTITUTIONAL_DECAY,
)

_ORIGIN_AGENT_ID: Final[str] = "agent-origin"
_EXTRA_1_AGENT_ID: Final[str] = "agent-extra-1"
_EXTRA_1_BODY_ID: Final[str] = "body-extra-1"
_EXTRA_2_AGENT_ID: Final[str] = "agent-extra-2"
_EXTRA_2_BODY_ID: Final[str] = "body-extra-2"
_ORIGIN_BODY_ID: Final[str] = "body-origin"
_CONTEXT_KEY: Final[str] = "0123456789abcdef"
_ROLE_TOKEN: Final[str] = "shared_work"
_ROLE_FUNCTION: Final[str] = "collective_project"
_OFFICE_CHANNEL: Final[str] = "social_expectation"
_OFFICE_PREDICATES: Final[Mapping[str, str]] = {
    "role": "office_role",
    "endorse": "office_endorse",
    "dispute": "office_dispute",
    "succession": "office_succession",
    "relinquish": "office_relinquish",
}


def _learner_initializer() -> NewAgentInitializationSpec:
    """Modes-on/content-empty descendant pack; never a copied founder config."""
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    )


def _cognition(
    agent_id: AgentId,
    *,
    narrative: bool,
    institution: bool,
    office: bool,
    memory: bool,
    decay: bool,
) -> AgentCognitionSpec:
    return AgentCognitionSpec(
        agent_id=agent_id,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
        cultural_narrative_mode=(
            CulturalNarrativeMode.DETERMINISTIC
            if narrative
            else CulturalNarrativeMode.DISABLED
        ),
        institution_concept_mode=(
            InstitutionConceptMode.DETERMINISTIC
            if institution
            else InstitutionConceptMode.DISABLED
        ),
        office_succession_mode=(
            OfficeSuccessionMode.DETERMINISTIC
            if office
            else OfficeSuccessionMode.DISABLED
        ),
        institutional_memory_mode=(
            InstitutionalMemoryMode.DETERMINISTIC
            if memory
            else InstitutionalMemoryMode.DISABLED
        ),
        institutional_decay_mode=(
            InstitutionalDecayMode.DETERMINISTIC
            if decay
            else InstitutionalDecayMode.DISABLED
        ),
    )


def _extra_body(body_id: str, location_id: str) -> AgentBody:
    return AgentBody(
        entity_id=EntityId(body_id),
        location_id=EntityId(location_id),
        health=Health(100.0),
        hunger=Hunger(0.0),
        thirst=Thirst(0.0),
        fatigue=Fatigue(0.0),
        temperature=TemperatureCelsius(36.5),
        inventory=(),
        life_status=LifeStatus.ALIVE,
        carry_capacity=CarryCapacity(12),
    )


def _with_role_owners(
    config: SimulationRunnerConfig,
    *,
    narrative: bool,
    institution: bool,
    office: bool,
    memory: bool,
    decay: bool,
) -> SimulationRunnerConfig:
    scenario = config.scenario
    bodies = [
        (
            replace(body, hunger=Hunger(0.0), thirst=Thirst(0.0))
            if body.entity_id.value == _ORIGIN_BODY_ID
            else body
        )
        for body in scenario.bodies
    ]
    existing = {body.entity_id.value for body in bodies}
    for body_id in (_EXTRA_1_BODY_ID, _EXTRA_2_BODY_ID):
        if body_id not in existing:
            bodies.append(_extra_body(body_id, "loc-origin"))
    modes = {
        "narrative": narrative,
        "institution": institution,
        "office": office,
        "memory": memory,
        "decay": decay,
    }
    agents = tuple(
        replace(agent, cognition=_cognition(agent.agent_id, **modes))
        for agent in config.agents
    ) + tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=_cognition(AgentId(agent_id), **modes),
            initial_goals=(),
        )
        for agent_id, body_id in (
            (_EXTRA_1_AGENT_ID, _EXTRA_1_BODY_ID),
            (_EXTRA_2_AGENT_ID, _EXTRA_2_BODY_ID),
        )
    )
    return replace(
        config,
        scenario=replace(scenario, bodies=tuple(bodies)),
        agents=agents,
        new_agent_initialization=_learner_initializer(),
    )


def _institutions_config(
    scenario_id: str, base: SimulationRunnerConfig
) -> SimulationRunnerConfig:
    narrative = scenario_id == V3_BENCH_24_NARRATIVE_AFTER_WITNESSES
    institution = scenario_id != V3_BENCH_24_NARRATIVE_AFTER_WITNESSES
    office = scenario_id in {
        V3_BENCH_26_OFFICE_SUCCESSION,
        V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
    }
    memory = office
    decay = scenario_id == V3_BENCH_28_INSTITUTIONAL_DECAY
    composed = _with_role_owners(
        base,
        narrative=narrative,
        institution=institution,
        office=office,
        memory=memory,
        decay=decay,
    )
    if narrative:
        return replace(
            composed,
            generational_narratives=example_generational_narratives_spec(),
        )
    return composed


def build_institutions_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 6 narrative/role case."""
    if scenario_id not in INSTITUTIONS_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not an institutions benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    config = _institutions_config(scenario_id, build.arms[0].config)
    founder_ids = tuple(agent.agent_id.value for agent in config.agents)
    arms = tuple(
        replace(arm, config=config, founder_ids=founder_ids) for arm in build.arms
    )
    result = replace(build, arms=arms)
    _LOG.debug(
        "institutions_benchmark_built scenario_id=%s lane=%s profile=%s owners=%s "
        "narratives=%s",
        scenario_id,
        lane.value,
        profile.value,
        len(config.agents),
        config.generational_narratives is not None,
    )
    return result


def _day_ticks(config: SimulationRunnerConfig, horizon: int) -> tuple[int, ...]:
    rules = config.scenario.physical_rules
    ticks = tuple(
        tick
        for tick in range(horizon)
        if rules.day_phase_for_tick(tick) is DayPhase.DAY
    )
    return ticks or (0,)


def _talk(
    *,
    tick: int,
    speaker_body: str,
    recipient_body: str,
    text: str,
    relations: tuple[CommunicationRelation, ...],
) -> Talk:
    return Talk(
        recipient_id=EntityId(recipient_body),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker_body),
            communication_id=f"v3-bench-inst-{speaker_body}-{tick}",
            text=text,
            sender_confidence=0.7,
            relations=relations,
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _retell(
    tick: int,
    speaker_body: str,
    recipient_body: str,
    token: str,
) -> Callable[[], Talk]:
    def build() -> Talk:
        return _talk(
            tick=tick,
            speaker_body=speaker_body,
            recipient_body=recipient_body,
            text="retell",
            relations=(
                CommunicationRelation(
                    subject=token, predicate="retell", object="event"
                ),
            ),
        )

    return build


def _pattern(
    tick: int,
    speaker_body: str,
    recipient_body: str,
    token: str,
) -> Callable[[], Talk]:
    def build() -> Talk:
        return _talk(
            tick=tick,
            speaker_body=speaker_body,
            recipient_body=recipient_body,
            text="expect",
            relations=(
                CommunicationRelation(
                    subject=_OFFICE_CHANNEL,
                    predicate="institution_pattern",
                    object=token,
                ),
            ),
        )

    return build


def _office(
    tick: int,
    speaker_body: str,
    recipient_body: str,
    *,
    predicate: str,
    occupant_body: str | None = None,
    supporter_body: str | None = None,
) -> Callable[[], Talk]:
    occupant = "-" if occupant_body is None else occupant_body
    supporter = "-" if supporter_body is None else supporter_body
    canonical = _OFFICE_PREDICATES[predicate]

    def build() -> Talk:
        return _talk(
            tick=tick,
            speaker_body=speaker_body,
            recipient_body=recipient_body,
            text=predicate,
            relations=(
                CommunicationRelation(
                    subject=_ROLE_FUNCTION,
                    predicate=canonical,
                    object=f"{_CONTEXT_KEY}|{occupant}|{supporter}",
                ),
            ),
        )

    return build


def _wait(agent_id: str, tick: int) -> MilestoneOverride:
    return MilestoneOverride(
        milestone_id=f"v3-bench-inst-hold-{agent_id}-{tick:04d}",
        tick=tick,
        agent_id=AgentId(agent_id),
        build_command=lambda: Wait(),
    )


def _milestone(
    milestone_id: str, tick: int, agent_id: str, build: Callable[[], object]
) -> MilestoneOverride:
    return MilestoneOverride(
        milestone_id=milestone_id,
        tick=tick,
        agent_id=AgentId(agent_id),
        build_command=build,  # type: ignore[arg-type]
    )


def institutions_benchmark_arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Schedule ordinary speech/records; no role, office or truth is installed."""
    if scenario_id not in INSTITUTIONS_BENCHMARK_IDS:
        return None
    horizon = config.stop_policy.max_ticks or 8
    days = _day_ticks(config, horizon)
    milestones: list[MilestoneOverride] = []
    if scenario_id == V3_BENCH_24_NARRATIVE_AFTER_WITNESSES:
        milestones.append(
            _milestone(
                "v3-bench-inst-retell-0",
                days[0],
                _ORIGIN_AGENT_ID,
                _retell(days[0], _ORIGIN_BODY_ID, _EXTRA_1_BODY_ID, "founding"),
            )
        )
        second = days[1] if len(days) > 1 else days[0]
        milestones.append(
            _milestone(
                "v3-bench-inst-retell-1",
                second,
                _ORIGIN_AGENT_ID,
                _retell(second, _ORIGIN_BODY_ID, _EXTRA_1_BODY_ID, "founding_shift"),
            )
        )
    elif scenario_id == V3_BENCH_25_PERSISTENT_ROLE:
        milestones.extend(
            (
                _milestone(
                    "v3-bench-inst-expect-1",
                    days[0],
                    _EXTRA_1_AGENT_ID,
                    _pattern(days[0], _EXTRA_1_BODY_ID, _ORIGIN_BODY_ID, _ROLE_TOKEN),
                ),
                _milestone(
                    "v3-bench-inst-expect-2",
                    days[0],
                    _EXTRA_2_AGENT_ID,
                    _pattern(days[0], _EXTRA_2_BODY_ID, _ORIGIN_BODY_ID, _ROLE_TOKEN),
                ),
            )
        )
        if len(days) > 1:
            milestones.append(
                _milestone(
                    "v3-bench-inst-expect-repeat",
                    days[1],
                    _EXTRA_1_AGENT_ID,
                    _pattern(days[1], _EXTRA_1_BODY_ID, _ORIGIN_BODY_ID, _ROLE_TOKEN),
                )
            )
    else:
        milestones.extend(
            (
                _milestone(
                    "v3-bench-inst-endorse-1",
                    days[0],
                    _EXTRA_2_AGENT_ID,
                    _office(
                        days[0],
                        _EXTRA_2_BODY_ID,
                        _ORIGIN_BODY_ID,
                        predicate="endorse",
                        occupant_body=_EXTRA_1_BODY_ID,
                    ),
                ),
                _milestone(
                    "v3-bench-inst-endorse-2",
                    days[0],
                    _EXTRA_1_AGENT_ID,
                    _office(
                        days[0],
                        _EXTRA_1_BODY_ID,
                        _ORIGIN_BODY_ID,
                        predicate="endorse",
                        occupant_body=_EXTRA_1_BODY_ID,
                    ),
                ),
            )
        )
        expectation_tick = days[1] if len(days) > 1 else days[0]
        expectation_agent = (
            _EXTRA_2_AGENT_ID if expectation_tick == days[0] else _EXTRA_1_AGENT_ID
        )
        expectation_body = (
            _EXTRA_2_BODY_ID if expectation_tick == days[0] else _EXTRA_1_BODY_ID
        )
        milestones.append(
            _milestone(
                "v3-bench-inst-expect",
                expectation_tick,
                expectation_agent,
                _pattern(
                    expectation_tick,
                    expectation_body,
                    _ORIGIN_BODY_ID,
                    _ROLE_TOKEN,
                ),
            )
        )
        if len(days) > 2:
            milestones.extend(
                (
                    _milestone(
                        "v3-bench-inst-dispute",
                        days[2],
                        _EXTRA_2_AGENT_ID,
                        _office(
                            days[2],
                            _EXTRA_2_BODY_ID,
                            _ORIGIN_BODY_ID,
                            predicate="dispute",
                            occupant_body=_EXTRA_1_BODY_ID,
                        ),
                    ),
                    _milestone(
                        "v3-bench-inst-endorse-next",
                        days[2],
                        _EXTRA_1_AGENT_ID,
                        _office(
                            days[2],
                            _EXTRA_1_BODY_ID,
                            _ORIGIN_BODY_ID,
                            predicate="endorse",
                            occupant_body=_EXTRA_2_BODY_ID,
                        ),
                    ),
                )
            )
        if scenario_id in {
            V3_BENCH_26_OFFICE_SUCCESSION,
            V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
        }:
            milestones.append(
                _milestone(
                    "v3-bench-inst-record",
                    1,
                    _EXTRA_2_AGENT_ID,
                    lambda: Inscribe(
                        kind=ArtifactKind.RECORD,
                        content=ArtifactContent(),
                        hold=False,
                    ),
                )
            )
    if milestones:
        occupied = {(item.tick, item.agent_id.value) for item in milestones}
        last_scheduled = max(item.tick for item in milestones)
        controlled = {
            _ORIGIN_AGENT_ID,
            _EXTRA_1_AGENT_ID,
            _EXTRA_2_AGENT_ID,
        }
        for tick in range(last_scheduled):
            for agent_id in controlled:
                if (tick, agent_id) in occupied:
                    continue
                milestones.append(_wait(agent_id, tick))
    milestones.sort(key=lambda item: (item.tick, item.agent_id.value))
    _LOG.debug(
        "institutions_arbiter_ready scenario_id=%s milestone_count=%s",
        scenario_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )


def required_institutions_milestones(
    scenario_id: str, config: SimulationRunnerConfig
) -> tuple[str, ...]:
    horizon = config.stop_policy.max_ticks or 8
    days = _day_ticks(config, horizon)
    if scenario_id == V3_BENCH_24_NARRATIVE_AFTER_WITNESSES:
        return ("v3-bench-inst-retell-0", "v3-bench-inst-retell-1")
    if scenario_id == V3_BENCH_25_PERSISTENT_ROLE:
        return (
            "v3-bench-inst-expect-1",
            "v3-bench-inst-expect-2",
            "v3-bench-inst-expect-repeat",
        )
    if scenario_id in INSTITUTIONS_BENCHMARK_IDS:
        required = [
            "v3-bench-inst-endorse-1",
            "v3-bench-inst-endorse-2",
            "v3-bench-inst-expect",
        ]
        if len(days) > 2:
            required.extend(("v3-bench-inst-dispute", "v3-bench-inst-endorse-next"))
        if scenario_id in {
            V3_BENCH_26_OFFICE_SUCCESSION,
            V3_BENCH_27_INSTITUTIONAL_PERSISTENCE,
        }:
            required.append("v3-bench-inst-record")
        return tuple(required)
    return ()


def _window_complete(probe: BenchmarkBoundaryProbe, boundary_end_tick: int) -> bool:
    observations = probe.observations
    return (
        bool(observations)
        and observations[-1].boundary_tick == boundary_end_tick
        and not probe.failures
    )


def _owner_refs(owners: tuple[str, ...]) -> tuple[V3BenchmarkSourceReference, ...]:
    return tuple(
        V3BenchmarkSourceReference(
            source_kind=V3BenchmarkSourceKind.SUBJECTIVE_DEBUG,
            reference_id=owner,
            owner_id=owner,
        )
        for owner in owners
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


def _history_gate(
    selector: str,
    probe: BenchmarkBoundaryProbe,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
    disabled_reason: str,
    rows: int,
    owners: tuple[str, ...],
    reason_code: str,
    missing_reason: str,
) -> V3BenchmarkCheck:
    if not mechanism_available:
        return _unavailable(selector, disabled_reason)
    if not _window_complete(probe, boundary_end_tick):
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code="probe_unavailable",
            evidence=V3BenchmarkEvidenceAvailability.PARTIAL,
            coverage=V3BenchmarkCoverage.EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
        )
    if rows < 1:
        return V3BenchmarkCheck(
            selector_id=selector,
            selector_version=1,
            status=V3BenchmarkCheckStatus.UNEXECUTED,
            reason_code=missing_reason,
            evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
            coverage=V3BenchmarkCoverage.NOT_EXERCISED,
            source_references=(),
            boundary_start_tick=0,
            boundary_end_tick=boundary_end_tick,
            numerator=0,
            denominator=0,
        )
    return V3BenchmarkCheck(
        selector_id=selector,
        selector_version=1,
        status=V3BenchmarkCheckStatus.PASS,
        reason_code=reason_code,
        evidence=V3BenchmarkEvidenceAvailability.COMPLETE,
        coverage=V3BenchmarkCoverage.EXERCISED,
        source_references=_owner_refs(owners),
        boundary_start_tick=0,
        boundary_end_tick=boundary_end_tick,
        numerator=rows,
        denominator=rows,
    )


def _ledger_owners(ledgers: object) -> tuple[str, ...]:
    owners: list[str] = []
    for ledger in ledgers if isinstance(ledgers, (tuple, list)) else ():
        owner = getattr(ledger, "owner_id", None)
        token = getattr(owner, "value", None)
        if isinstance(token, str):
            owners.append(token)
    return tuple(dict.fromkeys(owners))


def _rows(ledgers: object, attribute: str) -> int:
    total = 0
    for ledger in ledgers if isinstance(ledgers, (tuple, list)) else ():
        total += content_count(getattr(ledger, attribute, ()))
    return total


def _concept_rows(ledgers: object) -> int:
    total = 0
    for ledger in ledgers if isinstance(ledgers, (tuple, list)) else ():
        for concept in getattr(ledger, "concepts", ()) or ():
            if int(getattr(concept, "evidence_count", 0) or 0) > 0:
                total += 1
    return total


def evaluate_generational_narratives(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Count variants with retained lineage; a label is not a surviving story."""
    ledgers = getattr(result, "cultural_narrative_ledgers", ()) or ()
    rows = 0
    owners: list[str] = []
    for ledger in ledgers:
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        for variant in getattr(ledger, "variants", ()) or ():
            lineage = (
                bool(getattr(variant, "source_witnesses", ()) or ())
                or bool(getattr(variant, "parent_variant_ids", ()) or ())
                or bool(getattr(variant, "record_refs", ()) or ())
                or bool(getattr(variant, "transitions", ()) or ())
                or bool(getattr(variant, "carrier_agent_ids", ()) or ())
            )
            if lineage:
                rows += 1
                if isinstance(owner, str):
                    owners.append(owner)
    return _history_gate(
        "generational_narrative_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        disabled_reason="generational_narratives_disabled",
        rows=rows,
        owners=tuple(dict.fromkeys(owners)),
        reason_code="narrative_lineage_observed",
        missing_reason="no_narrative_lineage_observed",
    )


def evaluate_institution_concepts(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Measure owner-local pattern evidence; recognition is not required."""
    ledgers = getattr(result, "institution_concept_ledgers", ()) or ()
    return _history_gate(
        "institution_concept_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        disabled_reason="institution_concepts_disabled",
        rows=_concept_rows(ledgers),
        owners=_ledger_owners(ledgers),
        reason_code="institution_concept_evidence_observed",
        missing_reason="no_institution_concept_evidence_observed",
    )


def evaluate_office_succession(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Count owner-local office claims; vacancy and disagreement are legal."""
    ledgers = getattr(result, "office_concept_ledgers", ()) or ()
    rows = _concept_rows(ledgers)
    succession = _rows(ledgers, "succession")
    check = _history_gate(
        "office_succession_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        disabled_reason="office_succession_disabled",
        rows=rows,
        owners=_ledger_owners(ledgers),
        reason_code=(
            "office_succession_observed" if succession > 0 else "office_claims_observed"
        ),
        missing_reason="no_office_claims_observed",
    )
    return check


def evaluate_institutional_memory(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Acquisition requires a visible record or actual delivery, not entry."""
    ledgers = getattr(result, "institutional_memory_ledgers", ()) or ()
    entries = _rows(ledgers, "entries")
    channels = _rows(ledgers, "channels")
    uses = _rows(ledgers, "uses")
    return _history_gate(
        "institutional_memory_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        disabled_reason="institutional_memory_disabled",
        rows=entries + channels + uses,
        owners=_ledger_owners(ledgers),
        reason_code=(
            "institutional_memory_entries_observed"
            if entries > 0
            else "institutional_memory_channels_observed"
        ),
        missing_reason="no_institutional_memory_entries_observed",
    )


def evaluate_institutional_decay(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Measure owner decay updates; collapse is never inferred from absence."""
    ledgers = getattr(result, "institutional_decay_ledgers", ()) or ()
    samples = _rows(ledgers, "samples")
    receipts = _rows(ledgers, "receipts")
    return _history_gate(
        "institutional_decay_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        disabled_reason="institutional_decay_disabled",
        rows=samples + receipts,
        owners=_ledger_owners(ledgers),
        reason_code="decay_updates_observed",
        missing_reason="no_decay_updates_observed",
    )


__all__ = [
    "INSTITUTIONS_BENCHMARK_IDS",
    "build_institutions_benchmark",
    "evaluate_generational_narratives",
    "evaluate_institution_concepts",
    "evaluate_institutional_decay",
    "evaluate_institutional_memory",
    "evaluate_office_succession",
    "institutions_benchmark_arbiter",
    "required_institutions_milestones",
]
