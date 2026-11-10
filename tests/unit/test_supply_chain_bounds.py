# mypy: ignore-errors
"""Every supply-chain cap retains a deterministic prefix and reports truncation."""

from __future__ import annotations

import pytest

from analysis.supply_chain_analysis import harvest_supply_chain_analysis
from analysis.supply_chain_events import SupplyOrganizationClaim
from analysis.supply_chain_policy import (
    SupplyChainAnalysisPolicy,
    default_supply_chain_analysis_policy,
)
from tests.unit.test_supply_chain_graph import (
    _RECIPES,
    _craft_done,
    _craft_start,
    _harvest,
)

pytestmark = pytest.mark.unit


def _events():
    return [
        _harvest(
            "harvest_grain",
            "item-grain",
            tick=0,
            event_id="evt-h1",
            location="loc-1",
        ),
        _craft_start(
            "mill_grain",
            ("item-grain",),
            tick=0,
            event_id="evt-s1",
            location="loc-2",
        ),
        _craft_done(
            "mill_grain",
            "item-flour",
            tick=1,
            event_id="evt-d1",
            location="loc-2",
        ),
        _harvest(
            "harvest_grain",
            "item-grain",
            tick=32,
            event_id="evt-h2",
            location="loc-2",
        ),
        _craft_start(
            "mill_grain",
            ("item-grain",),
            tick=32,
            event_id="evt-s2",
            location="loc-1",
        ),
        _craft_done(
            "mill_grain",
            "item-flour",
            tick=33,
            event_id="evt-d2",
            location="loc-1",
        ),
    ]


def _claims():
    return (
        SupplyOrganizationClaim("org-a", ("craft",), ("body-1",), 0, 1, 2),
        SupplyOrganizationClaim("org-b", ("harvest",), ("body-1",), 0, 33, 2),
    )


def test_evidence_cap_retains_prefix_and_notice() -> None:
    result = harvest_supply_chain_analysis(
        _events(),
        recipes=_RECIPES,
        policy=SupplyChainAnalysisPolicy(max_evidence_rows=2),
    )
    assert result.stage_count == 2
    assert "evidence_truncated" in result.notices


@pytest.mark.parametrize(
    ("field", "notice"),
    [
        ("max_stages", "stage_truncated"),
        ("max_edges", "edge_truncated"),
        ("max_chains", "chain_truncated"),
        ("max_locations", "location_truncated"),
    ],
)
def test_graph_caps_report_truncation(field: str, notice: str) -> None:
    result = harvest_supply_chain_analysis(
        _events(),
        recipes=_RECIPES,
        policy=SupplyChainAnalysisPolicy(**{field: 1}),
    )
    assert notice in result.notices
    if field == "max_edges":
        assert result.edge_count == 1
    if field == "max_chains":
        assert result.chain_count <= 1
    if field == "max_locations":
        assert result.location_count == 1


def test_organization_cap() -> None:
    result = harvest_supply_chain_analysis(
        _events(),
        recipes=_RECIPES,
        organization_claims=_claims(),
        policy=SupplyChainAnalysisPolicy(max_organizations=1),
    )
    assert result.organization_count == 1
    assert "organization_truncated" in result.notices


def test_lineage_cap() -> None:
    result = harvest_supply_chain_analysis(
        _events(),
        recipes=_RECIPES,
        policy=SupplyChainAnalysisPolicy(max_lineage_edges=1),
    )
    assert len(result.lineage) <= 1
    assert "lineage_truncated" in result.notices


def test_bottleneck_cap() -> None:
    events = [
        _harvest(
            "harvest_grain",
            f"item-g{index}",
            tick=0,
            event_id=f"evt-h{index}",
            location="loc-1",
        )
        for index in range(4)
    ]
    for index in range(4):
        events.append(
            _craft_start(
                "mill_grain",
                (f"item-g{index}",),
                tick=1,
                event_id=f"evt-s{index}",
                location="loc-2",
            )
        )
        events.append(
            _craft_done(
                "mill_grain",
                f"item-f{index}",
                tick=2,
                event_id=f"evt-d{index}",
                location="loc-2",
            )
        )
    result = harvest_supply_chain_analysis(
        events,
        recipes=_RECIPES,
        policy=SupplyChainAnalysisPolicy(max_bottlenecks=1),
    )
    assert result.bottleneck_count == 1
    assert "bottleneck_truncated" in result.notices


def test_default_policy_is_locked() -> None:
    policy = default_supply_chain_analysis_policy()
    assert policy.max_evidence_rows == 200_000
    assert policy.max_stages == 4_096
    assert policy.max_edges == 16_384
    assert policy.max_chains == 4_096
    assert policy.max_bottlenecks == 4_096
    assert policy.max_locations == 4_096
    assert policy.max_organizations == 2_048
    assert policy.max_lineage_edges == 16_384
