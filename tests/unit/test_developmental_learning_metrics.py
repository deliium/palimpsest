"""Developmental learning analysis metric families (+3)."""

from __future__ import annotations

from agents.cognition.developmental_learning import (
    DevelopmentalAcquisitionAudit,
    DevelopmentalDomainId,
    DevelopmentalKnowledgeEntry,
    DevelopmentalSourceId,
    empty_developmental_knowledge_ledger,
    upsert_developmental_entry,
)
from agents.models import AgentId
from analysis.developmental_learning_metrics import (
    DEVELOPMENTAL_ACQUISITION_METRIC_VERSION,
    DEVELOPMENTAL_DIVERGENCE_METRIC_VERSION,
    DEVELOPMENTAL_SOURCE_MIX_METRIC_VERSION,
    compute_developmental_acquisition,
    compute_developmental_divergence,
    compute_developmental_source_mix,
)
from analysis.models import MetricAvailability
from analysis.specifications import (
    METRIC_FAMILY_COUNT,
    MetricFamilyId,
    all_metric_specifications,
    validate_metric_catalog,
)


def test_catalog_includes_three_developmental_families() -> None:
    specs = validate_metric_catalog()
    assert len(specs) == METRIC_FAMILY_COUNT == 47
    assert frozenset(spec.family_id for spec in specs) == frozenset(MetricFamilyId)
    ids = {spec.family_id for spec in all_metric_specifications()}
    assert MetricFamilyId.DEVELOPMENTAL_ACQUISITION in ids
    assert MetricFamilyId.DEVELOPMENTAL_SOURCE_MIX in ids
    assert MetricFamilyId.DEVELOPMENTAL_DIVERGENCE in ids


def _audit(
    *,
    owner: str,
    domain: DevelopmentalDomainId,
    source: DevelopmentalSourceId,
    tick: int,
    acquired: bool = True,
    teacher: AgentId | None = None,
) -> DevelopmentalAcquisitionAudit:
    return DevelopmentalAcquisitionAudit(
        owner_id=AgentId(owner),
        domain_id=domain,
        source_id=source,
        tick=tick,
        acquired=acquired,
        confidence_band="mid" if acquired else "none",
        reason_code="acquired" if acquired else "rate_zero",
        teacher_present=teacher is not None,
        teacher_agent_id=teacher,
    )


def test_compute_acquisition_and_source_mix() -> None:
    audits = (
        _audit(
            owner="a",
            domain=DevelopmentalDomainId.LOCATIONS,
            source=DevelopmentalSourceId.OBSERVATION,
            tick=1,
        ),
        _audit(
            owner="a",
            domain=DevelopmentalDomainId.SKILLS,
            source=DevelopmentalSourceId.INSTRUCTION,
            tick=2,
            teacher=AgentId("teacher"),
        ),
        _audit(
            owner="b",
            domain=DevelopmentalDomainId.RESOURCES,
            source=DevelopmentalSourceId.OBSERVATION,
            tick=1,
        ),
    )
    acq = compute_developmental_acquisition(
        audits, run_id="run-dev-1", input_revision="rev-1"
    )
    assert acq.availability is MetricAvailability.PRESENT
    assert acq.algorithm_version == "1"
    assert acq.metric_family == "developmental_acquisition"
    assert DEVELOPMENTAL_ACQUISITION_METRIC_VERSION == "developmental_acquisition@1"
    assert acq.values["agent_count"] == 2
    mix = compute_developmental_source_mix(
        audits, run_id="run-dev-1", input_revision="rev-1"
    )
    assert mix.availability is MetricAvailability.PRESENT
    assert DEVELOPMENTAL_SOURCE_MIX_METRIC_VERSION.endswith("@1")
    assert mix.values["teacher_present_count"] == 1


def test_compute_divergence() -> None:
    a = empty_developmental_knowledge_ledger(AgentId("a"))
    b = empty_developmental_knowledge_ledger(AgentId("b"))
    a = upsert_developmental_entry(
        a,
        DevelopmentalKnowledgeEntry(
            domain_id=DevelopmentalDomainId.LOCATIONS,
            concept_key="loc:alpha",
            source_id=DevelopmentalSourceId.OBSERVATION,
            confidence=0.5,
            acquired_tick=1,
            evidence_refs=("evt:1",),
        ),
    )
    b = upsert_developmental_entry(
        b,
        DevelopmentalKnowledgeEntry(
            domain_id=DevelopmentalDomainId.LOCATIONS,
            concept_key="loc:beta",
            source_id=DevelopmentalSourceId.OBSERVATION,
            confidence=0.5,
            acquired_tick=1,
            evidence_refs=("evt:2",),
        ),
    )
    doc = compute_developmental_divergence(
        (a, b), run_id="run-dev-2", input_revision="rev-2"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert DEVELOPMENTAL_DIVERGENCE_METRIC_VERSION == "developmental_divergence@1"
    assert doc.values["mean_pairwise_distance"] == 1.0
