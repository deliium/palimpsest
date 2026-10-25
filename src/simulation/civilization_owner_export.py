"""Detached metadata-only projection of owner ledgers for civilization capture.

The projection deliberately drops private labels, narrative content, evidence
text and full ledger objects. Only qualified identities, closed status values,
ticks, strengths and bounded references cross into the capture lane.
"""

from __future__ import annotations

from typing import Final

from agents.cognition.cultural_features import CulturalFeatureLedger
from agents.cognition.cultural_narratives import NarrativeLedger
from agents.cognition.group_formation import GroupLedger
from agents.cognition.institution_concepts import InstitutionConceptLedger
from agents.cognition.institutional_decay import InstitutionDecayLedger
from agents.cognition.offices import OfficeConceptLedger
from agents.cognition.practical_knowledge import PracticalKnowledgeLedger
from agents.cognition.semantic_naming import TerminologyLedger
from simulation.civilization_capture import (
    CivilizationError,
    CivilizationInventoryChannel,
    CivilizationInventoryCoverage,
    CivilizationOwnerConcept,
    CivilizationOwnerConceptEvidence,
    CivilizationOwnerDecaySample,
    CivilizationOwnerGroup,
    CivilizationOwnerInventory,
    CivilizationOwnerKnowledge,
    CivilizationOwnerOffice,
    CivilizationOwnerTrait,
)
from simulation.civilization_models import (
    CivilizationCoverage,
    CivilizationCoverageState,
)
from simulation.cultural_evidence import (
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES,
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE,
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY,
    CULTURAL_EVIDENCE_COVERAGE_COMPLETE,
    CULTURAL_EVIDENCE_COVERAGE_DISABLED,
    CulturalOwnerExport,
)

__all__ = ["owner_inventory_from_runtime"]

_CULTURAL_CHANNEL_MAP: Final = {
    CULTURAL_EVIDENCE_CHANNEL_CULTURAL_FEATURES: (
        CivilizationInventoryChannel.CULTURAL_FEATURES
    ),
    CULTURAL_EVIDENCE_CHANNEL_TERMINOLOGY: (CivilizationInventoryChannel.TERMINOLOGY),
    CULTURAL_EVIDENCE_CHANNEL_NARRATIVES: CivilizationInventoryChannel.NARRATIVES,
    CULTURAL_EVIDENCE_CHANNEL_PRACTICAL_KNOWLEDGE: (
        CivilizationInventoryChannel.PRACTICAL_KNOWLEDGE
    ),
}


def _coverage(enabled: bool, present: bool) -> CivilizationCoverage:
    if not enabled:
        return CivilizationCoverage(CivilizationCoverageState.DISABLED, "capture_off")
    if not present:
        return CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE, "capture_gap"
        )
    return CivilizationCoverage(CivilizationCoverageState.COMPLETE)


def _cultural_coverage(coverage: str, *, present: bool) -> CivilizationCoverage:
    if coverage == CULTURAL_EVIDENCE_COVERAGE_DISABLED:
        return CivilizationCoverage(CivilizationCoverageState.DISABLED, "capture_off")
    if coverage != CULTURAL_EVIDENCE_COVERAGE_COMPLETE:
        return CivilizationCoverage(
            CivilizationCoverageState.UNAVAILABLE, "capture_gap"
        )
    return CivilizationCoverage(CivilizationCoverageState.COMPLETE)


def _traits(
    ledger: object, *, channel: CivilizationInventoryChannel
) -> tuple[CivilizationOwnerTrait, ...]:
    rows: list[CivilizationOwnerTrait] = []
    if channel is CivilizationInventoryChannel.CULTURAL_FEATURES:
        if type(ledger) is not CulturalFeatureLedger:
            raise CivilizationError()
        for belief in ledger.beliefs:
            rows.append(
                CivilizationOwnerTrait(
                    belief.belief_id,
                    belief.content_fingerprint,
                    belief.acquired_tick,
                    belief.last_updated_tick,
                )
            )
    elif channel is CivilizationInventoryChannel.TERMINOLOGY:
        if type(ledger) is not TerminologyLedger:
            raise CivilizationError()
        for binding in ledger.bindings:
            first = binding.first_tick if binding.first_tick is not None else 0
            last = binding.last_tick if binding.last_tick is not None else first
            rows.append(
                CivilizationOwnerTrait(
                    binding.binding_id,
                    binding.binding_id,
                    first,
                    max(first, last),
                )
            )
    else:
        if type(ledger) is not NarrativeLedger:
            raise CivilizationError()
        for variant in ledger.variants:
            first = variant.first_tick if variant.first_tick is not None else 0
            last = variant.last_tick if variant.last_tick is not None else first
            rows.append(
                CivilizationOwnerTrait(
                    variant.variant_id,
                    variant.content_fingerprint,
                    first,
                    max(first, last),
                )
            )
    return tuple(rows)


def _knowledge(ledger: object) -> tuple[CivilizationOwnerKnowledge, ...]:
    if type(ledger) is not PracticalKnowledgeLedger:
        raise CivilizationError()
    return tuple(
        CivilizationOwnerKnowledge(
            entry.entry_id,
            entry.kind.value,
            entry.content_key,
            entry.origin.value,
            entry.parent_entry_ids,
            entry.lineage_root_id,
            entry.hop_index,
            entry.mutated,
            entry.evidence_refs,
            entry.acquired_tick,
            entry.active,
            entry.capability_anchor,
            (
                entry.source_agent_id.value
                if entry.source_agent_id is not None
                else None
            ),
            (
                entry.teacher_agent_id.value
                if entry.teacher_agent_id is not None
                else None
            ),
        )
        for entry in ledger.entries
    )


def _groups(ledger: object) -> tuple[CivilizationOwnerGroup, ...]:
    if type(ledger) is not GroupLedger:
        raise CivilizationError()
    concept_by_belief = {
        concept.belief_id: concept.concept_id for concept in ledger.concepts
    }
    rows: list[CivilizationOwnerGroup] = []
    for belief in ledger.beliefs:
        rows.append(
            CivilizationOwnerGroup(
                belief.belief_id,
                belief.stance.value,
                tuple(member.value for member in belief.member_ids),
                belief.support,
                belief.social_evidence,
                belief.status.value,
                concept_by_belief.get(belief.belief_id),
            )
        )
    for concept in ledger.concepts:
        if any(row.concept_id == concept.concept_id for row in rows):
            continue
        rows.append(
            CivilizationOwnerGroup(
                concept.belief_id,
                concept.stance.value,
                tuple(member.value for member in concept.member_ids),
                concept.support,
                concept.social_evidence,
                concept.status.value,
                concept.concept_id,
            )
        )
    return tuple(rows)


def _concepts(ledger: object) -> tuple[CivilizationOwnerConcept, ...]:
    if type(ledger) is not InstitutionConceptLedger:
        raise CivilizationError()
    rows: list[CivilizationOwnerConcept] = []
    for concept in ledger.concepts:
        rows.append(
            CivilizationOwnerConcept(
                concept.concept_id,
                concept.status.value,
                concept.conceptualization.value,
                concept.evidence_count,
                concept.first_tick,
                concept.last_tick,
                tuple(
                    CivilizationOwnerConceptEvidence(
                        evidence.evidence_id,
                        evidence.tick,
                        evidence.channel.value,
                        evidence.pattern.value,
                        evidence.lineage_ref,
                        (
                            evidence.actor_id.value
                            if evidence.actor_id is not None
                            else None
                        ),
                    )
                    for evidence in concept.evidence
                ),
            )
        )
    return tuple(rows)


def _offices(ledger: object) -> tuple[CivilizationOwnerOffice, ...]:
    if type(ledger) is not OfficeConceptLedger:
        raise CivilizationError()
    return tuple(
        CivilizationOwnerOffice(
            concept.office_id,
            concept.status.value,
            concept.function.value,
            concept.first_tick,
            concept.last_tick,
            concept.recognized,
            ledger.coverage,
        )
        for concept in ledger.concepts
    )


def _decay(ledger: object) -> tuple[CivilizationOwnerDecaySample, ...]:
    if type(ledger) is not InstitutionDecayLedger:
        raise CivilizationError()
    bindings = {binding.local_pattern_id: binding for binding in ledger.bindings}
    rows: list[CivilizationOwnerDecaySample] = []
    for sample in ledger.samples:
        binding = bindings.get(sample.local_pattern_id)
        if binding is None:
            raise CivilizationError()
        rows.append(
            CivilizationOwnerDecaySample(
                sample.local_pattern_id,
                binding.group_key,
                binding.concept_id,
                binding.inception_tick,
                sample.observation_tick,
                sample.source_first_tick,
                sample.source_last_tick,
                sample.role_recognition,
                sample.procedure_recurrence,
                sample.social_expectation,
                sample.legitimacy_belief,
                sample.succession_observed,
                sample.generational_continuity,
                sample.recognized,
                sample.covered,
                sample.pruned,
                sample.anchor_digests,
                sample.structural_components,
                sample.context_key,
                sample.office_id,
                tuple(agent.value for agent in sample.evidence.observed_cohort),
                tuple(
                    (agent.value, root) for agent, root in sample.evidence.supporters
                ),
                tuple(
                    (agent.value, key)
                    for agent, key in sample.evidence.participant_actions
                ),
                sample.evidence.performed_procedure_keys,
                sample.evidence.succession_transitions,
                sample.evidence.completed_transitions,
            )
        )
    return tuple(rows)


def owner_inventory_from_runtime(
    cultural: CulturalOwnerExport,
    *,
    groups: object | None,
    groups_enabled: bool,
    concepts: object | None,
    concepts_enabled: bool,
    offices: object | None,
    offices_enabled: bool,
    decay: object | None,
    decay_enabled: bool,
) -> CivilizationOwnerInventory:
    """Project one owner's ledgers without retaining labels or raw content."""
    if type(cultural) is not CulturalOwnerExport:
        raise CivilizationError()
    by_channel = {row.channel: row for row in cultural.channels}
    channels: list[CivilizationInventoryCoverage] = []
    cultural_traits: tuple[CivilizationOwnerTrait, ...] = ()
    terminology: tuple[CivilizationOwnerTrait, ...] = ()
    narratives: tuple[CivilizationOwnerTrait, ...] = ()
    knowledge: tuple[CivilizationOwnerKnowledge, ...] = ()
    for channel, inventory_channel in _CULTURAL_CHANNEL_MAP.items():
        export = by_channel[channel]
        coverage = _cultural_coverage(
            export.coverage, present=export.ledger is not None
        )
        channels.append(CivilizationInventoryCoverage(inventory_channel, coverage))
        if coverage.state is not CivilizationCoverageState.COMPLETE:
            continue
        if export.ledger is None:
            continue
        if inventory_channel is CivilizationInventoryChannel.CULTURAL_FEATURES:
            cultural_traits = _traits(export.ledger, channel=inventory_channel)
        elif inventory_channel is CivilizationInventoryChannel.TERMINOLOGY:
            terminology = _traits(export.ledger, channel=inventory_channel)
        elif inventory_channel is CivilizationInventoryChannel.NARRATIVES:
            narratives = _traits(export.ledger, channel=inventory_channel)
        else:
            knowledge = _knowledge(export.ledger)
    channels.append(
        CivilizationInventoryCoverage(
            CivilizationInventoryChannel.GROUPS,
            _coverage(groups_enabled, groups is not None),
        )
    )
    channels.append(
        CivilizationInventoryCoverage(
            CivilizationInventoryChannel.INSTITUTION_CONCEPTS,
            _coverage(concepts_enabled, concepts is not None),
        )
    )
    channels.append(
        CivilizationInventoryCoverage(
            CivilizationInventoryChannel.OFFICES,
            _coverage(offices_enabled, offices is not None),
        )
    )
    channels.append(
        CivilizationInventoryCoverage(
            CivilizationInventoryChannel.INSTITUTIONAL_DECAY,
            _coverage(decay_enabled, decay is not None),
        )
    )
    return CivilizationOwnerInventory(
        cultural.owner_id.value,
        cultural.generation_index,
        cultural.living,
        tuple(channels),
        cultural_traits,
        terminology,
        narratives,
        knowledge,
        _groups(groups) if groups is not None else (),
        _concepts(concepts) if concepts is not None else (),
        _offices(offices) if offices is not None else (),
        _decay(decay) if decay is not None else (),
    )
