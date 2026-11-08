# mypy: ignore-errors
"""Content-addressed ids, canonical payload, digest, and owner ledgers."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import replace

import pytest

from agents.cognition.migration_displacement import (
    PREFIX_BY_FAMILY,
    ClusterBasis,
    IntegrationDomain,
    MigrationCauseKind,
    MigrationCauseSource,
    MigrationDisplacementLedger,
    canonical_migration_displacement_json,
    canonical_migration_displacement_payload,
    empty_migration_displacement_ledger,
    finalize_migration_displacement_ledger,
    merge_migration_displacement_ledger,
    migration_cause_id,
    migration_cluster_id,
    migration_displacement_ledger_digest,
    migration_integration_id,
    migration_intent_id,
    migration_route_id,
    migration_wave_observation_id,
    require_migration_displacement_digest,
)
from tests.unit.migration_displacement_helpers import (
    OWNER,
    PEER,
    PEER3,
    A,
    B,
    C,
    D,
    cause,
    cluster,
    evidence,
    integration,
    intent,
    ledger,
    route,
    wave,
)

pytestmark = pytest.mark.unit

_HEX32 = re.compile(r"[0-9a-f]{32}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def _full_ledger():
    cause_row = cause(tick=1)
    return ledger(
        intents=(intent(causes=(cause_row,)),),
        routes=(route(),),
        causes=(cause_row,),
        clusters=(cluster(),),
        integrations=(integration(),),
        waves=(wave(causes=(cause_row,)),),
        notices=("route_unobserved",),
    )


def test_empty_ledger_digest_is_stable() -> None:
    first = empty_migration_displacement_ledger(OWNER)
    second = empty_migration_displacement_ledger(OWNER)
    assert first == second
    assert _HEX64.fullmatch(first.digest)
    assert first.digest == migration_displacement_ledger_digest(first)
    assert first.digest != empty_migration_displacement_ledger(PEER).digest
    payload = canonical_migration_displacement_payload(first)
    assert "digest" not in payload
    assert payload["policy_version"] == first.policy_version
    for family in ("intents", "routes", "causes", "clusters", "integrations", "waves"):
        assert payload[family] == []
    assert payload["notices"] == []
    # The digest is a pure function of the canonical JSON text.
    assert json.loads(canonical_migration_displacement_json(first)) == payload


def test_each_row_family_has_a_content_addressed_id() -> None:
    ids = {
        "intent": migration_intent_id(OWNER, (A, B), 1),
        "route": migration_route_id(OWNER, (A, B), 1),
        "cause": migration_cause_id(
            OWNER,
            MigrationCauseKind.RESOURCE_SCARCITY,
            MigrationCauseSource.OWN_NEED,
            None,
            1,
        ),
        "cluster": migration_cluster_id(OWNER, (OWNER, PEER), ClusterBasis.KINSHIP, 1),
        "integration": migration_integration_id(
            OWNER, C, IntegrationDomain.RESIDENCE, 1
        ),
        "wave": migration_wave_observation_id(OWNER, A, B, (OWNER, PEER), 1),
    }
    for family, value in ids.items():
        prefix = PREFIX_BY_FAMILY[family]
        assert value.startswith(prefix)
        assert _HEX32.fullmatch(value[len(prefix) :])
    assert len(set(ids.values())) == len(ids)
    # Equal inputs return equal ids.
    assert ids["intent"] == migration_intent_id(OWNER, (A, B), 1)
    assert ids["route"] == migration_route_id(OWNER, (A, B), 1)
    assert ids["wave"] == migration_wave_observation_id(OWNER, A, B, (OWNER, PEER), 1)


def test_changed_input_changes_id() -> None:
    base = migration_intent_id(OWNER, (A, B), 1)
    assert migration_intent_id(OWNER, (A, B), 2) != base
    assert migration_intent_id(OWNER, (A, C), 1) != base
    assert migration_intent_id(OWNER, (B, A), 1) != base
    assert migration_intent_id(PEER, (A, B), 1) != base
    assert migration_route_id(OWNER, (A, B, C), 1) != migration_route_id(
        OWNER, (A, B, D), 1
    )
    cause_args = (
        OWNER,
        MigrationCauseKind.RESOURCE_SCARCITY,
        MigrationCauseSource.OWN_NEED,
        "organization:org-1",
        1,
    )
    cause_base = migration_cause_id(*cause_args)
    assert (
        migration_cause_id(
            OWNER,
            MigrationCauseKind.CONFLICT,
            MigrationCauseSource.OWN_NEED,
            "organization:org-1",
            1,
        )
        != cause_base
    )
    assert (
        migration_cause_id(
            OWNER,
            MigrationCauseKind.RESOURCE_SCARCITY,
            MigrationCauseSource.OWN_NEED,
            "organization:org-2",
            1,
        )
        != cause_base
    )
    assert migration_integration_id(
        OWNER, C, IntegrationDomain.RESIDENCE, 1
    ) != migration_integration_id(OWNER, C, IntegrationDomain.NEEDS, 1)
    assert migration_wave_observation_id(
        OWNER, A, B, (OWNER, PEER), 1
    ) != migration_wave_observation_id(OWNER, A, B, (OWNER, PEER3), 1)
    assert migration_cluster_id(
        OWNER, (OWNER, PEER), ClusterBasis.KINSHIP, 1
    ) != migration_cluster_id(OWNER, (OWNER, PEER), ClusterBasis.COMMUNICATION, 1)


def test_canonical_order_is_independent_of_insertion_order() -> None:
    first_cause = cause(tick=1)
    second_cause = cause(MigrationCauseKind.CONFLICT, tick=4)
    intents = (
        intent((A, B), causes=(first_cause,), tick=5),
        intent((A, C), causes=(first_cause,), tick=2),
        intent((B, C), causes=(second_cause,), tick=2),
    )
    routes = (route((A, B), tick=3), route((A, C), tick=1), route((B, C), tick=3))
    forward = ledger(
        intents=intents,
        routes=routes,
        causes=(first_cause, second_cause),
        notices=("truncated", "route_unobserved"),
    )
    reverse = ledger(
        intents=tuple(reversed(intents)),
        routes=tuple(reversed(routes)),
        causes=(second_cause, first_cause),
        notices=("route_unobserved", "truncated"),
    )
    assert forward.digest == reverse.digest
    assert canonical_migration_displacement_json(
        forward
    ) == canonical_migration_displacement_json(reverse)
    payload = canonical_migration_displacement_payload(forward)
    for family in ("intents", "routes", "causes"):
        keys = [(item["first_tick"], item["id"]) for item in payload[family]]
        assert keys == sorted(keys)
    assert payload["notices"] == ["route_unobserved", "truncated"]
    # A changed confidence or route changes the digest.
    changed_confidence = ledger(
        intents=(replace(intents[0], confidence=0.7), *intents[1:]),
        routes=routes,
        causes=(first_cause, second_cause),
        notices=("truncated", "route_unobserved"),
    )
    assert changed_confidence.digest != forward.digest
    changed_route = ledger(
        intents=intents,
        routes=(route((A, B, C), tick=3), *routes[1:]),
        causes=(first_cause, second_cause),
        notices=("truncated", "route_unobserved"),
    )
    assert changed_route.digest != forward.digest


def test_canonical_payload_contains_no_raw_identifiers() -> None:
    cause_row = replace(
        cause(
            MigrationCauseKind.INSTITUTION,
            MigrationCauseSource.INSTITUTION_BELIEF,
            anchor="institution:inst-raw-1",
        ),
        evidence=(evidence(1, "lineage-raw-1", owner=PEER),),
    )
    full = ledger(
        intents=(intent(causes=(cause_row,)),),
        routes=(route(),),
        causes=(cause_row,),
        clusters=(cluster((OWNER, PEER, PEER3)),),
        integrations=(integration(),),
        waves=(wave(causes=(cause_row,)),),
    )
    text = canonical_migration_displacement_json(full)
    assert text.isascii()
    for raw in (
        "agent-1",
        "agent-2",
        "agent-3",
        "loc-a",
        "loc-b",
        "loc-c",
        "inst-raw-1",
        "lineage-raw-1",
    ):
        assert raw not in text
    payload = canonical_migration_displacement_payload(full)
    assert payload["owner_id"].startswith("mdo-")
    assert "digest" not in payload


def test_digest_mismatch_is_rejected(caplog: pytest.LogCaptureFixture) -> None:
    good = _full_ledger()
    require_migration_displacement_digest(good)
    tampered = replace(good, digest="0" * 64)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError, match="migration_displacement: digest_mismatch"):
            require_migration_displacement_digest(tampered)
    assert any(
        "migration_displacement_digest_mismatch" in item.message
        for item in caplog.records
    )
    # Only metadata is logged.
    assert all("agent-1" not in item.message for item in caplog.records)
    stale = replace(good, notices=("truncated",))
    with pytest.raises(ValueError, match="digest_mismatch"):
        require_migration_displacement_digest(stale)
    assert finalize_migration_displacement_ledger(stale).digest != good.digest
    refreshed = finalize_migration_displacement_ledger(stale)
    require_migration_displacement_digest(refreshed)
    with pytest.raises(ValueError):
        MigrationDisplacementLedger(owner_id=OWNER, digest="not-a-digest")


def test_merge_preserves_owner_and_order() -> None:
    first_cause = cause(tick=1)
    prior = ledger(
        intents=(intent((A, B), causes=(first_cause,), tick=1),),
        causes=(first_cause,),
        notices=("route_unobserved",),
    )
    updated = ledger(
        intents=(intent((A, C), causes=(first_cause,), tick=2),),
        routes=(route((A, C), tick=2),),
        causes=(first_cause,),
        notices=("truncated",),
    )
    merged = merge_migration_displacement_ledger(prior, updated)
    assert merged.owner_id == OWNER
    assert len(merged.intents) == 2
    assert len(merged.causes) == 1
    assert len(merged.routes) == 1
    assert merged.notices == ("route_unobserved", "truncated")
    assert merged.digest == migration_displacement_ledger_digest(merged)
    require_migration_displacement_digest(merged)
    reversed_merge = merge_migration_displacement_ledger(updated, prior)
    assert reversed_merge.digest == merged.digest
    # Updated rows win for an identical id.
    changed = replace(prior.intents[0], confidence=0.9)
    winner = merge_migration_displacement_ledger(
        prior, ledger(intents=(changed,), causes=(first_cause,))
    )
    assert winner.intents[0].confidence == 0.9
    with pytest.raises(ValueError, match="foreign_owner"):
        merge_migration_displacement_ledger(
            prior, empty_migration_displacement_ledger(PEER)
        )
    with pytest.raises(ValueError):
        merge_migration_displacement_ledger(prior, object())
