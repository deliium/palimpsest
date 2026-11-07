# mypy: ignore-errors
"""Boundary edges are observed adjacency pairs only."""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace

from agents.cognition import borders
from agents.cognition.borders import (
    BorderLedger,
    BoundaryBasis,
    BoundaryRecognition,
    BoundaryStatus,
    DomainClaimStatus,
    TerritorialDomainClaim,
    boundary_edges_for_domain,
    boundary_summary,
    domain_claim_id,
    observe_local_edges,
    unobserved_domain_locations,
)
from agents.models import AgentId
from world.identifiers import EntityId

OWNER = AgentId("agent-1")
LOC_A = EntityId("loc-a")
LOC_B = EntityId("loc-b")
LOC_C = EntityId("loc-c")


def _observation(origin: EntityId, destinations: tuple[EntityId, ...]):
    return SimpleNamespace(
        self_body=SimpleNamespace(location_id=origin),
        exits=[SimpleNamespace(destination_id=item) for item in destinations],
    )


def _domain(
    locations: tuple[EntityId, ...],
    edges: tuple[tuple[str, str], ...] = (),
) -> TerritorialDomainClaim:
    return TerritorialDomainClaim(
        domain_id=domain_claim_id(OWNER, locations),
        owner_id=OWNER,
        location_ids=locations,
        boundary_edges=edges,
        anchor_kind=None,
        anchor_ref=None,
        status=DomainClaimStatus.CLAIMED,
        strength=0.8,
        first_tick=1,
        last_tick=1,
    )


def test_isolated_domain_has_no_edges_and_is_unresolved() -> None:
    assert observe_local_edges(_observation(LOC_A, ())) == ()
    assert boundary_edges_for_domain((LOC_A,), ()) == ()
    assert unobserved_domain_locations((LOC_A,), ()) == (LOC_A,)
    ledger = BorderLedger(
        owner_id=OWNER,
        domains=(_domain((LOC_A,)),),
        recognitions=(
            BoundaryRecognition(
                domain_id=domain_claim_id(OWNER, (LOC_A,)),
                boundary_edges=(),
                basis=BoundaryBasis.OWN_CLAIM,
                status=BoundaryStatus.UNRESOLVED,
            ),
        ),
    )
    summary = boundary_summary(ledger)
    assert summary.unresolved_domain_count == 1
    assert summary.observed_edge_count == 0


def test_two_adjacent_locations_produce_one_canonical_boundary_edge() -> None:
    observed = observe_local_edges(_observation(LOC_A, (LOC_B,)))
    assert observed == ((LOC_A, LOC_B),)
    edges = boundary_edges_for_domain((LOC_A,), observed)
    assert edges == (("loc-a", "loc-b"),)


def test_edges_are_boundary_only_when_one_endpoint_is_in_the_set() -> None:
    observed = ((LOC_A, LOC_B), (LOC_B, LOC_C))
    assert boundary_edges_for_domain((LOC_A, LOC_B), observed) == (("loc-b", "loc-c"),)
    assert boundary_edges_for_domain((LOC_A,), observed) == (("loc-a", "loc-b"),)
    assert boundary_edges_for_domain((LOC_B,), observed) == (
        ("loc-a", "loc-b"),
        ("loc-b", "loc-c"),
    )


def test_prior_observed_edges_are_merged_and_deduplicated() -> None:
    observed = ((LOC_A, LOC_B),)
    local = observe_local_edges(_observation(LOC_B, (LOC_A, LOC_A)))
    assert local == ((LOC_B, LOC_A),)
    merged = list(observed) + list(local)
    assert boundary_edges_for_domain((LOC_A,), merged) == (("loc-a", "loc-b"),)


def test_dispute_wins_over_recognition_for_the_same_edge() -> None:
    domain = _domain((LOC_A, LOC_B), edges=(("loc-a", "loc-c"),))
    edge = ("loc-a", "loc-c")
    ledger = BorderLedger(
        owner_id=OWNER,
        domains=(domain,),
        recognitions=(
            BoundaryRecognition(
                domain_id=domain.domain_id,
                boundary_edges=(edge,),
                basis=BoundaryBasis.DIRECT_OBSERVATION,
                status=BoundaryStatus.RECOGNIZED,
            ),
            BoundaryRecognition(
                domain_id=domain.domain_id,
                boundary_edges=(edge,),
                basis=BoundaryBasis.TESTIMONY,
                status=BoundaryStatus.DISPUTED,
            ),
        ),
    )
    summary = boundary_summary(ledger)
    assert summary.disputed_edge_count == 1
    assert summary.recognized_edge_count == 0


def test_region_membership_is_never_converted_to_a_border() -> None:
    source = inspect.getsource(borders)
    assert "RegionDefinition" not in source
    assert "LocationRegion" not in source


def test_no_grid_coordinate_or_polygon_symbol_is_used() -> None:
    tree = ast.parse(inspect.getsource(borders))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    for symbol in ("grid", "polygon", "coordinate", "latitude", "longitude"):
        assert symbol not in names
        assert symbol not in attributes
