# mypy: ignore-errors
"""Identical social-mobility evidence produces identical canonical bytes."""

from __future__ import annotations

import pytest

from analysis.social_mobility_analysis import harvest_social_mobility_analysis
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
    compose_social_mobility_snapshot,
)
from simulation.social_mobility_codec import (
    encode_social_mobility_snapshot,
    social_mobility_digest,
)

pytestmark = pytest.mark.unit


def _token(name: str) -> str:
    return social_mobility_owner_token(name)


def _fixture():
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
        for owner, quantity, generation in (
            (ancestor, index, 0),
            (descendant, index + 1, 1),
        ):
            rows.append(
                SocialMobilityOutcomeRow(
                    owner_token=_token(owner),
                    generation_index=generation,
                    tick=31,
                    window_index=0,
                    domain=SocialMobilityDomain.RESOURCES,
                    measure=SocialMobilityMeasure.OBSERVED_RESOURCE_ITEM_COUNT,
                    quantity=quantity,
                    layer=SocialMobilityLayer.OBJECTIVE_OUTCOME,
                )
            )
    return (
        SocialMobilityGenealogyHarvest(
            edges=tuple(edges),
            generations=tuple(sorted(generations.items())),
            lineages=tuple(lineages),
            coverage=SocialMobilityCoverage.COMPLETE,
            event_count=8,
            owner_count=16,
            max_generation_index=1,
        ),
        SocialMobilityOutcomeHarvest(
            rows=tuple(rows),
            coverage=SocialMobilityCoverage.COMPLETE,
            event_count=16,
            owner_count=16,
        ),
    )


def test_snapshot_bytes_and_digest_are_stable() -> None:
    genealogy, outcomes = _fixture()
    first = harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)
    second = harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)
    assert first == second
    assert first.domain_rows == second.domain_rows
    assert first.generation_rows == second.generation_rows
    assert first.lag_rows == second.lag_rows
    assert first.pair_rows == second.pair_rows
    encoded_first = encode_social_mobility_snapshot(
        compose_social_mobility_snapshot(first, run_id="run-1")
    )
    encoded_second = encode_social_mobility_snapshot(
        compose_social_mobility_snapshot(second, run_id="run-1")
    )
    assert encoded_first == encoded_second
    assert social_mobility_digest(
        compose_social_mobility_snapshot(first, run_id="run-1")
    ) == social_mobility_digest(
        compose_social_mobility_snapshot(second, run_id="run-1")
    )


def test_identity_map_order_does_not_change_snapshot() -> None:
    genealogy, outcomes = _fixture()
    forward = {f"agent:{index}": _token(f"entity:{index}") for index in range(16)}
    from analysis.social_mobility_contract import SocialMobilityIdentityMap

    left = SocialMobilityIdentityMap(
        forward=dict(sorted(forward.items())),
        reverse={value: key for key, value in sorted(forward.items())},
    )
    right = SocialMobilityIdentityMap(
        forward=dict(reversed(sorted(forward.items()))),
        reverse={value: key for key, value in reversed(sorted(forward.items()))},
    )
    assert left.owner_count == right.owner_count
    assert harvest_social_mobility_analysis(
        genealogy=genealogy, outcomes=outcomes
    ) == harvest_social_mobility_analysis(genealogy=genealogy, outcomes=outcomes)
