"""Reconstruct committed possession and access evidence for inequality.

Only committed ``WorldEvent`` values are read. No ``WorldState``, inventory
object, runtime, store, or API object is consulted. Custody is reconstructed
from effect-complete committed transitions; access is physical presence at the
owner's last observed location plus operational infrastructure, store
structures, and repositories. Access is never permission.

Unknown recipe mappings, kinds, or locations stay explicit: an unknown item
kind is excluded from tool counts, and an owner without a location is excluded
from access counts rather than guessed.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from analysis.economic_inequality_contract import (
    EconomicInequalityCoverage,
    EconomicInequalityError,
    economic_inequality_owner_token,
)
from analysis.economic_inequality_policy import (
    EconomicInequalityAnalysisPolicy,
    default_economic_inequality_analysis_policy,
)
from analysis.economic_inequality_rows import (
    EconomicAccessRow,
    EconomicPossessionRow,
)
from world.events import (
    CraftStarted,
    Dropped,
    Eaten,
    ExchangeCompleted,
    Given,
    InfrastructureConstructed,
    InfrastructureDamaged,
    InfrastructureDecayed,
    InfrastructureDestroyed,
    InfrastructureRepaired,
    ItemCrafted,
    ItemStored,
    Moved,
    RepositoryEstablished,
    ResourceHarvested,
    StructureBuilt,
    StructureRepaired,
    Taken,
    WorldEvent,
)
from world.infrastructure import (
    InfrastructureKind,
    InfrastructureStatus,
    effects_active,
)
from world.values import ItemKind

__all__ = [
    "EconomicEvidenceHarvest",
    "harvest_economic_inequality_evidence",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.economic_inequality.events"
)

_INFRASTRUCTURE_EVENTS: Final[tuple[type, ...]] = (
    InfrastructureConstructed,
    InfrastructureRepaired,
    InfrastructureDamaged,
    InfrastructureDecayed,
    InfrastructureDestroyed,
)


@dataclass(frozen=True, slots=True)
class EconomicEvidenceHarvest:
    """Bounded objective evidence plus explicit coverage and notices."""

    possession_rows: tuple[EconomicPossessionRow, ...] = ()
    access_rows: tuple[EconomicAccessRow, ...] = ()
    notices: tuple[str, ...] = ()
    coverage: EconomicInequalityCoverage = EconomicInequalityCoverage.MISSING
    event_count: int = 0
    owner_count: int = 0
    unknown_kind_count: int = 0
    missing_location_count: int = 0

    def __post_init__(self) -> None:
        for name in ("possession_rows", "access_rows", "notices"):
            value = getattr(self, name)
            if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
                raise EconomicInequalityError("economic_inequality_invalid_row")
        if type(self.coverage) is not EconomicInequalityCoverage:
            raise EconomicInequalityError("economic_inequality_invalid_row")
        for name in (
            "event_count",
            "owner_count",
            "unknown_kind_count",
            "missing_location_count",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise EconomicInequalityError("economic_inequality_invalid_row")


def _entity(value: object) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", None)


def _sorted_events(events: Sequence[WorldEvent]) -> tuple[WorldEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise EconomicInequalityError("economic_inequality_invalid_input")
    for event in events:
        if type(event) is not WorldEvent:
            raise EconomicInequalityError("economic_inequality_invalid_input")
    return tuple(sorted(events, key=lambda event: (event.tick, event.sequence)))


def _snapshot(
    *,
    window_index: int,
    tick: int,
    owners: Sequence[str],
    item_holder: Mapping[str, str],
    item_kind: Mapping[str, str],
    owner_location: Mapping[str, str],
    infra_by_location: Mapping[str, int],
    storage_by_location: Mapping[str, set[str]],
) -> tuple[
    int,
    dict[str, tuple[int, int, int]],
    dict[str, tuple[int, int, bool]],
]:
    possession: dict[str, tuple[int, int, int]] = {}
    access: dict[str, tuple[int, int, bool]] = {}
    for owner in owners:
        held = sorted(
            item for item, holder in item_holder.items() if holder == owner
        )
        tool_count = sum(
            1 for item in held if item_kind.get(item) == ItemKind.TOOL.value
        )
        unknown_count = sum(
            1 for item in held if item_kind.get(item, "unknown") == "unknown"
        )
        possession[owner] = (len(held), tool_count, unknown_count)
        location = owner_location.get(owner)
        if location is None:
            access[owner] = (0, 0, False)
        else:
            access[owner] = (
                infra_by_location.get(location, 0),
                len(storage_by_location.get(location, ())),
                True,
            )
    return tick, possession, access


def harvest_economic_inequality_evidence(
    events: Sequence[WorldEvent],
    *,
    policy: EconomicInequalityAnalysisPolicy | None = None,
    recipe_output_kinds: Mapping[str, str] | None = None,
    recipe_structure_kinds: Mapping[str, str] | None = None,
) -> EconomicEvidenceHarvest:
    """Harvest bounded objective possession and access rows."""

    active = (
        default_economic_inequality_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not EconomicInequalityAnalysisPolicy:
        raise EconomicInequalityError("economic_inequality_invalid_policy")
    ordered = _sorted_events(events)
    notices: list[str] = []
    coverage = EconomicInequalityCoverage.COMPLETE
    if len(ordered) > active.max_event_rows:
        ordered = ordered[: active.max_event_rows]
        notices.append("economic_inequality_events_truncated")
        coverage = EconomicInequalityCoverage.PARTIAL

    output_kinds = dict(recipe_output_kinds or {})
    structure_kinds = dict(recipe_structure_kinds or {})

    item_holder: dict[str, str] = {}
    item_kind: dict[str, str] = {}
    owner_location: dict[str, str] = {}
    observed_owners: set[str] = set()
    infra: dict[str, tuple[str, str, float, str]] = {}
    storage_assets: dict[str, str] = {}
    structure_asset_kind: dict[str, str] = {}
    unknown_kind_count = 0
    missing_location_count = 0

    # window index -> (tick, possession, access) at that window's last event.
    snapshots: dict[
        int,
        tuple[
            int,
            dict[str, tuple[int, int, int]],
            dict[str, tuple[int, int, bool]],
        ],
    ] = {}
    current_window: int | None = None

    def snapshot_window(window_index: int, tick: int) -> None:
        owners = sorted(observed_owners)
        if len(owners) > active.max_owners:
            owners = owners[: active.max_owners]
        infra_by_location: dict[str, int] = {}
        for kind_name, status_name, integrity, location_id in infra.values():
            try:
                if effects_active(
                    status=InfrastructureStatus(status_name),
                    integrity=integrity,
                    kind=InfrastructureKind(kind_name),
                ):
                    infra_by_location[location_id] = (
                        infra_by_location.get(location_id, 0) + 1
                    )
            except (ValueError, TypeError):
                notices.append("economic_inequality_unknown_infrastructure_kind")
        storage_by_location: dict[str, set[str]] = {}
        for asset_key, location_id in storage_assets.items():
            storage_by_location.setdefault(location_id, set()).add(asset_key)
        snapshots[window_index] = _snapshot(
            window_index=window_index,
            tick=tick,
            owners=owners,
            item_holder=item_holder,
            item_kind=item_kind,
            owner_location=owner_location,
            infra_by_location=infra_by_location,
            storage_by_location=storage_by_location,
        )

    for event in ordered:
        tick = event.tick
        window_index = min(
            tick // active.window_ticks, active.max_windows - 1
        )
        if current_window is None:
            current_window = window_index
        elif window_index != current_window:
            snapshot_tick = min(
                tick - 1,
                (current_window + 1) * active.window_ticks - 1,
            )
            snapshot_window(
                current_window,
                max(snapshot_tick, current_window * active.window_ticks),
            )
            current_window = window_index

        actor = _entity(event.actor_id)
        if actor:
            observed_owners.add(actor)
        occurrence = event.occurrence
        if occurrence is not None:
            actor_location = _entity(occurrence.origin_location_id)
            if actor and actor_location:
                owner_location[actor] = actor_location
        details = event.details

        if isinstance(details, ItemCrafted):
            holder = details.resulting_holder_id.value
            kind = output_kinds.get(details.recipe_id.value)
            item_holder[details.created_item_id.value] = holder
            item_kind[details.created_item_id.value] = kind or "unknown"
            if kind is None:
                unknown_kind_count += 1
            observed_owners.add(holder)
            location = owner_location.get(actor or "")
            if location:
                owner_location.setdefault(holder, location)
        elif isinstance(details, Taken):
            taken_holder = _entity(details.resulting_holder_id)
            if taken_holder:
                item_holder[details.item_id.value] = taken_holder
                item_kind.setdefault(details.item_id.value, "unknown")
                observed_owners.add(taken_holder)
        elif isinstance(details, Given):
            given_holder = _entity(details.resulting_holder_id) or _entity(
                details.recipient_id
            )
            if given_holder:
                item_holder[details.item_id.value] = given_holder
                item_kind.setdefault(details.item_id.value, "unknown")
                observed_owners.add(given_holder)
            else:
                item_holder.pop(details.item_id.value, None)
        elif isinstance(details, ExchangeCompleted):
            actor_id = details.actor_id.value
            counterparty = details.counterparty_id.value
            for index, item in enumerate(details.give_item_ids):
                kind = (
                    details.give_item_kinds[index]
                    if index < len(details.give_item_kinds)
                    else None
                )
                item_holder[item.value] = counterparty
                item_kind[item.value] = kind or "unknown"
                if kind is None:
                    unknown_kind_count += 1
            for index, item in enumerate(details.take_item_ids):
                kind = (
                    details.take_item_kinds[index]
                    if index < len(details.take_item_kinds)
                    else None
                )
                item_holder[item.value] = actor_id
                item_kind[item.value] = kind or "unknown"
                if kind is None:
                    unknown_kind_count += 1
            observed_owners.update({actor_id, counterparty})
        elif isinstance(details, Dropped):
            item_holder.pop(details.item_id.value, None)
        elif isinstance(details, ItemStored):
            item_holder.pop(details.consumed_item_id.value, None)
        elif isinstance(details, Eaten):
            item_holder.pop(details.item_id.value, None)
        elif isinstance(details, CraftStarted):
            for item in details.consumed_item_ids:
                item_holder.pop(item.value, None)
        elif isinstance(details, (StructureBuilt, StructureRepaired)):
            item_holder.pop(details.consumed_item_id.value, None)
        elif isinstance(details, ResourceHarvested):
            created = _entity(details.created_item_id)
            if created and actor:
                item_holder[created] = actor
                kind = output_kinds.get(details.recipe_id.value)
                item_kind[created] = kind or "unknown"
                if kind is None:
                    unknown_kind_count += 1
        elif isinstance(details, Moved):
            destination = _entity(details.resulting_location_id) or _entity(
                details.destination_id
            )
            if actor and destination:
                owner_location[actor] = destination
        elif isinstance(details, RepositoryEstablished):
            location_id = details.location_id.value
            structure_id = _entity(details.structure_id)
            if structure_id and structure_id in structure_asset_kind:
                storage_assets[structure_id] = location_id
            else:
                storage_assets[
                    f"repository:{details.repository_id.value}"
                ] = location_id

        if isinstance(details, _INFRASTRUCTURE_EVENTS):
            asset = cast(Any, details)
            kind_name = asset.asset_kind
            try:
                kind = InfrastructureKind(kind_name)
                status = InfrastructureStatus(asset.status)
            except ValueError:
                _LOG.warning(
                    "economic_inequality_invalid_infrastructure_kind kind=%s",
                    kind_name,
                )
                notices.append(
                    "economic_inequality_unknown_infrastructure_kind"
                )
                continue
            infra[asset.asset_id.value] = (
                kind.value,
                status.value,
                asset.integrity,
                asset.location_id.value,
            )
        elif isinstance(details, StructureBuilt):
            kind_name = structure_kinds.get(details.recipe_id.value)
            if kind_name:
                structure_asset_kind[details.structure_id.value] = kind_name
                if kind_name == "store":
                    storage_assets[details.structure_id.value] = (
                        details.location_id.value
                    )
            elif details.structure_id.value not in structure_asset_kind:
                structure_asset_kind[details.structure_id.value] = "unknown"
                notices.append("economic_inequality_unknown_structure_kind")

    if current_window is not None:
        snapshot_window(current_window, ordered[-1].tick)

    if not observed_owners and not item_holder:
        _LOG.debug("economic_inequality_events_empty events=%d", len(ordered))
        return EconomicEvidenceHarvest(
            notices=tuple(dict.fromkeys(notices)),
            coverage=coverage,
            event_count=len(ordered),
        )

    owners = sorted(observed_owners)
    if len(owners) > active.max_owners:
        owners = owners[: active.max_owners]
        notices.append("economic_inequality_owners_truncated")
        coverage = EconomicInequalityCoverage.PARTIAL

    possession_rows: list[EconomicPossessionRow] = []
    access_rows: list[EconomicAccessRow] = []
    for window_index in sorted(snapshots):
        window_tick, possession, access = snapshots[window_index]
        for owner in owners:
            if owner not in possession:
                continue
            token = economic_inequality_owner_token(owner)
            item_count, tool_count, unknown_count = possession[owner]
            possession_rows.append(
                EconomicPossessionRow(
                    owner_token=token,
                    tick=window_tick,
                    window_index=window_index,
                    observed_item_count=item_count,
                    observed_tool_count=tool_count,
                    unknown_kind_count=unknown_count,
                )
            )
            infra_count, storage_count, location_known = access[owner]
            if not location_known:
                missing_location_count += 1
                coverage = EconomicInequalityCoverage.PARTIAL
            access_rows.append(
                EconomicAccessRow(
                    owner_token=token,
                    tick=window_tick,
                    window_index=window_index,
                    accessible_infrastructure_count=infra_count,
                    accessible_storage_count=storage_count,
                    location_known=location_known,
                )
            )

    if unknown_kind_count:
        notices.append("economic_inequality_unknown_item_kind")
        _LOG.warning(
            "economic_inequality_unknown_item_kind count=%d", unknown_kind_count
        )
    if missing_location_count:
        notices.append("economic_inequality_missing_location")
        _LOG.warning(
            "economic_inequality_missing_location count=%d",
            missing_location_count,
        )

    possession_rows.sort(key=lambda row: (row.tick, row.owner_token))
    access_rows.sort(key=lambda row: (row.tick, row.owner_token))

    _LOG.debug(
        "economic_inequality_events_harvested events=%d owners=%d "
        "possession_rows=%d access_rows=%d unknown_kinds=%d",
        len(ordered),
        len(owners),
        len(possession_rows),
        len(access_rows),
        unknown_kind_count,
    )
    return EconomicEvidenceHarvest(
        possession_rows=tuple(possession_rows),
        access_rows=tuple(access_rows),
        notices=tuple(dict.fromkeys(notices)),
        coverage=coverage,
        event_count=len(ordered),
        owner_count=len(owners),
        unknown_kind_count=unknown_kind_count,
        missing_location_count=missing_location_count,
    )
