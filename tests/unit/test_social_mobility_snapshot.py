# mypy: ignore-errors
"""Canonical social-mobility snapshot model, codec, and paging."""

from __future__ import annotations

import json

import pytest

from simulation.social_mobility_codec import (
    canonical_social_mobility_json,
    compute_social_mobility_publication_id,
    decode_social_mobility_snapshot,
    encode_social_mobility_snapshot,
    finalize_social_mobility_snapshot,
    social_mobility_digest,
)
from simulation.social_mobility_models import (
    MAX_SOCIAL_MOBILITY_DOMAIN_ROWS,
    MAX_SOCIAL_MOBILITY_GENERATION_ROWS,
    MAX_SOCIAL_MOBILITY_LAG_ROWS,
    SOCIAL_MOBILITY_POLICY_VERSION,
    SOCIAL_MOBILITY_SNAPSHOT_VERSION,
    SocialMobilityCoverageRecord,
    SocialMobilityDomainRecord,
    SocialMobilityGenerationRecord,
    SocialMobilityLagRecord,
    SocialMobilitySnapshot,
    SocialMobilitySummaryRecord,
    empty_social_mobility_snapshot,
)
from simulation.social_mobility_paging import (
    SOCIAL_MOBILITY_PAGE_MAX,
    page_social_mobility,
)
from simulation.social_mobility_ports import (
    SOCIAL_MOBILITY_PURPOSES,
    SocialMobilityCursor,
    social_mobility_query_fingerprint,
)

pytestmark = pytest.mark.unit


def _domain(
    domain: str = "resources", *, window: int = 0
) -> SocialMobilityDomainRecord:
    return SocialMobilityDomainRecord(
        window_index=window,
        window_tick=window * 32 + 31,
        domain=domain,
        measure={
            "resources": "observed_resource_item_count",
            "skills": "known_technique_count",
            "social_influence": "inbound_communication_partner_count",
            "organization_roles": "held_organization_role_count",
            "educational_access": "educational_access_receipt_count",
            "productive_assets": "observed_productive_asset_count",
        }[domain],
        pair_count=8,
        resolved_pair_count=8,
        rank_correlation_milli=250,
        same_bin_share_milli=600,
        upward_share_milli=250,
        downward_share_milli=150,
        mean_absolute_rank_change_milli=200,
        persistence_direction="persistent",
        coverage="complete",
        availability="available",
    )


def _snapshot() -> SocialMobilitySnapshot:
    return SocialMobilitySnapshot(
        run_id="run:1",
        schema_version=SOCIAL_MOBILITY_SNAPSHOT_VERSION,
        policy_version=SOCIAL_MOBILITY_POLICY_VERSION,
        summary=SocialMobilitySummaryRecord(
            domain_row_count=1,
            generation_row_count=1,
            lag_row_count=1,
            window_count=1,
            owner_count=16,
            generation_count=2,
            genealogy_edge_count=8,
            pair_count=8,
            resolved_pair_count=8,
            unresolved_pair_count=0,
            domain_available_count=1,
            coverage="complete",
            evidence_coverage="complete",
            domain_coverage="complete",
            generation_coverage="complete",
            truncated=False,
        ),
        domains=(_domain(),),
        generations=(
            SocialMobilityGenerationRecord(
                window_index=0,
                window_tick=31,
                generation_index=1,
                owner_count=8,
                pair_count=8,
                comparable=True,
                same_bin_share_milli=600,
                upward_share_milli=250,
                downward_share_milli=150,
                coverage="complete",
                availability="available",
            ),
        ),
        lags=(
            SocialMobilityLagRecord(
                window_index=0,
                window_tick=31,
                generation_lag=1,
                pair_count=8,
                comparable=True,
                same_bin_share_milli=600,
                upward_share_milli=250,
                downward_share_milli=150,
                coverage="complete",
                availability="available",
            ),
        ),
        coverage=(
            SocialMobilityCoverageRecord(
                window_index=0,
                window_tick=31,
                generation_count=2,
                owner_count=16,
                genealogy_edge_count=8,
                pair_count=8,
                resolved_pair_count=8,
                unresolved_pair_count=0,
                domain_available_count=1,
                truncated=False,
                coverage="complete",
            ),
        ),
    )


def test_empty_snapshot_is_missing_and_wall_clock_free() -> None:
    snapshot = empty_social_mobility_snapshot("run:1")
    assert snapshot.summary.coverage == "missing"
    payload = json.loads(encode_social_mobility_snapshot(snapshot))
    assert "created_at" not in payload
    assert "timestamp" not in payload


def test_snapshot_rejects_duplicate_identity_and_version_mismatch() -> None:
    with pytest.raises(ValueError, match="social_mobility_snapshot_invalid"):
        SocialMobilitySnapshot(
            run_id="run:1",
            schema_version=SOCIAL_MOBILITY_SNAPSHOT_VERSION,
            policy_version=SOCIAL_MOBILITY_POLICY_VERSION,
            summary=_snapshot().summary,
            domains=(_domain(), _domain()),
        )
    with pytest.raises(ValueError, match="social_mobility_snapshot_version"):
        SocialMobilitySnapshot(
            run_id="run:1",
            schema_version="social-mobility-snapshot-v0",
            policy_version=SOCIAL_MOBILITY_POLICY_VERSION,
            summary=_snapshot().summary,
        )


def test_caps_match_the_locked_summary() -> None:
    assert MAX_SOCIAL_MOBILITY_DOMAIN_ROWS == 4_096
    assert MAX_SOCIAL_MOBILITY_GENERATION_ROWS == 1_024
    assert MAX_SOCIAL_MOBILITY_LAG_ROWS == 2_048


def test_codec_round_trip_is_byte_identical() -> None:
    snapshot = finalize_social_mobility_snapshot(_snapshot())
    encoded = encode_social_mobility_snapshot(snapshot)
    assert canonical_social_mobility_json(snapshot) == encoded
    decoded = decode_social_mobility_snapshot(encoded, run_id="run:1")
    assert decoded.digest == snapshot.digest
    assert decoded.publication_id.startswith("socmob-pub-")
    assert encode_social_mobility_snapshot(decoded) == encoded


def test_digest_is_stable_and_publication_id_derives_from_it() -> None:
    snapshot = _snapshot()
    digest = social_mobility_digest(snapshot)
    assert digest == social_mobility_digest(snapshot)
    assert digest.startswith("sha256:")
    assert compute_social_mobility_publication_id(digest) == (
        "socmob-pub-" + digest.removeprefix("sha256:")[:16]
    )


def test_decode_rejects_corrupt_version_run_and_noncanonical_payloads() -> None:
    encoded = encode_social_mobility_snapshot(_snapshot())
    with pytest.raises(ValueError, match="social_mobility_snapshot_corrupt"):
        decode_social_mobility_snapshot(b"{not json")
    with pytest.raises(ValueError, match="social_mobility_snapshot_run_mismatch"):
        decode_social_mobility_snapshot(encoded, run_id="run:2")
    parsed = json.loads(encoded)
    parsed["schema_version"] = "social-mobility-snapshot-v0"
    with pytest.raises(ValueError, match="social_mobility_snapshot_version"):
        decode_social_mobility_snapshot(
            (json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n").encode()
        )
    parsed = json.loads(encoded)
    parsed["domains"][0]["rank_correlation_milli"] = 999
    tampered = (
        json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    with pytest.raises(ValueError, match="social_mobility_snapshot_digest_mismatch"):
        decode_social_mobility_snapshot(tampered)


def test_decode_rejects_publication_id_not_derived_from_digest() -> None:
    encoded = encode_social_mobility_snapshot(_snapshot())
    parsed = json.loads(encoded)
    parsed["publication_id"] = "socmob-pub-0000000000000000"
    tampered = (
        json.dumps(parsed, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    with pytest.raises(
        ValueError, match="social_mobility_snapshot_publication_mismatch"
    ):
        decode_social_mobility_snapshot(tampered)


def test_paging_filters_by_purpose_and_window() -> None:
    rows = (
        _domain("resources"),
        _domain("organization_roles"),
        _domain("resources", window=1),
    )
    page, next_key = page_social_mobility(domains=rows, purpose="economy")
    assert [row.domain for row in page] == ["resources", "resources"]
    assert next_key == ""
    filtered, _ = page_social_mobility(domains=rows, purpose="domains", window_index=1)
    assert [row.window_index for row in filtered] == [1]
    standing, _ = page_social_mobility(domains=rows, purpose="standing")
    assert [row.domain for row in standing] == ["organization_roles"]


def test_paging_limit_and_strict_after_key() -> None:
    rows = tuple(_domain("resources", window=index) for index in range(3))
    page, next_key = page_social_mobility(domains=rows, purpose="domains", limit=2)
    assert len(page) == 2
    assert next_key
    second, final = page_social_mobility(
        domains=rows, purpose="domains", limit=2, after_key=next_key
    )
    assert len(second) == 1
    assert final == ""
    with pytest.raises(ValueError, match="social_mobility_page_invalid"):
        page_social_mobility(
            domains=rows, purpose="domains", limit=2, after_key="999|resources"
        )
    with pytest.raises(ValueError, match="social_mobility_page_invalid"):
        page_social_mobility(
            domains=rows, purpose="domains", limit=SOCIAL_MOBILITY_PAGE_MAX + 1
        )


def test_generations_page_includes_generation_and_lag_rows() -> None:
    snapshot = _snapshot()
    page, _ = page_social_mobility(
        generations=snapshot.generations,
        lags=snapshot.lags,
        purpose="generations",
    )
    assert len(page) == 2


def test_cursor_and_fingerprint_bind_the_query() -> None:
    assert SOCIAL_MOBILITY_PURPOSES == (
        "summary",
        "domains",
        "economy",
        "human_capital",
        "standing",
        "generations",
        "coverage",
    )
    cursor = SocialMobilityCursor(
        purpose="domains",
        fingerprint="f" * 64,
        after_key="000|resources",
        window_index=0,
    )
    assert cursor.purpose == "domains"
    with pytest.raises(ValueError, match="social_mobility_cursor_invalid"):
        SocialMobilityCursor(
            purpose="not-a-purpose", fingerprint="f", after_key="", window_index=None
        )
    first = social_mobility_query_fingerprint(
        run_id="run:1",
        publication_id="socmob-pub-1",
        digest="sha256:1",
        purpose="domains",
        limit=100,
        window_index=0,
    )
    second = social_mobility_query_fingerprint(
        run_id="run:1",
        publication_id="socmob-pub-1",
        digest="sha256:1",
        purpose="domains",
        limit=100,
        window_index=1,
    )
    assert first != second
