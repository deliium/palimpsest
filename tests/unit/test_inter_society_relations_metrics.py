"""ISR metric families and MetricComputationInputs emit gate."""

from __future__ import annotations

from itertools import pairwise

import pytest

from analysis.inter_society_relations_detection import (
    InterSocietyMacroCandidate,
    harvest_inter_society_relations,
)
from analysis.inter_society_relations_evidence import InterSocietyEvidenceInputs
from analysis.inter_society_relations_metrics import (
    compute_inter_society_domain_evidence,
    compute_inter_society_pair_comparison,
    compute_inter_society_relation_structure,
    compute_inter_society_relation_timeseries,
)
from analysis.macro_society_contract import MacroSocietyLane, derive_macro_society_id
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.specifications import MetricFamilyId

pytestmark = pytest.mark.unit


def _msoc(label: str, *, tick: int = 0) -> str:
    return derive_macro_society_id(
        creation_tick=tick,
        founding_member_ids=tuple(f"{label}-p{i}" for i in range(1, 5)),
        lane_signature=(MacroSocietyLane.COMMUNICATION.value,),
    )


def _analysis(*, pairs: int = 1):
    candidates = []
    evidence = {}
    societies = []
    for index in range(pairs + 1):
        society = _msoc(f"s{index}", tick=index)
        societies.append(society)
        candidates.append(
            InterSocietyMacroCandidate(
                society_id=society,
                member_ids=tuple(f"s{index}-p{i}" for i in range(1, 5)),
                window_tick=0,
            )
        )
    for left, right in pairwise(societies):
        key = tuple(sorted((left, right)))
        evidence[key] = InterSocietyEvidenceInputs(exchange_event_count=1)
    return harvest_inter_society_relations(candidates, evidence_by_pair=evidence)


def test_empty_analysis_emits_unknown_not_invented_pairs() -> None:
    empty = harvest_inter_society_relations(())
    structure = compute_inter_society_relation_structure(
        empty, run_id="run", input_revision="rev"
    )
    assert structure.availability.value == "unknown"
    assert structure.values == {}


def test_structure_and_domain_metrics() -> None:
    analysis = _analysis(pairs=1)
    structure = compute_inter_society_relation_structure(
        analysis, run_id="run", input_revision="rev"
    )
    assert (
        structure.metric_family == MetricFamilyId.INTER_SOCIETY_RELATION_STRUCTURE.value
    )
    assert structure.values["pair_count"] == 1
    domain = compute_inter_society_domain_evidence(
        analysis, run_id="run", input_revision="rev"
    )
    assert domain.values["exchange_present"] == 1
    assert "score" not in domain.values


def test_timeseries_and_comparison_metrics() -> None:
    analysis = _analysis(pairs=2)
    series = compute_inter_society_relation_timeseries(
        analysis, run_id="run", input_revision="rev"
    )
    assert series.values["pair_series_count"] >= 1
    comparison = compute_inter_society_pair_comparison(
        analysis, run_id="run", input_revision="rev"
    )
    assert comparison.values["domain_count"] == 8
    assert "composite" not in comparison.values


def test_metric_service_emit_gate() -> None:
    analysis = _analysis(pairs=2)
    bundle = assemble_metric_documents(
        MetricComputationInputs(
            run_id="run-1",
            input_revision="rev-1",
            window_end=64,
            inter_society_relations_analysis=analysis,
        )
    )
    families = {doc.metric_family for doc in bundle.documents}
    assert "inter_society_relation_structure" in families
    assert "inter_society_domain_evidence" in families
    assert "inter_society_relation_timeseries" in families
    assert "inter_society_pair_comparison" in families
    absent = assemble_metric_documents(
        MetricComputationInputs(run_id="run-1", input_revision="rev-1", window_end=64)
    )
    absent_families = {doc.metric_family for doc in absent.documents}
    assert "inter_society_relation_structure" not in absent_families
