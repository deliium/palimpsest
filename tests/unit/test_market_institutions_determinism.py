"""Cross-process determinism and cap boundaries for market analysis."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from analysis.market_institutions_analysis import (
    harvest_market_institutions_analysis,
    market_institutions_analysis_digest,
)
from analysis.market_institutions_contract import (
    MarketCoverage,
    MarketVenueStatus,
    market_candidate_token,
    market_venue_token,
)
from analysis.market_institutions_detection import (
    detect_gatherings,
    detect_market_candidates,
    detect_participation,
    detect_venues,
)
from analysis.market_institutions_events import (
    MarketEvidenceHarvest,
    MarketExchangeRow,
)
from analysis.market_institutions_expectations import join_market_owner_rows
from analysis.market_institutions_identity import link_market_series
from analysis.market_institutions_policy import MarketInstitutionsAnalysisPolicy
from analysis.market_institutions_rows import (
    MarketCandidateRow,
    MarketOwnerExpectationInput,
    MarketOwnerRecordInput,
    MarketOwnerRoleInput,
    MarketParticipationRow,
    MarketVenueRow,
)
from world.identifiers import EventId

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]

_SCRIPT = """
from tests.unit.test_market_institutions_analysis import _events
from analysis.market_institutions_analysis import (
    harvest_market_institutions_analysis,
    market_institutions_analysis_digest,
)
from experiments.market_institutions_publication import (
    compose_market_institutions_snapshot,
)
analysis = harvest_market_institutions_analysis(committed_events=_events())
snapshot = compose_market_institutions_snapshot(analysis, run_id="run-1")
print(market_institutions_analysis_digest(analysis))
print(snapshot.digest)
print(analysis.coverage.value)
"""


def _run(seed: str) -> str:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed
    result = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_hash_seed_does_not_change_analysis_digest() -> None:
    assert _run("0") == _run("1")


def _harvest(windows: int, parties: int) -> MarketEvidenceHarvest:
    rows = []
    for window in range(windows):
        for index in range(min(parties, 4)):
            rows.append(
                MarketExchangeRow(
                    tick=window * 32,
                    window_index=window,
                    location_token="loc-a",
                    event_token=f"evt-{window}-{index}",
                    actor_token="body-a",
                    counterparty_token=f"body-{index + 2}",
                    party_tokens=cast(
                        tuple[str, str], tuple(sorted(("body-a", f"body-{index + 2}")))
                    ),
                )
            )
    return MarketEvidenceHarvest(
        exchanges=tuple(rows),
        attempts=(),
        coverage=MarketCoverage.COMPLETE,
        notices=(),
        exchange_count=len(rows),
        attempt_count=0,
    )


@given(
    windows=st.integers(min_value=1, max_value=8),
    parties=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=50, deadline=None)
def test_rows_never_exceed_policy_caps(windows: int, parties: int) -> None:
    policy = MarketInstitutionsAnalysisPolicy()
    harvest = _harvest(windows, parties)
    assert len(detect_gatherings(harvest)) <= policy.max_gathering_rows
    venues = detect_venues(harvest, window_end=windows - 1)
    assert len(venues) <= policy.max_venue_rows
    assert len(detect_participation(harvest)) <= policy.max_participation_rows
    assert len(detect_market_candidates(venues)) <= policy.max_markets
    for row in venues:
        assert 0 <= row.window_index < policy.max_windows
        assert 0 <= row.recurrence_milli <= 1_000


def _venue_row(window: int) -> MarketVenueRow:
    return MarketVenueRow(
        venue_id=market_venue_token("loc-a"),
        window_index=window,
        location_token="loc-a",
        exchange_count=2,
        proposal_count=0,
        withdrawn_count=0,
        distinct_party_count=2,
        distinct_actor_count=1,
        active_window_count=1,
        recurrence_milli=1_000,
        status=MarketVenueStatus.SINGLE_GATHERING,
        market_like=False,
        coverage=MarketCoverage.COMPLETE,
        participant_tokens=("body-a", "body-b"),
    )


def _venue_id() -> str:
    return market_venue_token("loc-a")


def _expectation_input(index: int) -> MarketOwnerExpectationInput:
    return MarketOwnerExpectationInput(
        owner_token=f"owner-{index}",
        venue_token=_venue_id(),
        expectation="expected",
        cadence="unknown",
        interval_ticks=None,
        phase_tick=None,
        schedule_window_index=None,
        confidence_milli=500,
        evidence_count=2,
        first_tick=0,
        last_tick=2,
    )


def _role_input(index: int) -> MarketOwnerRoleInput:
    return MarketOwnerRoleInput(
        owner_token=f"owner-{index}",
        venue_token=_venue_id(),
        role_kind="host",
        role_basis="claimed",
        recognized=False,
        actor_token=f"actor-{index}",
        first_tick=0,
        last_tick=2,
    )


def _record_input(index: int) -> MarketOwnerRecordInput:
    return MarketOwnerRecordInput(
        owner_token=f"owner-{index}",
        venue_token=_venue_id(),
        record_kind="exchange_record",
        anchor_token=f"anchor-{index}",
        first_tick=0,
        last_tick=2,
    )


@given(owners=st.integers(min_value=1, max_value=5))
@settings(max_examples=50, deadline=None)
def test_owner_join_rows_never_exceed_policy_caps(owners: int) -> None:
    policy = MarketInstitutionsAnalysisPolicy(
        max_expectation_rows=1,
        max_role_rows=1,
        max_record_rows=1,
    )
    venues = tuple(_venue_row(window) for window in range(3))
    participation = tuple(
        MarketParticipationRow(
            venue_id=_venue_id(),
            window_index=window,
            actor_token=f"actor-{index}",
            exchange_count=1,
            counterparty_count=1,
            active_window_count=1,
            broker_like=False,
            coverage=MarketCoverage.COMPLETE,
        )
        for window in range(3)
        for index in range(owners)
    )
    joined = join_market_owner_rows(
        expectation_inputs=tuple(_expectation_input(index) for index in range(owners)),
        role_inputs=tuple(_role_input(index) for index in range(owners)),
        record_inputs=tuple(_record_input(index) for index in range(owners)),
        venues=venues,
        participation=participation,
        window_end=2,
        policy=policy,
    )
    assert len(joined.expectations) <= policy.max_expectation_rows
    assert len(joined.roles) <= policy.max_role_rows
    assert len(joined.records) <= policy.max_record_rows


def test_market_lineage_respects_the_edge_cap() -> None:
    policy = MarketInstitutionsAnalysisPolicy(max_lineage_edges=1)
    tokens = tuple(market_venue_token(f"loc-{index}") for index in range(3))
    grouped = tuple(
        (
            MarketCandidateRow(
                market_token=market_candidate_token((token,)),
                window_index=window,
                venue_ids=(token,),
                exchange_count=2,
                distinct_party_count=2,
                coverage=MarketCoverage.COMPLETE,
            ),
        )
        for window, token in enumerate(tokens)
    )
    rows = link_market_series(grouped, policy=policy)
    assert len(rows) <= policy.max_lineage_edges


def test_unrelated_event_kind_does_not_change_the_digest() -> None:
    from tests.unit.test_market_institutions_analysis import _events

    baseline = harvest_market_institutions_analysis(committed_events=_events())
    unrelated = SimpleNamespace(
        event_id=EventId("evt-unrelated"),
        tick=999,
        sequence=0,
        details=object(),
        occurrence=None,
    )
    extended = harvest_market_institutions_analysis(
        committed_events=(*_events(), unrelated)
    )
    assert market_institutions_analysis_digest(baseline) == (
        market_institutions_analysis_digest(extended)
    )
    assert extended.exchange_count == baseline.exchange_count
