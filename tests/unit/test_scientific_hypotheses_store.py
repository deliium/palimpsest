# mypy: ignore-errors
"""Atomic store and dual-gated settings for hypothesis snapshots."""

from __future__ import annotations

import pytest

from analysis.scientific_hypotheses_analysis import (
    harvest_scientific_hypotheses_analysis,
)
from analysis.scientific_hypotheses_contract import (
    NONE_TOKEN,
    ScientificHypothesisSourceKind,
    ScientificHypothesisStatus,
)
from analysis.scientific_hypotheses_rows import HypothesisFact
from experiments.scientific_hypotheses_publication import (
    compose_scientific_hypotheses_snapshot,
)
from infrastructure.settings import Settings
from persistence.scientific_hypotheses_filesystem import (
    SCIENTIFIC_HYPOTHESES_STORE_VERSION,
    ScientificHypothesesPublisherOptions,
    scientific_hypotheses_store_publisher,
    scientific_hypotheses_store_reader,
)
from world.experimentation import ExperimentOutcomeClass

pytestmark = pytest.mark.unit


def _snapshot():
    fact = HypothesisFact(
        owner_token="owner-1",
        hypothesis_token="schyp-1",
        claim_token="claim-1",
        causal_hypothesis_token=NONE_TOKEN,
        status=ScientificHypothesisStatus.PROVISIONAL,
        predicted_outcome=ExperimentOutcomeClass.SUCCESS.value,
        confidence_milli=500,
        created_tick=0,
        active=True,
        source_kind=ScientificHypothesisSourceKind.SELF_FORMULATED,
        source_token="self",
        conditions=(),
        revisions=(),
        trials=(),
    )
    analysis = harvest_scientific_hypotheses_analysis(events=(), facts=(fact,))
    return compose_scientific_hypotheses_snapshot(
        analysis, run_id="run-science"
    )


def test_store_version_and_round_trip(tmp_path) -> None:
    assert SCIENTIFIC_HYPOTHESES_STORE_VERSION == "scientific-hypotheses-store-v1"
    snapshot = _snapshot()
    publisher = scientific_hypotheses_store_publisher(tmp_path)
    receipt = publisher.publish(snapshot)
    assert receipt.stored is True
    reader = scientific_hypotheses_store_reader(tmp_path)
    assert reader.read_snapshot("run-science") == snapshot
    again = publisher.publish(snapshot)
    assert again.stored is False


def test_store_conflict_on_differing_digest(tmp_path) -> None:
    snapshot = _snapshot()
    publisher = scientific_hypotheses_store_publisher(tmp_path)
    publisher.publish(snapshot)
    conflicting = compose_scientific_hypotheses_snapshot(
        harvest_scientific_hypotheses_analysis(events=(), facts=()),
        run_id="run-science",
    )
    object.__setattr__(conflicting, "publication_id", snapshot.publication_id)
    with pytest.raises(ValueError, match="scientific_hypotheses_publication_exists"):
        publisher.publish(conflicting)


def test_store_count_quota(tmp_path) -> None:
    publisher = scientific_hypotheses_store_publisher(
        tmp_path,
        options=ScientificHypothesesPublisherOptions(max_publications=1),
    )
    publisher.publish(_snapshot())
    with pytest.raises(ValueError, match="quota_exceeded"):
        publisher.publish(
            compose_scientific_hypotheses_snapshot(
                harvest_scientific_hypotheses_analysis(events=(), facts=()),
                run_id="run-science",
            )
        )


def test_store_corruption_fails_closed(tmp_path) -> None:
    publisher = scientific_hypotheses_store_publisher(tmp_path)
    snapshot = _snapshot()
    publisher.publish(snapshot)
    state = tmp_path / "run-science" / "state.json"
    state.write_text("{not-json", encoding="utf-8")
    reader = scientific_hypotheses_store_reader(tmp_path)
    with pytest.raises(ValueError, match="store_corrupt"):
        reader.read_snapshot("run-science")


def test_settings_dual_gate() -> None:
    unset = Settings().bootstrap_fields()
    assert unset["scientific_hypotheses_enabled"] is False
    root_only = Settings(scientific_hypotheses_root="/tmp/science").bootstrap_fields()
    assert root_only["has_scientific_hypotheses_root"] is True
    assert root_only["scientific_hypotheses_enabled"] is False
    key_only = Settings(
        scientific_hypotheses_cursor_key="x" * 32
    ).bootstrap_fields()
    assert key_only["has_scientific_hypotheses_cursor_key"] is True
    assert key_only["scientific_hypotheses_enabled"] is False
    both = Settings(
        scientific_hypotheses_root="/tmp/science",
        scientific_hypotheses_cursor_key="x" * 32,
    ).bootstrap_fields()
    assert both["scientific_hypotheses_enabled"] is True
    with pytest.raises(ValueError):
        Settings(scientific_hypotheses_cursor_key="short")


def test_settings_empty_root_is_unset() -> None:
    assert Settings(scientific_hypotheses_root="").scientific_hypotheses_root is None


def test_bootstrap_flags() -> None:
    both = Settings(
        scientific_hypotheses_root="/tmp/science",
        scientific_hypotheses_cursor_key="x" * 32,
    )
    fields = both.bootstrap_fields()
    assert fields["has_scientific_hypotheses_root"] is True
    assert fields["has_scientific_hypotheses_cursor_key"] is True
    assert fields["scientific_hypotheses_enabled"] is True
    assert fields["scientific_hypotheses_cursor_enabled"] is True
