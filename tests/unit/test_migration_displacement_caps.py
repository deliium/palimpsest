# mypy: ignore-errors
"""Caps, notices, expiry, and token-only owner export."""

from __future__ import annotations

import ast
import inspect
import logging
import random
import re
from dataclasses import replace
from types import SimpleNamespace

import pytest

from agents.cognition.migration_displacement import (
    CauseEvidenceStatus,
    ClusterStatus,
    IntegrationStatus,
    MigrationDisplacementLedger,
    MigrationIntentStatus,
    RouteBeliefStatus,
    WaveObservationStatus,
    _enforce_caps,
    _expire_rows,
    default_migration_displacement_policy,
    migration_displacement_row_projections,
    validate_migration_displacement_ledger_caps,
)
from simulation import migration_displacement_export as export_module
from simulation.migration_displacement_export import (
    MigrationOwnerExportRow,
    migration_displacement_export_digest,
    migration_displacement_export_notices,
    migration_displacement_owner_export,
)
from tests.unit.migration_displacement_helpers import (
    OWNER,
    PEER,
    A,
    B,
    C,
    D,
    cause,
    cluster,
    integration,
    intent,
    ledger,
    route,
    wave,
)

pytestmark = pytest.mark.unit

POLICY = default_migration_displacement_policy()
TOKEN = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")

# family -> (ledger field, cap, terminal builder, notice code)
_FAMILIES = {
    "intents": (
        8,
        lambda i: intent((A, B), tick=i, status=MigrationIntentStatus.EXPIRED),
        "intent_cap_reached",
    ),
    "routes": (
        16,
        lambda i: route((A, B), tick=i, status=RouteBeliefStatus.EXPIRED),
        "route_cap_reached",
    ),
    "causes": (
        32,
        lambda i: cause(tick=i, status=CauseEvidenceStatus.EXPIRED),
        "cause_cap_reached",
    ),
    "clusters": (
        8,
        lambda i: cluster(tick=i, status=ClusterStatus.DISSOLVED),
        "cluster_cap_reached",
    ),
    "integrations": (
        8,
        lambda i: integration(tick=i, status=IntegrationStatus.UNKNOWN),
        "integration_cap_reached",
    ),
    "waves": (
        8,
        lambda i: wave(tick=i, status=WaveObservationStatus.EXPIRED),
        "wave_cap_reached",
    ),
}


def _rows(family: str, count: int):
    _, build, _ = _FAMILIES[family]
    return tuple(build(index + 1) for index in range(count))


def _with(**families) -> MigrationDisplacementLedger:
    return ledger(**families)


def test_each_family_cap_is_enforced() -> None:
    assert POLICY.max_intents == 8
    assert POLICY.max_route_beliefs == 16
    assert POLICY.max_cause_evidence == 32
    assert POLICY.max_cluster_beliefs == 8
    assert POLICY.max_integration_beliefs == 8
    assert POLICY.max_wave_observations == 8
    assert POLICY.max_ledger_rows == 96
    for family, (cap, _, _) in _FAMILIES.items():
        over = _with(**{family: _rows(family, cap + 3)})
        assert len(getattr(over, family)) == cap + 3
        with pytest.raises(ValueError, match="capacity_reached"):
            validate_migration_displacement_ledger_caps(over)
        bounded = _enforce_caps(over, POLICY, None)
        assert len(getattr(bounded, family)) == cap
        validate_migration_displacement_ledger_caps(bounded)
        # The oldest terminal rows are dropped first; the newest remain.
        kept = sorted(item.first_tick for item in getattr(bounded, family))
        assert kept == list(range(4, cap + 4))
    # Exactly at the cap nothing is dropped and no notice is added.
    at_cap = _with(intents=_rows("intents", 8))
    unchanged = _enforce_caps(at_cap, POLICY, None)
    assert unchanged.intents == at_cap.intents
    assert unchanged.notices == ()
    # The family caps can never exceed the total cap together.
    assert sum(cap for cap, _, _ in _FAMILIES.values()) <= POLICY.max_ledger_rows


def test_total_ledger_cap_is_enforced() -> None:
    limits = dict(
        max_intents=8,
        max_route_beliefs=16,
        max_cause_evidence=32,
        max_cluster_beliefs=8,
        max_integration_beliefs=8,
        max_wave_observations=8,
    )
    tight = SimpleNamespace(max_ledger_rows=10, **limits)
    candidate = _with(
        intents=_rows("intents", 6),
        routes=_rows("routes", 6),
        causes=_rows("causes", 6),
    )
    bounded = _enforce_caps(candidate, tight, None)
    total = len(bounded.intents) + len(bounded.routes) + len(bounded.causes)
    assert total == 10
    assert "truncated" in bounded.notices
    assert _enforce_caps(candidate, tight, None) == bounded
    # The production total cap holds for a maximal ledger.
    full = _with(
        **{family: _rows(family, cap) for family, (cap, _, _) in _FAMILIES.items()}
    )
    full_bounded = _enforce_caps(full, POLICY, None)
    rows = sum(len(getattr(full_bounded, family)) for family in _FAMILIES)
    assert rows == 80
    assert rows <= POLICY.max_ledger_rows
    assert full_bounded.notices == ()
    # Insertion order never changes the retained set.
    shuffled = list(candidate.intents)
    random.Random(7).shuffle(shuffled)
    other = _with(
        intents=tuple(shuffled),
        routes=tuple(reversed(candidate.routes)),
        causes=tuple(reversed(candidate.causes)),
    )
    reordered = _enforce_caps(other, tight, None)
    assert {item.intent_id for item in reordered.intents} == {
        item.intent_id for item in bounded.intents
    }
    assert {item.route_id for item in reordered.routes} == {
        item.route_id for item in bounded.routes
    }
    assert {item.cause_id for item in reordered.causes} == {
        item.cause_id for item in bounded.causes
    }


def test_terminal_rows_are_dropped_before_active_rows() -> None:
    planned = tuple(
        intent((A, B), tick=index, status=MigrationIntentStatus.PLANNED)
        for index in range(10, 18)
    )
    departed = intent((B, C), tick=20, status=MigrationIntentStatus.DEPARTED)
    expired = tuple(
        intent((A, C), tick=index, status=MigrationIntentStatus.EXPIRED)
        for index in range(1, 4)
    )
    abandoned = intent((C, D), tick=5, status=MigrationIntentStatus.ABANDONED)
    candidate = _with(intents=(*planned[:7], departed, *expired, abandoned))
    assert len(candidate.intents) == 12
    bounded = _enforce_caps(candidate, POLICY, None)
    assert len(bounded.intents) == 8
    statuses = [item.status for item in bounded.intents]
    assert statuses.count(MigrationIntentStatus.PLANNED) == 7
    assert statuses.count(MigrationIntentStatus.DEPARTED) == 1
    assert MigrationIntentStatus.EXPIRED not in statuses
    assert MigrationIntentStatus.ABANDONED not in statuses
    assert "intent_cap_reached" in bounded.notices
    # Expired rows go before abandoned rows.
    mixed = _with(intents=(*planned[:6], expired[0], abandoned, expired[1]))
    assert len(mixed.intents) == 9
    trimmed = _enforce_caps(mixed, POLICY, None)
    assert len(trimmed.intents) == 8
    left = sorted(
        (item.status.value, item.first_tick)
        for item in trimmed.intents
        if item.status is not MigrationIntentStatus.PLANNED
    )
    # The oldest expired row goes first; the abandoned row outlives it.
    assert left == [("abandoned", 5), ("expired", 2)]
    # Active rows survive even when only non-terminal non-active rows can go.
    live = tuple(
        intent((A, B), tick=index, status=MigrationIntentStatus.PLANNED)
        for index in range(1, 9)
    )
    considered = intent((A, C), tick=30, status=MigrationIntentStatus.CONSIDERED)
    guarded = _enforce_caps(_with(intents=(*live, considered)), POLICY, None)
    assert {item.intent_id for item in guarded.intents} == {
        item.intent_id for item in live
    }
    assert "ledger_cap_reached" in guarded.notices


def test_no_droppable_row_keeps_prior_ledger_and_notice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    prior_intents = tuple(
        intent((A, B), tick=index, status=MigrationIntentStatus.PLANNED)
        for index in range(1, 9)
    )
    prior = _with(intents=prior_intents)
    candidate = _with(
        intents=(
            *prior_intents,
            intent((A, C), tick=9, status=MigrationIntentStatus.PLANNED),
            intent((A, D), tick=10, status=MigrationIntentStatus.DEPARTED),
        )
    )
    with caplog.at_level(logging.WARNING):
        result = _enforce_caps(candidate, POLICY, prior)
    assert result.intents == prior.intents
    assert "ledger_cap_reached" in result.notices
    assert any(
        "migration_displacement_capacity_reached rows=" in item.message
        for item in caplog.records
    )
    assert not any("loc-" in item.message for item in caplog.records)
    # Without a prior ledger the overflow is still bounded; oldest rows go first.
    fallback = _enforce_caps(candidate, POLICY, None)
    assert len(fallback.intents) == 8
    assert min(item.first_tick for item in fallback.intents) == 3
    assert "ledger_cap_reached" in fallback.notices


def test_truncation_notice_is_family_specific() -> None:
    for family, (cap, _, notice) in _FAMILIES.items():
        bounded = _enforce_caps(_with(**{family: _rows(family, cap + 1)}), POLICY, None)
        assert bounded.notices == (notice,)
    # Two overflowing families emit exactly their own two notices, sorted.
    both = _enforce_caps(
        _with(waves=_rows("waves", 9), clusters=_rows("clusters", 9)), POLICY, None
    )
    assert both.notices == ("cluster_cap_reached", "wave_cap_reached")


def test_expiry_does_not_invent_a_row() -> None:
    empty = _with()
    assert _expire_rows(empty, 10_000, POLICY) is empty
    old_cause = cause(tick=1)
    stale = _with(
        intents=(
            intent(
                (A, B),
                tick=1,
                causes=(old_cause,),
                status=MigrationIntentStatus.PLANNED,
            ),
            intent(
                (B, C),
                tick=190,
                causes=(old_cause,),
                status=MigrationIntentStatus.PLANNED,
            ),
        ),
        routes=(route((A, B), tick=1),),
        causes=(old_cause,),
        clusters=(cluster(tick=1),),
        waves=(wave(tick=1),),
        integrations=(integration(tick=1),),
    )
    expired = _expire_rows(stale, 200, POLICY)
    for field in ("intents", "routes", "causes", "clusters", "integrations", "waves"):
        assert len(getattr(expired, field)) == len(getattr(stale, field))
    by_tick = {item.first_tick: item.status for item in expired.intents}
    assert by_tick[1] is MigrationIntentStatus.EXPIRED
    assert by_tick[190] is MigrationIntentStatus.PLANNED
    assert expired.routes[0].status is RouteBeliefStatus.OPEN
    assert expired.causes[0].status is CauseEvidenceStatus.ACTIVE
    # Rows within their age cap are retained; terminal rows are never revived.
    assert _expire_rows(stale, 5, POLICY) == stale
    terminal = _with(
        intents=(intent((A, B), tick=1, status=MigrationIntentStatus.ABANDONED),)
    )
    assert _expire_rows(terminal, 10_000, POLICY).intents[0].status is (
        MigrationIntentStatus.ABANDONED
    )
    # Expiry never adds a cause, route, cluster, integration, or wave.
    again = _expire_rows(expired, 10_000, POLICY)
    assert len(again.intents) == len(stale.intents)
    assert again.integrations == stale.integrations


def _populated(owner=OWNER, *, tick: int = 1) -> MigrationDisplacementLedger:
    cause_row = cause(tick=tick, owner=owner)
    return ledger(
        owner=owner,
        intents=(intent((A, B, C), causes=(cause_row,), tick=tick, owner=owner),),
        routes=(route((A, B, C), tick=tick, owner=owner),),
        causes=(cause_row,),
        clusters=(
            cluster((owner, PEER if owner == OWNER else OWNER), tick=tick, owner=owner),
        ),
        integrations=(integration(tick=tick, owner=owner),),
        waves=(wave(causes=(cause_row,), tick=tick, owner=owner),),
        notices=("route_unobserved",),
    )


def test_owner_export_is_token_only_and_sorted() -> None:
    first = _populated(OWNER)
    second = _populated(PEER, tick=2)
    rows = migration_displacement_owner_export((first, second))
    assert rows
    assert all(type(item) is MigrationOwnerExportRow for item in rows)
    keys = [
        (item.owner_token, item.family, item.first_tick, item.row_token)
        for item in rows
    ]
    assert keys == sorted(keys)
    assert {item.family for item in rows} == {
        "intent",
        "route",
        "cause",
        "cluster",
        "integration",
        "wave",
        "notice",
    }
    for item in rows:
        for token in (
            item.owner_token,
            item.family,
            item.row_token,
            item.origin_token,
            item.destination_token,
            item.status,
            item.coverage,
            *item.route_tokens,
            *item.cause_tokens,
            *item.cluster_tokens,
        ):
            assert type(token) is str
            assert TOKEN.fullmatch(token)
    text = repr(rows)
    for raw in ("agent-1", "agent-2", "loc-a", "loc-b", "loc-c", "body-1"):
        assert raw not in text
    # Reordering the input never changes the output.
    assert migration_displacement_owner_export((second, first)) == rows
    # The export tokens match the cognition projection for the same ledger.
    own = [item for item in rows if item.owner_token == rows_owner(first, rows)]
    projected = migration_displacement_row_projections(first)
    assert sorted(item.row_token for item in own) == sorted(
        item.row_token for item in projected
    )
    assert migration_displacement_owner_export(()) == ()
    assert migration_displacement_export_notices(rows) == ("route-unobserved",)
    # The export module imports neither cognition nor world identities.
    tree = ast.parse(inspect.getsource(export_module))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [getattr(node, "module", None) or ""] + [
                item.name for item in node.names
            ]
            assert not any(
                name.startswith(("agents", "world", "experiments", "analysis"))
                for name in names
            )


def rows_owner(owner_ledger, rows) -> str:
    projected = {
        item.row_token for item in migration_displacement_row_projections(owner_ledger)
    }
    return next(item.owner_token for item in rows if item.row_token in projected)


def test_export_rejects_duplicate_or_foreign_owner(
    caplog: pytest.LogCaptureFixture,
) -> None:
    first = _populated(OWNER)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(
            ValueError, match="migration_displacement_export: duplicate_owner"
        ):
            migration_displacement_owner_export((first, first))
        with pytest.raises(
            ValueError, match="migration_displacement_export: foreign_owner"
        ):
            migration_displacement_owner_export((first,), allowed_owner_ids={"agent-9"})
        with pytest.raises(
            ValueError, match="migration_displacement_export: foreign_owner"
        ):
            migration_displacement_owner_export((object(),))
    assert not any("agent-1" in item.message for item in caplog.records)
    assert migration_displacement_owner_export((first,), allowed_owner_ids={"agent-1"})
    with pytest.raises(TypeError):
        migration_displacement_owner_export("agent-1")


def test_export_digest_is_stable() -> None:
    first = _populated(OWNER)
    second = _populated(PEER, tick=2)
    rows = migration_displacement_owner_export((first, second))
    digest = migration_displacement_export_digest(rows)
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == migration_displacement_export_digest(rows)
    assert digest == migration_displacement_export_digest(tuple(reversed(rows)))
    assert digest == migration_displacement_export_digest(
        migration_displacement_owner_export((second, first))
    )
    changed = migration_displacement_owner_export(
        (replace(first, notices=("truncated",)), second)
    )
    assert migration_displacement_export_digest(changed) != digest
    assert migration_displacement_export_digest(()) != digest
