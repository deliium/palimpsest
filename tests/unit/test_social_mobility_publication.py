# mypy: ignore-errors
"""Compose and publish completed-run social-mobility snapshots."""

from __future__ import annotations

import pytest

from analysis.social_mobility_analysis import (
    empty_social_mobility_analysis,
    harvest_social_mobility_analysis,
)
from analysis.social_mobility_contract import (
    SocialMobilityCoverage,
    SocialMobilityDomain,
    SocialMobilityLayer,
    SocialMobilityMeasure,
    social_mobility_lineage_token,
    social_mobility_owner_token,
)
from analysis.social_mobility_genealogy import SocialMobilityGenealogyHarvest
from analysis.social_mobility_outcomes import SocialMobilityOutcomeHarvest
from analysis.social_mobility_rows import (
    SocialMobilityGenealogyRow,
    SocialMobilityLineageEntry,
    SocialMobilityOutcomeRow,
)
from experiments.social_mobility_publication import (
    build_social_mobility_harvest_result,
    compose_social_mobility_snapshot,
    publish_social_mobility_snapshot,
)
from persistence.social_mobility_filesystem import (
    SocialMobilityPublisherOptions,
    create_social_mobility_publisher,
)
from simulation.social_mobility_codec import (
    decode_social_mobility_snapshot,
    encode_social_mobility_snapshot,
)

pytestmark = pytest.mark.unit


def _token(name: str) -> str:
    return social_mobility_owner_token(name)


def _analysis():
    lineages = []
    edges = []
    generations = {}
    rows = []
    for index in range(8):
        ancestor = f"entity:a{index}"
        descendant = f"entity:b{index}"
        lineages.append(
            SocialMobilityLineageEntry(
                lineage_token=social_mobility_lineage_token(
                    _token(ancestor), _token(descendant)
                ),
                ancestor_token=_token(ancestor),
                descendant_token=_token(descendant),
                generation_lag=1,
                ancestor_generation=0,
                descendant_generation=1,
            )
        )
        edges.append(
            SocialMobilityGenealogyRow(
                parent_token=_token(ancestor),
                child_token=_token(descendant),
                parent_generation=0,
                child_generation=1,
                established_tick=index,
                window_index=0,
            )
        )
        generations[_token(ancestor)] = 0
        generations[_token(descendant)] = 1
        rows.append(_outcome(ancestor, index))
        rows.append(_outcome(descendant, index + 1, generation=1))
    genealogy = SocialMobilityGenealogyHarvest(
        edges=tuple(edges),
        generations=tuple(sorted(generations.items())),
        lineages=tuple(lineages),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=8,
        owner_count=16,
        max_generation_index=1,
    )
    outcomes = SocialMobilityOutcomeHarvest(
        rows=tuple(rows),
        coverage=SocialMobilityCoverage.COMPLETE,
        event_count=16,
        owner_count=16,
    )
    return harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)


def _outcome(owner: str, quantity: int, *, generation: int = 0):
    return SocialMobilityOutcomeRow(
        owner_token=_token(owner),
        generation_index=generation,
        tick=31,
        window_index=0,
        domain=SocialMobilityDomain.RESOURCES,
        measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
        quantity=quantity,
        layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
    )


def test_compose_maps_every_row_family_and_round_trips() -> None:
    snapshot = compose_social_mobility_snapshot(_analysis(), run_id="run-1")
    assert snapshot.summary.domain_row_count > 0
    assert snapshot.summary.generation_row_count > 0
    assert snapshot.summary.lag_row_count > 0
    assert snapshot.coverage
    encoded = encode_social_mobility_snapshot(snapshot)
    decoded = decode_social_mobility_snapshot(encoded, run_id="run-1")
    assert decoded == snapshot
    assert decoded.summary.truncated is True


def test_empty_analysis_composes_a_missing_snapshot() -> None:
    snapshot = compose_social_mobility_snapshot(
        empty_social_mobility_analysis(), run_id="run-1"
    )
    assert snapshot.summary.coverage == "missing"
    assert snapshot.summary.domain_row_count == 0


def test_publish_receipts_for_each_reason(tmp_path) -> None:
    missing = compose_social_mobility_snapshot(
        empty_social_mobility_analysis(), run_id="run-1"
    )
    assert publish_social_mobility_snapshot(missing, None).reason_code == (
        "publication_missing"
    )
    snapshot = compose_social_mobility_snapshot(_analysis(), run_id="run-1")
    disabled = publish_social_mobility_snapshot(snapshot, None)
    assert disabled.reason_code == "publication_disabled"
    assert disabled.stored is False
    publisher = create_social_mobility_publisher(tmp_path)
    published = publish_social_mobility_snapshot(snapshot, publisher)
    assert published.reason_code == "published"
    assert published.stored is True
    republished = publish_social_mobility_snapshot(snapshot, publisher)
    assert republished.reason_code == "published"
    assert republished.stored is False


def test_publish_maps_quota_failure_without_raising(tmp_path) -> None:
    snapshot = compose_social_mobility_snapshot(_analysis(), run_id="run-1")
    publisher = create_social_mobility_publisher(
        tmp_path, options=SocialMobilityPublisherOptions(max_bytes=1)
    )
    receipt = publish_social_mobility_snapshot(snapshot, publisher)
    assert receipt.reason_code == "store_quota_exceeded"
    assert receipt.stored is False


def test_build_harvest_result_composes_and_publishes(tmp_path) -> None:
    harvest = build_social_mobility_harvest_result(
        _analysis(),
        run_id="run-1",
        publisher=create_social_mobility_publisher(tmp_path),
    )
    assert harvest.run_id == "run-1"
    assert harvest.snapshot.publication_id.startswith("socmob-pub-")
    assert harvest.receipt.reason_code == "published"
