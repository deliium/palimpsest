"""Executable metric specifications and known-answer fixtures (Task 10)."""

from __future__ import annotations

import math
import re

import pytest

from analysis.evidence import EvidenceStage
from analysis.models import METRIC_DOCUMENT_SCHEMA_VERSION, MetricAvailability
from analysis.numerical import (
    CANONICAL_FLOAT_DECIMAL_PLACES,
    CANONICAL_OUTPUT_CLAIM,
    SUPPORTED_COMMUNITY_ALGORITHM,
    quantize_float,
)
from analysis.specifications import (
    ACTION_VOCABULARY_V1,
    ADOPTION_STAGES_V1,
    METRIC_CATALOG_VERSION,
    METRIC_FAMILY_COUNT,
    AdoptionStage,
    MetricFamilyId,
    MetricSpecificationError,
    ResourceMeasureId,
    action_resolution_rate_spec,
    all_metric_specifications,
    metric_specification,
    require_metric_family_id,
    validate_metric_catalog,
    validate_metric_specification,
)
from tests.unit.metric_fixtures import (
    FixtureKind,
    all_known_answer_fixtures,
    degenerate_fixtures,
    reference_derived_fixtures,
)


def test_catalog_has_sixteen_unique_families() -> None:
    specs = validate_metric_catalog()
    assert len(specs) == METRIC_FAMILY_COUNT == 74
    assert len({spec.family_id for spec in specs}) == 74
    assert frozenset(spec.family_id for spec in specs) == frozenset(MetricFamilyId)
    assert METRIC_CATALOG_VERSION.startswith("metric-catalog-")


def test_every_spec_names_policy_and_version() -> None:
    for spec in all_metric_specifications():
        validate_metric_specification(spec)
        assert spec.schema_version == METRIC_DOCUMENT_SCHEMA_VERSION
        assert spec.algorithm_version == "1"
        assert spec.version_identifier == f"{spec.family_id.value}@1"
        assert spec.evidence_inputs
        assert spec.population
        assert spec.denominator
        assert spec.cohort_window
        assert spec.deceased_policy
        assert spec.zero_holding_policy
        assert spec.opportunity_vs_occurrence
        assert spec.self_edge_policy
        assert spec.censoring_policy
        assert spec.evidence_stage_deduplication
        assert spec.empty_case
        assert spec.one_case
        assert spec.all_zero_case
        assert MetricAvailability.UNKNOWN.value in spec.unknown_case
        assert CANONICAL_OUTPUT_CLAIM in spec.numpy_policy
        assert "pandas_na_is_unknown" in spec.pandas_policy
        assert "empty_or_single" in spec.scipy_policy
        assert str(CANONICAL_FLOAT_DECIMAL_PLACES) in spec.quantization
        assert spec.formula_ids
        assert set(spec.formula_ids) == set(spec.formulas)
        assert spec.value_keys
        assert "wealth" not in spec.population.lower()
        assert "wealth" not in " ".join(spec.formulas.values()).lower()


def test_resource_inequality_named_measures_not_wealth() -> None:
    spec = metric_specification(MetricFamilyId.RESOURCE_INEQUALITY)
    text = " ".join(
        [
            spec.denominator,
            *spec.formulas.values(),
            *spec.value_keys,
        ]
    )
    for measure in ResourceMeasureId:
        assert measure.value in text or measure.value in spec.denominator
    assert "wealth" not in text.lower()
    assert EvidenceStage.OBJECTIVE_EVENT_STATE in spec.evidence_inputs


def test_action_vocabulary_and_coop_conflict_disjoint_cores() -> None:
    assert len(ACTION_VOCABULARY_V1) == 15
    assert len(set(ACTION_VOCABULARY_V1)) == 15
    coop = metric_specification(MetricFamilyId.COOPERATION)
    conflict = metric_specification(MetricFamilyId.CONFLICT)
    assert set(coop.action_vocabulary) & set(conflict.action_vocabulary) == set()
    assert "attack" in conflict.action_vocabulary
    assert "help" in coop.action_vocabulary
    assert EvidenceStage.ACTION_RESOLUTION in coop.evidence_inputs
    assert EvidenceStage.ACTION_RESOLUTION in conflict.evidence_inputs


def test_shared_action_resolution_never_infers_from_absent_events() -> None:
    shared = action_resolution_rate_spec()
    assert shared.version_identifier == "action_resolution_rates@1"
    assert EvidenceStage.ACTION_RESOLUTION in shared.evidence_inputs
    blob = " ".join(shared.formulas.values()) + shared.unknown_case
    assert "never infer" in shared.unknown_case.lower() or "never infer" in blob.lower()
    assert "absent" in shared.unknown_case.lower() or "never" in shared.unknown_case


def test_motif_and_adoption_policies() -> None:
    motifs = metric_specification(MetricFamilyId.REPEATED_CONVENTIONS)
    assert "n-gram" in motifs.motif_tokenization.lower() or "n-gram" in motifs.formulas[
        "ngram_support_table"
    ]
    assert motifs.motif_gap_policy != "not_applicable"
    assert motifs.motif_support_policy != "not_applicable"
    assert motifs.action_vocabulary == ACTION_VOCABULARY_V1

    diffusion = metric_specification(MetricFamilyId.KNOWLEDGE_DIFFUSION)
    assert diffusion.adoption_stages == ADOPTION_STAGES_V1
    assert len(AdoptionStage) == 6
    assert "never infer parents" in diffusion.evidence_stage_deduplication.lower()


def test_belief_accuracy_requires_claim_truth_only() -> None:
    spec = metric_specification(MetricFamilyId.BELIEF_ACCURACY)
    assert "ClaimTruthSpec" in spec.population or "ClaimTruthSpec" in spec.denominator
    assert EvidenceStage.BELIEF_REVISION_TESTIMONY in spec.evidence_inputs
    assert "excluded" in spec.opportunity_vs_occurrence.lower()


def test_signed_trust_and_community_projection() -> None:
    trust = metric_specification(MetricFamilyId.TRUST_NETWORK_STRUCTURE)
    community = metric_specification(MetricFamilyId.GROUP_COMMUNITY_STRUCTURE)
    assert "signed" in trust.signed_trust_policy.lower()
    assert "self-loop" in trust.self_edge_policy.lower() or (
        "self-loops" in trust.self_edge_policy
    )
    assert "centralization_out" in trust.value_keys
    assert "mean_degree_centrality" in trust.value_keys
    assert "mean_betweenness_centrality" in trust.value_keys
    assert "mean_closeness_centrality" in trust.value_keys
    assert community.community_algorithm == SUPPORTED_COMMUNITY_ALGORITHM
    assert "max(trust,0)" in community.signed_trust_policy or "nonnegative" in (
        community.signed_trust_policy + community.graph_projection
    ).lower()
    assert "lexicographic" in community.graph_projection.lower() or "sorted" in (
        community.graph_projection.lower()
    )


def test_memory_drift_visibility_and_stage_dedup() -> None:
    spec = metric_specification(MetricFamilyId.MEMORY_DRIFT)
    assert EvidenceStage.AGENT_VISIBLE_PROJECTION in spec.evidence_inputs
    assert EvidenceStage.DIRECT_TRACE in spec.evidence_inputs
    assert "lineage root" in spec.evidence_stage_deduplication.lower()
    assert "agent-visible" in spec.opportunity_vs_occurrence.lower()


def test_lookup_and_unknown_family_error_codes_only() -> None:
    found = metric_specification("survival")
    assert found.family_id is MetricFamilyId.SURVIVAL
    assert (
        require_metric_family_id("x", MetricFamilyId.SURVIVAL)
        is MetricFamilyId.SURVIVAL
    )
    with pytest.raises(MetricSpecificationError) as exc:
        metric_specification("not_a_real_family")
    err = exc.value
    assert err.reason_code == "unknown_metric_family"
    assert err.metric_family == "not_a_real_family"
    message = str(err)
    assert "not_a_real_family" in message
    assert "unknown_metric_family" in message
    # No fixture/evidence payload leakage patterns.
    assert "inventory" not in message
    assert "gini" not in message


def test_validate_rejects_formula_mismatch_without_payload() -> None:
    from dataclasses import replace

    spec = metric_specification(MetricFamilyId.SURVIVAL)
    broken = replace(
        spec,
        formulas={"only_one": "x"},
        formula_ids=("only_one", "missing_in_map"),
    )
    with pytest.raises(MetricSpecificationError) as exc:
        validate_metric_specification(broken)
    assert exc.value.reason_code == "formula_id_mismatch"
    assert exc.value.metric_family == "survival"
    assert "x" not in str(exc.value)


def test_known_answer_fixtures_cover_reference_and_degenerate() -> None:
    ref = reference_derived_fixtures()
    deg = degenerate_fixtures()
    assert ref
    assert deg
    assert all(item.kind is FixtureKind.REFERENCE_DERIVED for item in ref)
    assert all(item.kind is FixtureKind.DEGENERATE for item in deg)
    all_fx = all_known_answer_fixtures()
    assert len(all_fx) == len(ref) + len(deg)
    families = {item.family_id for item in all_fx}
    # Fixtures span objective, behavior, subjective, and network families.
    assert MetricFamilyId.RESOURCE_INEQUALITY in families
    assert MetricFamilyId.SURVIVAL in families
    assert MetricFamilyId.BELIEF_ACCURACY in families
    assert MetricFamilyId.GROUP_COMMUNITY_STRUCTURE in families


def test_reference_survival_and_gini_known_answers() -> None:
    by_id = {item.fixture_id: item for item in all_known_answer_fixtures()}
    survival = by_id["ref-survival-early-death"]
    assert survival.availability is MetricAvailability.PRESENT
    assert survival.expected_values["survival_rate_at_T"] == quantize_float(0.8)
    assert survival.expected_values["deaths"] == 1

    skew = by_id["ref-resource-inequality-inventory-skew"]
    assert skew.expected_values["gini"] == quantize_float(0.8)
    assert skew.expected_values["theil_t"] == quantize_float(math.log(5.0))

    two = by_id["deg-resource-two-agent-gini"]
    assert two.expected_values["gini"] == quantize_float(0.5)


def test_action_resolution_partition_fixture() -> None:
    fx = next(
        item
        for item in degenerate_fixtures()
        if item.fixture_id == "deg-action-resolution-partition"
    )
    assert fx.expected_values["attempt_count"] == 4
    assert fx.expected_values["applied_rate"] == quantize_float(0.5)
    assert fx.expected_values["conflicted_rate"] == quantize_float(0.25)


def test_fixture_repr_omits_expected_numeric_payload_details() -> None:
    fx = reference_derived_fixtures()[0]
    text = repr(fx)
    assert fx.fixture_id in text
    assert "gini" not in text
    assert "0.8" not in text


def test_offline_consolidation_counts_and_missing_report() -> None:
    from analysis.metric_service import (
        MetricComputationInputs,
        assemble_metric_documents,
    )
    from analysis.offline_consolidation_metrics import (
        OfflineConsolidationReport,
        compute_offline_consolidation,
    )

    report = OfflineConsolidationReport(
        run_id="run-1",
        consolidation_invocations=2,
        traces_strengthened=3,
        traces_soft_forgotten=1,
        patterns_merged=1,
        belief_revisions=1,
        relationship_revisions=0,
        goal_transitions=0,
    )
    document = compute_offline_consolidation(report, input_revision="rev-1")
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["traces_strengthened"] == quantize_float(3.0)
    assert document.metric_family == "offline_consolidation"
    inputs = MetricComputationInputs(
        run_id="run-1",
        input_revision="rev-1",
        window_end=1,
    )
    bundle = assemble_metric_documents(inputs)
    assert "offline_consolidation" not in {
        item.metric_family for item in bundle.documents
    }


def test_spec_repr_is_metadata_only() -> None:
    text = repr(metric_specification(MetricFamilyId.RUMOR_DISTORTION))
    assert "rumor_distortion" in text
    assert "formula_count=" in text
    assert re.search(r"concepts_added|utterance|claim", text) is None
