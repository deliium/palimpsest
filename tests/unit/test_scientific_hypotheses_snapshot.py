# mypy: ignore-errors
"""Snapshot, codec, paging, ports, and publication composition."""

from __future__ import annotations

import dataclasses

import pytest

from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisConditionSlot,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import (
    HypothesisConditionFact,
    HypothesisFact,
    HypothesisTrialFact,
)
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
    publish_scientific_hypotheses_snapshot,
)
from simulation.scientific_hypotheses_codec import (
    decode_scientific_hypotheses_snapshot,
    encode_scientific_hypotheses_snapshot,
    scientific_hypotheses_digest,
)
from simulation.scientific_hypotheses_models import (
    ScientificHypothesesSnapshot,
    empty_scientific_hypotheses_snapshot,
)
from simulation.scientific_hypotheses_paging import (
    DEFAULT_SCIENTIFIC_HYPOTHESES_LIMIT,
    MAX_SCIENTIFIC_HYPOTHESES_LIMIT,
    page_scientific_hypothesis_rows,
)
from simulation.scientific_hypotheses_ports import (
    SCIENTIFIC_HYPOTHESES_CURSOR_TOKEN,
    scientific_hypotheses_query_fingerprint,
)
from world.experimentation import DiscoveryMode, ExperimentOutcomeClass

pytestmark = pytest.mark.unit


def _analysis():
    facts = tuple(
        HypothesisFact(
            owner_token=f"owner-{index}",
            hypothesis_token=f"schyp-{index}",
            claim_token=f"claim-{index}",
            causal_hypothesis_token=NONE_TOKEN,
            status=ScientificHypothesisStatus.PROVISIONAL,
            predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
            confidence_milli=500,
            created_tick=index,
            active=True,
            source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
            source_token="self",
            conditions=(
                HypothesisConditionFact(
                    slot=ScientificHypothesisConditionSlot.LOCATION,
                    value_token="loc-1",
                ),
            ),
            revisions=(),
            trials=(
                HypothesisTrialFact(
                    tick=index,
                    event_token=f"evt:{index}",
                    outcome_class=ExperimentOutcomeClass.SUCCESS,
                    discovery_mode=DiscoveryMode.DELIBERATE,
                    predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
                    matched=True,
                ),
            ),
        )
        for index in range(3)
    )
    return harvest_scientific_hypotheses_analysis(events=(), facts=facts)


def _snapshot():
    return compose_scientific_hypotheses_snapshot(
        _analysis(), run_id="run-science"
    )


def test_empty_snapshot_is_explicit() -> None:
    snapshot = empty_scientific_hypotheses_snapshot(run_id="run-empty")
    assert snapshot.hypotheses == ()
    assert snapshot.summary.coverage == "missing"


def test_snapshot_has_no_owner_or_wall_clock_fields() -> None:
    names = set(ScientificHypothesesSnapshot.__dataclass_fields__)
    assert "owner_id" not in names
    assert "generated_at" not in names
    dumped = str(dataclasses.asdict(_snapshot()))
    assert "owner-" not in dumped
    assert "generated_at" not in dumped


def test_compose_drops_owner_tokens() -> None:
    snapshot = _snapshot()
    assert snapshot.hypotheses
    for row in snapshot.hypotheses:
        assert not hasattr(row, "owner_token")
    assert snapshot.internal_digest.startswith("sha256:")
    assert snapshot.publication_id.startswith("schyp-")


def test_codec_round_trip_is_byte_identical() -> None:
    snapshot = _snapshot()
    payload = encode_scientific_hypotheses_snapshot(snapshot)
    decoded = decode_scientific_hypotheses_snapshot(
        payload, run_id="run-science"
    )
    assert decoded == snapshot
    assert encode_scientific_hypotheses_snapshot(decoded) == payload
    assert scientific_hypotheses_digest(snapshot) == snapshot.internal_digest


def test_codec_rejects_tamper_run_mismatch_and_unknown_keys() -> None:
    snapshot = _snapshot()
    payload = encode_scientific_hypotheses_snapshot(snapshot)
    with pytest.raises(ValueError, match="run_mismatch"):
        decode_scientific_hypotheses_snapshot(payload, run_id="other")
    with pytest.raises(ValueError):
        decode_scientific_hypotheses_snapshot(payload + b" ")
    with pytest.raises(ValueError):
        decode_scientific_hypotheses_snapshot(payload.replace(b'"run_id"', b'"runn"'))


def test_paging_filters_and_limits() -> None:
    snapshot = _snapshot()
    rows, next_key = page_scientific_hypothesis_rows(
        snapshot, purpose="hypotheses", limit=1
    )
    assert len(rows) == 1
    assert next_key
    rest, _ = page_scientific_hypothesis_rows(
        snapshot, purpose="hypotheses", limit=10, after=next_key
    )
    assert {row.hypothesis_token for row in rows} & {
        row.hypothesis_token for row in rest
    } == set()
    with pytest.raises(ValueError):
        page_scientific_hypothesis_rows(snapshot, purpose="unknown")
    with pytest.raises(ValueError):
        page_scientific_hypothesis_rows(
            snapshot, purpose="hypotheses", limit=MAX_SCIENTIFIC_HYPOTHESES_LIMIT + 1
        )
    assert DEFAULT_SCIENTIFIC_HYPOTHESES_LIMIT == 100


def test_windows_purpose_uses_coverage() -> None:
    rows, _ = page_scientific_hypothesis_rows(_snapshot(), purpose="windows")
    assert rows


def test_cursor_fingerprint_binds_query_dimensions() -> None:
    assert SCIENTIFIC_HYPOTHESES_CURSOR_TOKEN.endswith("cursor.v1")
    base = dict(
        run_id="run-1",
        publication_id="schyp-1",
        digest="sha256:abc",
        purpose="hypotheses",
        window_index=0,
        limit=100,
    )
    first = scientific_hypotheses_query_fingerprint(**base)
    assert first == scientific_hypotheses_query_fingerprint(**base)
    assert first != scientific_hypotheses_query_fingerprint(
        **{**base, "purpose": "evidence"}
    )
    assert first != scientific_hypotheses_query_fingerprint(
        **{**base, "window_index": 1}
    )
    assert first != scientific_hypotheses_query_fingerprint(
        **{**base, "limit": 50}
    )


def test_publication_disabled_and_missing_statuses() -> None:
    disabled = publish_scientific_hypotheses_snapshot(
        analysis=_analysis(), run_id="run-science", enabled=False
    )
    assert disabled.reason_code == "publication_disabled"
    assert disabled.stored is False
    empty = harvest_scientific_hypotheses_analysis(events=(), facts=())
    missing = publish_scientific_hypotheses_snapshot(
        analysis=empty, run_id="run-empty"
    )
    assert missing.reason_code == "publication_missing"


def test_publication_quota_and_success_statuses(tmp_path) -> None:
    from persistence.scientific_hypotheses_filesystem import (
        ScientificHypothesesPublisherOptions,
        scientific_hypotheses_store_publisher,
    )

    publisher = scientific_hypotheses_store_publisher(
        tmp_path, options=ScientificHypothesesPublisherOptions(max_publications=1)
    )
    first = publish_scientific_hypotheses_snapshot(
        analysis=_analysis(), run_id="run-science", publisher=publisher
    )
    assert first.reason_code == "published"
    assert first.stored is True

    class Failing:
        def publish(self, snapshot):
            raise ValueError("scientific_hypotheses_store_quota_exceeded")

    quota = publish_scientific_hypotheses_snapshot(
        analysis=_analysis(), run_id="run-science", publisher=Failing()
    )
    assert quota.reason_code == "store_quota_exceeded"
