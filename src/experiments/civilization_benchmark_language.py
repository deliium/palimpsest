"""Bounded v55 compositions for benchmark cases 21-23 (symbols and meaning).

Owner-local vocabularies, sense histories and translation hypotheses are
measured as subjective evidence. No world dictionary, shared language pack or
truth correction exists.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Final

from agents.models import AgentId
from analysis.semantic_drift_metrics import semantic_sense_rows_from_ledgers
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
    V3_BENCH_21_VOCABULARY_DIVERGENCE,
    V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT,
    V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION,
)
from experiments.composition import symbolic_analysis_inputs_from_harvest
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
    SemanticNamingMode,
    SimulationRunnerConfig,
    SkillLearningMode,
    SymbolicLanguageMode,
    TeachingInteractionMode,
    TranslationMode,
)
from world.actions import Talk, Wait
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
    "experiments.civilization_benchmark_language"
)

LANGUAGE_BENCHMARK_IDS: Final[tuple[str, ...]] = (
    V3_BENCH_21_VOCABULARY_DIVERGENCE,
    V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT,
    V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION,
)

_ORIGIN_AGENT_ID: Final[str] = "agent-origin"
_ORIGIN_BODY_ID: Final[str] = "body-origin"
_EXTRA_1_AGENT_ID: Final[str] = "agent-extra-1"
_EXTRA_1_BODY_ID: Final[str] = "body-extra-1"
_GRAIN_AGENT_ID: Final[str] = "agent-grain"
_GRAIN_BODY_ID: Final[str] = "body-grain"
_EXTRA_2_AGENT_ID: Final[str] = "agent-extra-2"
_EXTRA_2_BODY_ID: Final[str] = "body-extra-2"


def _learner_initializer() -> NewAgentInitializationSpec:
    return replace(
        default_new_agent_initialization_spec(),
        species_defaults_id=SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
    )


def _cognition(agent_id: AgentId, *, translation: bool) -> AgentCognitionSpec:
    return AgentCognitionSpec(
        agent_id=agent_id,
        skill_learning_mode=SkillLearningMode.DETERMINISTIC,
        teaching_interaction_mode=TeachingInteractionMode.DETERMINISTIC,
        communication_strategy_mode=CommunicationStrategyMode.DETERMINISTIC,
        semantic_naming_mode=SemanticNamingMode.DETERMINISTIC,
        symbolic_language_mode=SymbolicLanguageMode.DETERMINISTIC,
        translation_mode=(
            TranslationMode.DETERMINISTIC if translation else TranslationMode.DISABLED
        ),
        cultural_narrative_mode=CulturalNarrativeMode.DETERMINISTIC,
        artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
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


def _with_symbolic_owners(
    config: SimulationRunnerConfig, *, translation: bool
) -> SimulationRunnerConfig:
    scenario = config.scenario
    bodies = list(scenario.bodies)
    existing = {body.entity_id.value for body in bodies}
    for body_id, location_id in (
        (_EXTRA_1_BODY_ID, "loc-origin"),
        (_EXTRA_2_BODY_ID, "loc-grain"),
    ):
        if body_id not in existing:
            bodies.append(_extra_body(body_id, location_id))
    agents = tuple(
        replace(agent, cognition=_cognition(agent.agent_id, translation=translation))
        for agent in config.agents
    ) + tuple(
        AgentRunnerSpec(
            agent_id=AgentId(agent_id),
            entity_id=EntityId(body_id),
            cognition=_cognition(AgentId(agent_id), translation=translation),
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


def build_language_benchmark(
    scenario_id: str,
    *,
    seed: int | None = None,
    profile: V3BenchmarkProfile = V3BenchmarkProfile.SMOKE,
    lane: V3BenchmarkLane = V3BenchmarkLane.RESEARCH,
) -> V3BenchmarkScenarioBuild:
    """Materialize one Phase 5 symbolic/semantic/translation case."""
    if scenario_id not in LANGUAGE_BENCHMARK_IDS:
        raise V3BenchmarkError(
            "unknown_scenario", f"not a language benchmark: {scenario_id!r}"
        )
    build = build_v3_benchmark_scenario(
        scenario_id, seed=seed, profile=profile, lane=lane
    )
    base = _with_symbolic_owners(
        build.arms[0].config,
        translation=scenario_id == V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION,
    )
    founder_ids = tuple(agent.agent_id.value for agent in base.agents)
    arms = tuple(
        replace(arm, config=base, founder_ids=founder_ids) for arm in build.arms
    )
    result = replace(build, arms=arms)
    _LOG.debug(
        "language_benchmark_built scenario_id=%s lane=%s profile=%s owners=%s",
        scenario_id,
        lane.value,
        profile.value,
        len(base.agents),
    )
    return result


def _call(
    *,
    tick: int,
    speaker_body: str,
    recipient_body: str,
    token: str,
    kind: str = "location",
    predicate: str = "call",
) -> Talk:
    return Talk(
        recipient_id=EntityId(recipient_body),
        utterance=origin_utterance(
            speaker_id=EntityId(speaker_body),
            communication_id=f"v3-bench-call-{speaker_body}-{tick}",
            text="call",
            sender_confidence=0.7,
            relations=(
                CommunicationRelation(subject=token, predicate=predicate, object=kind),
            ),
            source_basis=CommunicationSourceBasis.UNREFERENCED,
        ),
    )


def _call_factory(
    tick: int,
    speaker_body: str,
    recipient_body: str,
    token: str,
    *,
    kind: str = "location",
    predicate: str = "call",
) -> Callable[[], Talk]:
    def build() -> Talk:
        return _call(
            tick=tick,
            speaker_body=speaker_body,
            recipient_body=recipient_body,
            token=token,
            kind=kind,
            predicate=predicate,
        )

    return build


def language_benchmark_arbiter(
    scenario_id: str, config: SimulationRunnerConfig
) -> MilestoneInterventionArbiter | None:
    """Exchange bounded call relations; no label or meaning is installed."""
    if scenario_id not in LANGUAGE_BENCHMARK_IDS:
        return None
    horizon = config.stop_policy.max_ticks or 8
    rules = config.scenario.physical_rules
    day_ticks = [
        tick
        for tick in range(horizon)
        if rules.day_phase_for_tick(tick) is DayPhase.DAY
    ][:5]
    milestones: list[MilestoneOverride] = []
    origin = AgentId(_ORIGIN_AGENT_ID)
    extra_one = AgentId(_EXTRA_1_AGENT_ID)
    grain = AgentId(_GRAIN_AGENT_ID)
    for tick in day_ticks:
        milestones.append(
            MilestoneOverride(
                milestone_id=f"v3-bench-call-origin-{tick:04d}",
                tick=tick,
                agent_id=origin,
                build_command=_call_factory(
                    tick,
                    _ORIGIN_BODY_ID,
                    _EXTRA_1_BODY_ID,
                    "north_place",
                    kind="shared_place",
                    predicate=(
                        "attributive"
                        if scenario_id != V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION
                        else "call"
                    ),
                ),
            )
        )
        milestones.append(
            MilestoneOverride(
                milestone_id=f"v3-bench-call-grain-{tick:04d}",
                tick=tick,
                agent_id=grain,
                build_command=_call_factory(
                    tick,
                    _GRAIN_BODY_ID,
                    _EXTRA_2_BODY_ID,
                    "dry_place",
                    kind="shared_place",
                    predicate=(
                        "attributive"
                        if scenario_id != V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION
                        else "call"
                    ),
                ),
            )
        )
    if scenario_id == V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION:
        for tick in day_ticks[1:]:
            milestones.append(
                MilestoneOverride(
                    milestone_id=f"v3-bench-call-foreign-{tick:04d}",
                    tick=tick,
                    agent_id=extra_one,
                    build_command=_call_factory(
                        tick,
                        _EXTRA_1_BODY_ID,
                        _ORIGIN_BODY_ID,
                        "foreign_form",
                    ),
                )
            )
    occupied = {(item.tick, item.agent_id.value) for item in milestones}
    for tick in range(horizon):
        for agent_id in (
            _ORIGIN_AGENT_ID,
            _EXTRA_1_AGENT_ID,
            _GRAIN_AGENT_ID,
            _EXTRA_2_AGENT_ID,
        ):
            if (tick, agent_id) in occupied:
                continue
            milestones.append(
                MilestoneOverride(
                    milestone_id=f"v3-bench-hold-{agent_id}-{tick:04d}",
                    tick=tick,
                    agent_id=AgentId(agent_id),
                    build_command=lambda: Wait(),
                )
            )
    milestones.sort(key=lambda item: (item.tick, item.agent_id.value))
    _LOG.debug(
        "language_arbiter_ready scenario_id=%s milestone_count=%s",
        scenario_id,
        len(milestones),
    )
    return MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )


def required_language_milestones(
    scenario_id: str, config: SimulationRunnerConfig
) -> tuple[str, ...]:
    horizon = config.stop_policy.max_ticks or 8
    rules = config.scenario.physical_rules
    day_ticks = [
        tick
        for tick in range(horizon)
        if rules.day_phase_for_tick(tick) is DayPhase.DAY
    ]
    if scenario_id == V3_BENCH_21_VOCABULARY_DIVERGENCE:
        return tuple(f"v3-bench-call-origin-{tick:04d}" for tick in day_ticks[:1])
    if scenario_id == V3_BENCH_22_GENERATIONAL_SEMANTIC_DRIFT:
        return tuple(f"v3-bench-call-origin-{tick:04d}" for tick in day_ticks[:2])
    if scenario_id == V3_BENCH_23_CROSS_CULTURAL_MISTRANSLATION:
        return (
            *(f"v3-bench-call-origin-{tick:04d}" for tick in day_ticks[:1]),
            *(f"v3-bench-call-foreign-{tick:04d}" for tick in day_ticks[3:4]),
        )
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
    rows: int,
    owners: tuple[str, ...],
    reason_code: str,
    missing_reason: str,
) -> V3BenchmarkCheck:
    if not mechanism_available:
        return _unavailable(selector, f"{selector}_disabled")
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


def evaluate_symbolic_language(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Measure owner-local compositions; resemblance is never identity."""
    ledgers = getattr(result, "symbolic_ledgers", ()) or ()
    inputs = symbolic_analysis_inputs_from_harvest(ledgers=ledgers)
    rows = len(inputs.compositions) + len(inputs.interpretations)
    return _history_gate(
        "symbolic_language_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        rows=rows,
        owners=_ledger_owners(ledgers),
        reason_code=(
            "symbolic_compositions_observed"
            if inputs.compositions
            else "symbolic_interpretations_observed"
        ),
        missing_reason="no_symbolic_evidence_observed",
    )


def evaluate_semantic_drift(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Require retained sense history; a label change alone is not drift."""
    naming = getattr(result, "terminology_ledgers", ()) or ()
    symbolic = getattr(result, "symbolic_ledgers", ()) or ()
    rows = semantic_sense_rows_from_ledgers(
        naming_ledgers=naming, symbolic_ledgers=symbolic
    )
    return _history_gate(
        "semantic_drift_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        rows=len(rows),
        owners=tuple(
            dict.fromkeys([*_ledger_owners(naming), *_ledger_owners(symbolic)])
        ),
        reason_code="sense_history_observed",
        missing_reason="no_sense_history_observed",
    )


def evaluate_translation(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    boundary_end_tick: int,
    mechanism_available: bool,
) -> V3BenchmarkCheck:
    """Count owner-local translation hypotheses; confidence is not truth."""
    ledgers = getattr(result, "translation_ledgers", ()) or ()
    rows = sum(content_count(ledger) for ledger in ledgers) if ledgers else 0
    return _history_gate(
        "translation_evidence",
        probe,
        boundary_end_tick=boundary_end_tick,
        mechanism_available=mechanism_available,
        rows=rows,
        owners=_ledger_owners(ledgers),
        reason_code="translation_hypotheses_observed",
        missing_reason="no_translation_hypothesis_observed",
    )


__all__ = [
    "LANGUAGE_BENCHMARK_IDS",
    "build_language_benchmark",
    "evaluate_semantic_drift",
    "evaluate_symbolic_language",
    "evaluate_translation",
    "language_benchmark_arbiter",
    "required_language_milestones",
]
