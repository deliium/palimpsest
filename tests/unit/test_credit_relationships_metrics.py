"""Four detached credit metric families and their coverage states."""

# mypy: ignore-errors


from __future__ import annotations

import pytest

from analysis.credit_relationships_analysis import (
    empty_credit_relationships_analysis,
    harvest_credit_relationships_analysis,
)
from analysis.credit_relationships_metrics import (
    assemble_credit_relationship_metrics,
    compute_credit_distribution_structure,
    compute_credit_relationship_formation,
    compute_credit_repayment_performance,
    compute_credit_term_alignment,
)
from analysis.credit_relationships_policy import (
    CreditRelationshipsAnalysisPolicy,
)
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId
from tests.unit.credit_relationships_analysis_helpers import (
    completed,
    frame,
    given,
    talked,
)
from tests.unit.test_credit_relationships_expectations import _owner
from world.credit_relationships import CreditFrameAct

pytestmark = pytest.mark.unit

RUN_ID = "run-credit-1"
REVISION = "rev-1"


def _analysis():
    return harvest_credit_relationships_analysis(
        committed_events=[
            completed(
                "evt-0", give_ids=("item-1",), give_kinds=("food",), tick=0
            ),
            talked("evt-1", frame(), tick=0, sequence=1),
            talked("evt-2", frame(act=CreditFrameAct.ACCEPT), tick=1),
            given("evt-3", item_id="item-1", tick=2),
        ],
        owner_inputs=(_owner(),),
        policy=CreditRelationshipsAnalysisPolicy(min_distribution_samples=1),
    )


def test_unknown_analysis_emits_four_unknown_documents() -> None:
    analysis = empty_credit_relationships_analysis()
    documents = assemble_credit_relationship_metrics(
        analysis, run_id=RUN_ID, input_revision=REVISION
    )
    assert len(documents) == 4
    assert [document.metric_family for document in documents] == [
        MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION.value,
        MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE.value,
        MetricFamilyId.CREDIT_TERM_ALIGNMENT.value,
        MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE.value,
    ]
    for document in documents:
        assert document.availability is MetricAvailability.UNKNOWN
        assert document.values == {}


def test_present_analysis_emits_values_for_every_family() -> None:
    analysis = _analysis()
    documents = assemble_credit_relationship_metrics(
        analysis, run_id=RUN_ID, input_revision=REVISION
    )
    assert all(
        document.availability is MetricAvailability.PRESENT
        for document in documents
    )
    assert documents[0].values["relationship_count"] == 1
    assert documents[1].values["performance_count"] == 1
    assert documents[2].values["alignment_row_count"] == 1
    assert documents[3].values["distribution_count"] == 2


def test_partial_analysis_emits_partial_documents() -> None:
    analysis = harvest_credit_relationships_analysis(
        committed_events=[talked("evt-1", frame(), tick=0)],
        owner_inputs=(_owner(window_index=9),),
    )
    documents = assemble_credit_relationship_metrics(
        analysis, run_id=RUN_ID, input_revision=REVISION
    )
    formation = documents[0]
    assert formation.availability is MetricAvailability.PARTIAL
    assert formation.coverage.observed == 0
    assert formation.coverage.expected == 1


def test_each_compute_function_targets_its_own_family() -> None:
    analysis = _analysis()
    assert (
        compute_credit_relationship_formation(
            analysis, run_id=RUN_ID, input_revision=REVISION
        ).metric_family
        == MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION.value
    )
    assert (
        compute_credit_repayment_performance(
            analysis, run_id=RUN_ID, input_revision=REVISION
        ).metric_family
        == MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE.value
    )
    assert (
        compute_credit_term_alignment(
            analysis, run_id=RUN_ID, input_revision=REVISION
        ).metric_family
        == MetricFamilyId.CREDIT_TERM_ALIGNMENT.value
    )
    assert (
        compute_credit_distribution_structure(
            analysis, run_id=RUN_ID, input_revision=REVISION
        ).metric_family
        == MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE.value
    )


def test_value_keys_match_specifications() -> None:
    from analysis.specifications import (
        CREDIT_DISTRIBUTION_STRUCTURE_KEYS,
        CREDIT_RELATIONSHIP_FORMATION_KEYS,
        CREDIT_REPAYMENT_PERFORMANCE_KEYS,
        CREDIT_TERM_ALIGNMENT_KEYS,
        metric_specification,
    )

    for family, keys in (
        (
            MetricFamilyId.CREDIT_RELATIONSHIP_FORMATION,
            CREDIT_RELATIONSHIP_FORMATION_KEYS,
        ),
        (
            MetricFamilyId.CREDIT_REPAYMENT_PERFORMANCE,
            CREDIT_REPAYMENT_PERFORMANCE_KEYS,
        ),
        (MetricFamilyId.CREDIT_TERM_ALIGNMENT, CREDIT_TERM_ALIGNMENT_KEYS),
        (
            MetricFamilyId.CREDIT_DISTRIBUTION_STRUCTURE,
            CREDIT_DISTRIBUTION_STRUCTURE_KEYS,
        ),
    ):
        assert metric_specification(family).value_keys == keys


def test_forbidden_metric_keys_are_rejected() -> None:
    from analysis.credit_relationships_contract import (
        CreditRelationshipAnalysisError,
    )
    from analysis.credit_relationships_metrics import _reject_forbidden_fields

    with pytest.raises(CreditRelationshipAnalysisError):
        _reject_forbidden_fields({"credit_score": 1})
