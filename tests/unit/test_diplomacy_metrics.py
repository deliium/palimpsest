"""V4-10 four metric documents and completed-run assembly."""

from __future__ import annotations

import pytest

from analysis.diplomacy_alignment import summarize_diplomacy
from analysis.diplomacy_contract import (
    DIPLOMACY_FORBIDDEN_RESULT_FIELDS,
    DiplomacyCoverage,
    diplomacy_agent_token,
)
from analysis.diplomacy_detection import detect_diplomacy_candidates
from analysis.diplomacy_identity import assign_diplomacy_identities
from analysis.diplomacy_layers import project_diplomacy_layers
from analysis.diplomacy_metrics import (
    compute_diplomatic_contact_structure,
    compute_diplomatic_envoy_alignment,
    compute_diplomatic_instrument_outcomes,
    compute_inter_society_relation_lanes,
)
from analysis.diplomacy_rows import (
    DiplomacyContactRow,
    DiplomacyDeclarationRow,
    DiplomacyHarvestRows,
    DiplomacyInstrumentRow,
    DiplomacyRelationRow,
    DiplomacyTerminationRow,
)
from analysis.metric_service import MetricComputationInputs, assemble_metric_documents
from analysis.models import MetricAvailability
from analysis.specifications import MetricFamilyId, metric_specification

pytestmark = pytest.mark.unit

OWNER = diplomacy_agent_token("agent-a")
PARTY = diplomacy_agent_token("agent-b")


def _rows() -> DiplomacyHarvestRows:
    return DiplomacyHarvestRows(
        relations=(
            DiplomacyRelationRow(
                owner_token=OWNER,
                relation_id="dpl-1",
                party_tokens=tuple(sorted((OWNER, PARTY))),
                opened_tick=1,
                last_tick=2,
                coverage=DiplomacyCoverage.PARTIAL,
            ),
        ),
        contacts=(
            DiplomacyContactRow(
                owner_token=OWNER,
                relation_id="dpl-1",
                tick=1,
                contact_kind="direct_co_presence",
                participant_count=2,
            ),
        ),
        instruments=(
            DiplomacyInstrumentRow(
                owner_token=OWNER,
                relation_id="dpl-1",
                instrument_id="dpi-1",
                party_tokens=tuple(sorted((OWNER, PARTY))),
                instrument_kind="proposal",
                term_kind="material_exchange",
                subject_token=None,
                opened_tick=1,
                end_tick=None,
                anchor_refs=(),
            ),
        ),
        declarations=(
            DiplomacyDeclarationRow(
                owner_token=OWNER,
                instrument_id="dpi-1",
                party_token=OWNER,
                envoy_token=None,
                act="propose",
                declared_tick=1,
            ),
            DiplomacyDeclarationRow(
                owner_token=OWNER,
                instrument_id="dpi-1",
                party_token=PARTY,
                envoy_token=None,
                act="accept",
                declared_tick=2,
            ),
        ),
        terminations=(
            DiplomacyTerminationRow(
                owner_token=OWNER,
                target_kind="instrument",
                kind="superseded",
                tick=2,
            ),
        ),
    )


def _context():
    rows = _rows()
    candidates = detect_diplomacy_candidates(rows, ())
    analysis = assign_diplomacy_identities(candidates)
    layers = project_diplomacy_layers(rows, candidates, analysis)
    summary = summarize_diplomacy(rows, candidates, layers)
    return rows, candidates, analysis, layers, summary


def test_four_documents_have_exact_value_keys() -> None:
    rows, candidates, _, layers, summary = _context()
    documents = (
        compute_diplomatic_contact_structure(
            rows, summary, layers, run_id="run-1", input_revision="rev-1"
        ),
        compute_diplomatic_instrument_outcomes(
            rows, summary, layers, run_id="run-1", input_revision="rev-1"
        ),
        compute_diplomatic_envoy_alignment(
            rows, summary, layers, run_id="run-1", input_revision="rev-1"
        ),
        compute_inter_society_relation_lanes(
            rows,
            summary,
            layers,
            run_id="run-1",
            input_revision="rev-1",
            candidates=candidates,
        ),
    )
    for document in documents:
        spec = metric_specification(document.metric_family)
        assert set(document.values) == set(spec.value_keys)
        for name in DIPLOMACY_FORBIDDEN_RESULT_FIELDS:
            assert name not in document.values
    assert documents[1].values["agreement_count"] == 1
    assert documents[1].values["superseded_count"] == 1


def test_absent_inputs_produce_no_values() -> None:
    document = compute_diplomatic_contact_structure(
        None, None, None, run_id="run-1", input_revision="rev-1"
    )
    assert document.availability is MetricAvailability.ABSENT
    assert document.values == {}


def test_completed_run_assembly_emits_all_four() -> None:
    rows = _rows()
    inputs = MetricComputationInputs(
        run_id="run-1",
        input_revision="rev-1",
        window_end=2,
        diplomacy_rows=rows,
    )
    bundle = assemble_metric_documents(inputs)
    families = {document.metric_family for document in bundle.documents}
    assert {
        MetricFamilyId.DIPLOMATIC_CONTACT_STRUCTURE.value,
        MetricFamilyId.DIPLOMATIC_INSTRUMENT_OUTCOMES.value,
        MetricFamilyId.DIPLOMATIC_ENVOY_ALIGNMENT.value,
        MetricFamilyId.INTER_SOCIETY_RELATION_LANES.value,
    } <= families


def test_trade_lane_excludes_given_by_construction() -> None:
    document = compute_inter_society_relation_lanes(
        _rows(),
        _context()[4],
        _context()[3],
        run_id="run-1",
        input_revision="rev-1",
        candidates=(),
    )
    assert document.values["trade_pair_count"] == 0
