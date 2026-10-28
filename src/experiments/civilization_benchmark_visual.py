"""Bounded visual integration fixture for the release acceptance workflow.

This fixture is outside the 30-case research registry. Task 17 owns the
controlled opportunity schedule and the eight visual markers; this module only
materializes the same six-founder visual world under a stable recipe identity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from agents.models import AgentId
from experiments.civilization_benchmark_base import (
    V3BenchmarkBase,
    build_v3_benchmark_base,
)
from experiments.civilization_benchmark_evidence import BenchmarkBoundaryProbe
from experiments.civilization_benchmark_models import (
    V3_VISUAL_BENCHMARK_ID,
    V3BenchmarkProfile,
)
from experiments.civilization_benchmark_suite import V3_BENCH_01_BLANK_SLATE
from experiments.interventions import (
    MilestoneInterventionArbiter,
    MilestoneOverride,
)
from simulation.runner_models import SimulationRunnerConfig
from world.actions import Move, StartCollectiveProject, Talk, Wait
from world.communications import (
    CommunicationRelation,
    CommunicationSourceBasis,
    origin_utterance,
)
from world.identifiers import EntityId, require_stable_id
from world.values import DayPhase

VISUAL_BENCHMARK_RECIPE_ID: Final[str] = V3_VISUAL_BENCHMARK_ID


def build_v3_visual_benchmark(*, seed: int = 23) -> V3BenchmarkBase:
    """Materialize the bounded visual world (not a research case)."""
    return build_v3_benchmark_base(
        seed=seed,
        profile=V3BenchmarkProfile.VISUAL,
        scenario_id=V3_BENCH_01_BLANK_SLATE,
    )


__all__ = [
    "VISUAL_BENCHMARK_RECIPE_ID",
    "VisualAcceptanceMarker",
    "VisualMarkerKind",
    "VisualMarkerStatus",
    "build_v3_visual_benchmark",
    "build_v3_visual_fixture",
    "build_visual_marker_manifest",
    "require_all_visual_markers",
    "visual_fixture_arbiter",
]


class VisualMarkerKind(StrEnum):
    """Eight requested visualization phenomena, never a research finding."""

    NEW_AGENTS = "new_agents"
    DEATHS = "deaths"
    MIGRATION = "migration"
    TEACHING = "teaching"
    COLLECTIVE_PROJECT = "collective_project"
    TECHNOLOGY_SPREAD = "technology_spread"
    CULTURAL_DIFFERENTIATION = "cultural_differentiation"
    OFFICE_SUCCESSION = "office_succession"


class VisualMarkerStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class VisualAcceptanceMarker:
    """Source-pinned marker for one presentation test; never simulation input."""

    kind: VisualMarkerKind
    status: VisualMarkerStatus
    tick: int | None = None
    reference_id: str | None = None
    owner_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.kind) is not VisualMarkerKind:
            raise TypeError("kind must be VisualMarkerKind")
        if type(self.status) is not VisualMarkerStatus:
            raise TypeError("status must be VisualMarkerStatus")
        if self.tick is not None and (type(self.tick) is not int or self.tick < 0):
            raise ValueError("tick must be a non-negative int or None")
        if self.reference_id is not None:
            require_stable_id("reference_id", self.reference_id)
        if any(not item or not item.strip() for item in self.owner_ids):
            raise ValueError("owner_ids entries must be non-blank")


def build_visual_marker_manifest(
    probe: BenchmarkBoundaryProbe,
    result: object,
    *,
    office_succession_receipts: tuple[str, ...] = (),
) -> tuple[VisualAcceptanceMarker, ...]:
    """Select markers from actual evidence; missing channels stay unavailable."""
    observations = probe.observations
    last_tick = observations[-1].boundary_tick if observations else None
    owners = observations[-1].owners if observations else ()
    owners = tuple(owners)
    owner_ids = tuple(owner.owner_id for owner in owners)
    stamps: list[VisualAcceptanceMarker] = []

    admissions = tuple(
        observation.boundary_tick
        for observation in observations
        if observation.new_owners
    )
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.NEW_AGENTS,
            status=(
                VisualMarkerStatus.AVAILABLE
                if admissions
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=admissions[0] if admissions else None,
            reference_id="boundary:new-owner" if admissions else None,
            owner_ids=owner_ids if admissions else (),
        )
    )
    deaths = probe.death_ticks_by_body
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.DEATHS,
            status=(
                VisualMarkerStatus.AVAILABLE
                if deaths
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=deaths[0][1] if deaths else None,
            reference_id="event-kind:Died" if deaths else None,
        )
    )

    def _event_marker(
        kind: VisualMarkerKind, event_kinds: tuple[str, ...]
    ) -> VisualAcceptanceMarker:
        totals = tuple((name, probe.event_total(name)) for name in event_kinds)
        if any(count > 0 for _, count in totals):
            return VisualAcceptanceMarker(
                kind=kind,
                status=VisualMarkerStatus.AVAILABLE,
                tick=last_tick,
                reference_id=f"event-kind:{event_kinds[0]}",
                owner_ids=owner_ids,
            )
        return VisualAcceptanceMarker(kind=kind, status=VisualMarkerStatus.UNAVAILABLE)

    stamps.append(
        _event_marker(VisualMarkerKind.MIGRATION, ("JourneyStarted", "JourneyArrived"))
    )
    stamps.append(
        _event_marker(
            VisualMarkerKind.COLLECTIVE_PROJECT,
            ("ProjectCreated", "ProjectContributed"),
        )
    )
    result_teaching = tuple(getattr(result, "teaching_audits", ()) or ())
    taught = sum(
        owner.teaching_audits + owner.mentorship_audits for owner in owners
    ) + len(result_teaching)
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.TEACHING,
            status=(
                VisualMarkerStatus.AVAILABLE
                if taught > 0
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id="owner:teaching-audits" if taught else None,
            owner_ids=owner_ids if taught else (),
        )
    )
    skill_audits = tuple(getattr(result, "skill_audits", ()) or ())
    practical_audits = tuple(getattr(result, "practical_knowledge_audits", ()) or ())
    knowledge = (
        sum(int(owner.count("practical_knowledge") or 0) for owner in owners)
        + len(skill_audits)
        + len(practical_audits)
    )
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.TECHNOLOGY_SPREAD,
            status=(
                VisualMarkerStatus.AVAILABLE
                if knowledge > 0
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id="owner:practical-knowledge" if knowledge else None,
            owner_ids=owner_ids if knowledge else (),
        )
    )
    cultural_owners = tuple(
        owner.owner_id
        for owner in owners
        if owner.cultural_audits > 0 or int(owner.count("cultural_features") or 0) > 0
    )
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.CULTURAL_DIFFERENTIATION,
            status=(
                VisualMarkerStatus.AVAILABLE
                if len(cultural_owners) >= 2
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id=(
                "owner:cultural-audits" if len(cultural_owners) >= 2 else None
            ),
            owner_ids=cultural_owners,
        )
    )
    succession = 0
    office_owners: list[str] = []
    for ledger in getattr(result, "office_concept_ledgers", ()) or ():
        owner = getattr(getattr(ledger, "owner_id", None), "value", None)
        for concept in getattr(ledger, "concepts", ()) or ():
            count = len(getattr(concept, "succession", ()) or ())
            if count > 0:
                succession += count
                if isinstance(owner, str):
                    office_owners.append(owner)
    receipt_reference = (
        office_succession_receipts[0] if office_succession_receipts else None
    )
    succession_available = succession > 0 or receipt_reference is not None
    stamps.append(
        VisualAcceptanceMarker(
            kind=VisualMarkerKind.OFFICE_SUCCESSION,
            status=(
                VisualMarkerStatus.AVAILABLE
                if succession_available
                else VisualMarkerStatus.UNAVAILABLE
            ),
            tick=last_tick,
            reference_id=(
                "owner:office-succession" if succession > 0 else receipt_reference
            ),
            owner_ids=tuple(dict.fromkeys(office_owners)),
        )
    )
    return tuple(stamps)


def require_all_visual_markers(
    markers: tuple[VisualAcceptanceMarker, ...],
) -> tuple[str, ...]:
    """Return missing marker kinds; the caller fails its coverage gate."""
    missing = tuple(
        marker.kind.value
        for marker in markers
        if marker.status is VisualMarkerStatus.UNAVAILABLE
    )
    return missing


def build_v3_visual_fixture(*, seed: int = 23) -> V3BenchmarkBase:
    """Controlled visual world with the prerequisites for all eight markers."""
    from dataclasses import replace

    from experiments.civilization_benchmark_technology import (
        _experimentation,
        _with_material_opportunities,
    )
    from simulation.new_agent_initialization import (
        SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
        default_new_agent_initialization_spec,
    )
    from simulation.runner_models import (
        ArtifactInterpretationMode,
        InstitutionConceptMode,
        OfficeSuccessionMode,
        example_collective_projects_spec,
        example_developmental_learning_spec,
        example_knowledge_genealogy_spec,
        example_mentorship_spec,
        example_technique_lifecycle_spec,
    )
    from world.production import example_production_catalog

    base = build_v3_visual_benchmark(seed=seed)
    catalog = example_production_catalog()
    agents = tuple(
        replace(
            agent,
            cognition=replace(
                agent.cognition,
                artifact_interpretation_mode=ArtifactInterpretationMode.DETERMINISTIC,
                institution_concept_mode=InstitutionConceptMode.DETERMINISTIC,
                office_succession_mode=OfficeSuccessionMode.DETERMINISTIC,
                production_catalog=catalog,
            ),
        )
        for agent in base.config.agents
    )
    config = _with_material_opportunities(
        replace(base.config, agents=agents), held_body_ids=("body-origin",)
    )
    config = replace(
        config,
        agents=agents,
        new_agent_initialization=replace(
            default_new_agent_initialization_spec(),
            species_defaults_id=SPECIES_DEFAULT_CIVILIZATION_LEARNER_V1,
        ),
        developmental_learning=example_developmental_learning_spec(),
        mentorship=example_mentorship_spec(),
        knowledge_genealogy=example_knowledge_genealogy_spec(),
        technique_lifecycle=example_technique_lifecycle_spec(),
        bounded_experimentation=_experimentation(),
        collective_projects=example_collective_projects_spec(),
    )
    return replace(
        base,
        config=config,
        founder_ids=tuple(agent.agent_id.value for agent in config.agents),
    )


def visual_fixture_arbiter(
    config: SimulationRunnerConfig,
) -> MilestoneInterventionArbiter:
    """Sparse ordinary-command opportunities; no ledger is seeded."""
    horizon = config.stop_policy.max_ticks or 160
    days = tuple(
        tick
        for tick in range(horizon)
        if config.resolve_physical_rules().day_phase_for_tick(tick) is DayPhase.DAY
    ) or (0,)
    milestones: list[MilestoneOverride] = [
        MilestoneOverride(
            milestone_id="v3-visual-project-start",
            tick=0,
            agent_id=AgentId("agent-origin"),
            build_command=lambda: StartCollectiveProject(project_kind="shared_shelter"),
        ),
        MilestoneOverride(
            milestone_id="v3-visual-journey",
            tick=days[0] + 2,
            agent_id=AgentId("agent-origin"),
            build_command=lambda: Move(EntityId("loc-spring")),
        ),
    ]
    from experiments.civilization_benchmark_technology import _experiment_command

    milestones.append(
        MilestoneOverride(
            milestone_id="v3-visual-experiment",
            tick=2,
            agent_id=AgentId("agent-origin"),
            build_command=_experiment_command,
        )
    )
    milestones.append(
        MilestoneOverride(
            milestone_id="v3-visual-teach",
            tick=3,
            agent_id=AgentId("agent-origin"),
            build_command=_teach_command(3, "body-origin", "body-extra-1"),
        )
    )
    if len(days) > 2:
        milestones.append(
            MilestoneOverride(
                milestone_id="v3-visual-succession",
                tick=days[1],
                agent_id=AgentId("agent-extra-2"),
                build_command=_succession_command(
                    days[1], "body-extra-2", "body-origin", "body-extra-1"
                ),
            )
        )
    for index, day in enumerate(days[:6]):
        milestones.append(
            MilestoneOverride(
                milestone_id=f"v3-visual-endorse-{index}",
                tick=day,
                agent_id=AgentId("agent-extra-1"),
                build_command=_endorse_command(day, "body-extra-1", "body-origin"),
            )
        )
    occupied = {(item.tick, item.agent_id.value) for item in milestones}
    hold_until = days[1] if len(days) > 1 else days[0]
    for tick in range(hold_until):
        for agent_id in ("agent-origin", "agent-extra-1", "agent-extra-2"):
            if (tick, agent_id) in occupied:
                continue
            milestones.append(
                MilestoneOverride(
                    milestone_id=f"v3-visual-hold-{agent_id}-{tick}",
                    tick=tick,
                    agent_id=AgentId(agent_id),
                    build_command=lambda: Wait(),
                )
            )
    occupied = {(item.tick, item.agent_id.value) for item in milestones}
    for tick in range(days[1]):
        for agent_id in ("agent-origin", "agent-extra-2"):
            if (tick, agent_id) in occupied:
                continue
            milestones.append(
                MilestoneOverride(
                    milestone_id=f"v3-visual-hold-{agent_id}-{tick}",
                    tick=tick,
                    agent_id=AgentId(agent_id),
                    build_command=lambda: Wait(),
                )
            )
    if len(days) > 1:
        milestones.append(
            MilestoneOverride(
                milestone_id="v3-visual-hold-origin-succession",
                tick=days[1],
                agent_id=AgentId("agent-origin"),
                build_command=lambda: Wait(),
            )
        )
    milestones.sort(key=lambda item: (item.tick, item.agent_id.value))
    return MilestoneInterventionArbiter(
        tuple(milestones), override_budget=len(milestones)
    )


def _endorse_command(tick: int, speaker: str, occupant: str) -> Callable[[], Talk]:
    def build() -> Talk:
        return Talk(
            recipient_id=EntityId("body-origin"),
            utterance=origin_utterance(
                speaker_id=EntityId(speaker),
                communication_id=f"v3-visual-endorse-{tick}",
                text="endorse",
                sender_confidence=0.7,
                relations=(
                    CommunicationRelation(
                        subject="collective_project",
                        predicate="office_endorse",
                        object=f"fedcba9876543210|{occupant}|-",
                    ),
                ),
                source_basis=CommunicationSourceBasis.UNREFERENCED,
            ),
        )

    return build


def _teach_command(tick: int, speaker: str, recipient: str) -> Callable[[], Talk]:
    def build() -> Talk:
        return Talk(
            recipient_id=EntityId(recipient),
            utterance=origin_utterance(
                speaker_id=EntityId(speaker),
                communication_id=f"v3-visual-teach-{tick}",
                text="explain",
                sender_confidence=0.8,
                concepts=("crafting",),
                relations=(
                    CommunicationRelation(
                        subject="crafting",
                        predicate="explain",
                        object="crafting:high",
                    ),
                ),
                source_basis=CommunicationSourceBasis.UNREFERENCED,
            ),
        )

    return build


def _succession_command(
    tick: int, speaker: str, recipient: str, successor: str
) -> Callable[[], Talk]:
    def build() -> Talk:
        return Talk(
            recipient_id=EntityId(recipient),
            utterance=origin_utterance(
                speaker_id=EntityId(speaker),
                communication_id=f"v3-visual-succession-{tick}",
                text="succession",
                sender_confidence=0.7,
                relations=(
                    CommunicationRelation(
                        subject="collective_project",
                        predicate="office_succession",
                        object=f"fedcba9876543210|{successor}|-",
                    ),
                ),
                source_basis=CommunicationSourceBasis.BELIEF,
            ),
        )

    return build
