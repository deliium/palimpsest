"""Knowledge genealogy holders / lineage / mutation metric computors."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from analysis.knowledge_genealogy_metrics import (
    KNOWLEDGE_GENEALOGY_HOLDERS_METRIC_VERSION,
    KNOWLEDGE_GENEALOGY_LINEAGE_METRIC_VERSION,
    KNOWLEDGE_GENEALOGY_MUTATION_METRIC_VERSION,
    compute_knowledge_genealogy_holders,
    compute_knowledge_genealogy_lineage,
    compute_knowledge_genealogy_mutation,
)
from analysis.models import MetricAvailability
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications

_LOG = logging.getLogger("tests.knowledge_genealogy_metrics")


def _audit(**kwargs) -> SimpleNamespace:
    base = dict(
        owner_id="alice",
        entry_id="e1",
        kind="foraging_method",
        content_key="tech:foraging",
        origin="independent_discovery",
        parent_entry_ids=(),
        lineage_root_id="root:alice:foraging_method:tech:foraging",
        hop_index=0,
        mutated=False,
        acquired_tick=1,
        tick=1,
        active=True,
        source_agent_id=None,
        teacher_agent_id=None,
        capability_anchor="foraging",
        fingerprint_distance_q=0.0,
        reason_code="formed",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_catalog_includes_three_genealogy_families() -> None:
    specs = all_metric_specifications()
    assert len(specs) == METRIC_FAMILY_COUNT == 65
    ids = {spec.family_id.value for spec in specs}
    assert "knowledge_genealogy_holders" in ids
    assert "knowledge_genealogy_lineage" in ids
    assert "knowledge_genealogy_mutation" in ids


def test_holders_empty_absent() -> None:
    _LOG.debug("case_id=holders_empty")
    doc = compute_knowledge_genealogy_holders(
        (), run_id="run-a", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.ABSENT
    assert doc.algorithm_version == "1"
    assert doc.metric_family == "knowledge_genealogy_holders"
    assert KNOWLEDGE_GENEALOGY_HOLDERS_METRIC_VERSION.endswith("@1")


def test_holders_nonempty_living_vs_dead() -> None:
    audits = (
        _audit(owner_id="alice", entry_id="e1"),
        _audit(
            owner_id="bob",
            entry_id="e2",
            origin="teaching",
            hop_index=1,
            teacher_agent_id="alice",
            source_agent_id="alice",
            acquired_tick=2,
            tick=2,
        ),
    )
    doc = compute_knowledge_genealogy_holders(
        audits,
        run_id="run-a",
        input_revision="rev-1",
        as_of_tick=5,
        death_ticks={"alice": 3},
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["living_holder_count"] == 1
    assert doc.values["dead_holder_count"] == 1
    assert doc.values["technique_count"] == 1
    assert "fingerprint" not in str(doc.values).lower() or "mean_hop" in doc.values


def test_lineage_empty_and_dual_emergence() -> None:
    empty = compute_knowledge_genealogy_lineage(
        (), run_id="run-a", input_revision="rev-1"
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert KNOWLEDGE_GENEALOGY_LINEAGE_METRIC_VERSION == "knowledge_genealogy_lineage@1"
    audits = (
        _audit(owner_id="alice", entry_id="e1"),
        _audit(
            owner_id="carol",
            entry_id="e2",
            lineage_root_id="root:carol:foraging_method:tech:foraging",
            acquired_tick=2,
            tick=2,
        ),
        _audit(
            owner_id="bob",
            entry_id="combo",
            content_key="tech:combo",
            origin="combination",
            parent_entry_ids=("e1", "e2"),
            hop_index=2,
            acquired_tick=3,
            tick=3,
            lineage_root_id="root:alice:foraging_method:tech:foraging",
        ),
    )
    doc = compute_knowledge_genealogy_lineage(
        audits, run_id="run-a", input_revision="rev-1", as_of_tick=4
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["independent_root_count"] >= 2
    assert float(doc.values["multi_parent_share"]) > 0.0
    assert float(doc.values["combination_rate"]) > 0.0
    assert float(doc.values["dual_independent_emergence_rate"]) > 0.0


def test_mutation_mean_distance_and_histogram() -> None:
    empty = compute_knowledge_genealogy_mutation(
        (), run_id="run-a", input_revision="rev-1"
    )
    assert empty.availability is MetricAvailability.ABSENT
    assert (
        KNOWLEDGE_GENEALOGY_MUTATION_METRIC_VERSION
        == "knowledge_genealogy_mutation@1"
    )
    audits = (
        _audit(entry_id="e1", fingerprint_distance_q=0.0),
        _audit(
            entry_id="e2",
            mutated=True,
            hop_index=1,
            origin="teaching",
            fingerprint_distance_q=0.2,
            parent_entry_ids=("e1",),
            acquired_tick=2,
            tick=2,
        ),
    )
    doc = compute_knowledge_genealogy_mutation(
        audits, run_id="run-a", input_revision="rev-1"
    )
    assert doc.availability is MetricAvailability.PRESENT
    assert doc.values["mutated_count"] == 1
    assert float(doc.values["mutated_hop_share"]) == 0.5
    assert float(doc.values["mean_fingerprint_distance_q"]) == 0.1
    assert doc.values["origin_independent_discovery_count"] == 1
    assert doc.values["origin_teaching_count"] == 1
