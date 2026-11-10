"""Committed-event reconstruction of bounded production-chain evidence.

This is the only supply-chain analysis module that knows event shapes. It never
reads ``WorldState`` or final inventories, and recipe structure arrives only as
an explicit detached ``SupplyRecipeSpec`` list.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from analysis.supply_chain_contract import (
    NONE_TOKEN,
    SupplyChainError,
    SupplyCoverage,
)
from analysis.supply_chain_policy import (
    SupplyChainAnalysisPolicy,
    window_index_for_tick,
)
from world.events import (
    CraftStarted,
    Dropped,
    Given,
    ItemCrafted,
    ItemStored,
    ResourceHarvested,
    StructureBuilt,
    StructureRepaired,
    Taken,
    Transported,
    WorldEvent,
)

__all__ = [
    "SupplyEvidenceHarvest",
    "SupplyInfrastructureFact",
    "SupplyItemCreation",
    "SupplyOrganizationClaim",
    "SupplyRecipeSpec",
    "SupplySkillLevel",
    "SupplyStageObservation",
    "supply_evidence_from_events",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.supply_chain.events")

_ACTIONS: Final[frozenset[str]] = frozenset(
    {"harvest", "craft", "build", "repair", "store"}
)
_OUTPUT_KINDS: Final[frozenset[str]] = frozenset(
    {"food", "water", "material", "medical", "generic", "tool", "structure", "storage"}
)
_CAUSES: Final[frozenset[str]] = frozenset({"harvest", "craft", "structure", "storage"})


def _text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value:
        raise SupplyChainError("supply_chain_invalid_recipe_spec")
    return value


def _names(values: object) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise SupplyChainError("supply_chain_invalid_recipe_spec")
    ordered: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        ordered.add(value)
    return tuple(sorted(ordered))


@dataclass(frozen=True, slots=True)
class SupplyRecipeSpec:
    """Detached recipe structure. Never a ``ProductionRecipe`` import."""

    recipe_id: str
    action: str
    resource_input_names: tuple[str, ...]
    item_input_names: tuple[str, ...]
    input_kinds: tuple[str, ...]
    output_name: str
    output_kind: str
    skill_domain: str | None = None
    tool_role: str | None = None

    def __post_init__(self) -> None:
        _text("recipe_id", self.recipe_id)
        if self.action not in _ACTIONS:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        object.__setattr__(
            self,
            "resource_input_names",
            _names(self.resource_input_names),
        )
        object.__setattr__(self, "item_input_names", _names(self.item_input_names))
        object.__setattr__(self, "input_kinds", _names(self.input_kinds))
        _text("output_name", self.output_name)
        if self.output_kind not in _OUTPUT_KINDS:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        for field_name in ("skill_domain", "tool_role"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value):
                raise SupplyChainError("supply_chain_invalid_recipe_spec")


@dataclass(frozen=True, slots=True)
class SupplyStageObservation:
    """One observed attempt or completion, never a catalog possibility."""

    tick: int
    sequence: int
    window_index: int
    recipe_id: str
    action: str
    location_token: str
    actor_token: str
    item_names: tuple[str, ...]
    completed: bool
    attempt: bool
    started_success: bool | None
    duration_ticks: int
    created_item_token: str
    cause: str
    item_tokens: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("tick", "sequence", "window_index", "duration_ticks"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 0:
                raise SupplyChainError("supply_chain_invalid_event_order")
        _text("recipe_id", self.recipe_id)
        if self.action not in _ACTIONS:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        _text("location_token", self.location_token)
        _text("actor_token", self.actor_token)
        object.__setattr__(self, "item_names", _names(self.item_names))
        if type(self.completed) is not bool or type(self.attempt) is not bool:
            raise SupplyChainError("supply_chain_invalid_event_order")
        if self.started_success is not None and type(self.started_success) is not bool:
            raise SupplyChainError("supply_chain_invalid_event_order")
        if self.cause not in _CAUSES:
            raise SupplyChainError("supply_chain_invalid_event_order")
        if self.created_item_token != NONE_TOKEN:
            _text("created_item_token", self.created_item_token)


@dataclass(frozen=True, slots=True)
class SupplyItemCreation:
    item_token: str
    recipe_id: str
    location_token: str
    tick: int


@dataclass(frozen=True, slots=True)
class SupplySkillLevel:
    agent_token: str
    domain: str
    level: float

    def __post_init__(self) -> None:
        _text("agent_token", self.agent_token)
        _text("domain", self.domain)
        if (
            isinstance(self.level, bool)
            or not isinstance(self.level, (int, float))
            or self.level < 0.0
            or self.level > 1.0
        ):
            raise SupplyChainError("supply_chain_invalid_recipe_spec")


@dataclass(frozen=True, slots=True)
class SupplyInfrastructureFact:
    location_token: str
    kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        _text("location_token", self.location_token)
        object.__setattr__(self, "kinds", _names(self.kinds))


@dataclass(frozen=True, slots=True)
class SupplyOrganizationClaim:
    """Owner-local organization claim joined only by performer actor token."""

    organization_token: str
    command_kinds: tuple[str, ...]
    actor_tokens: tuple[str, ...]
    first_tick: int | None
    last_tick: int | None
    claim_count: int

    def __post_init__(self) -> None:
        _text("organization_token", self.organization_token)
        object.__setattr__(self, "command_kinds", _names(self.command_kinds))
        object.__setattr__(self, "actor_tokens", _names(self.actor_tokens))
        for value in (self.first_tick, self.last_tick):
            if value is not None and (
                isinstance(value, bool) or type(value) is not int or value < 0
            ):
                raise SupplyChainError("supply_chain_invalid_event_order")
        if (
            isinstance(self.claim_count, bool)
            or type(self.claim_count) is not int
            or self.claim_count < 0
        ):
            raise SupplyChainError("supply_chain_invalid_event_order")


@dataclass(frozen=True, slots=True)
class SupplyEvidenceHarvest:
    rows: tuple[SupplyStageObservation, ...] = ()
    item_creations: tuple[SupplyItemCreation, ...] = ()
    skill_levels: tuple[SupplySkillLevel, ...] = ()
    infrastructure: tuple[SupplyInfrastructureFact, ...] = ()
    organization_claims: tuple[SupplyOrganizationClaim, ...] = ()
    recipes: tuple[SupplyRecipeSpec, ...] = ()
    coverage: SupplyCoverage = SupplyCoverage.MISSING
    skill_coverage: SupplyCoverage = SupplyCoverage.MISSING
    infrastructure_coverage: SupplyCoverage = SupplyCoverage.MISSING
    organization_coverage: SupplyCoverage = SupplyCoverage.MISSING
    notices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for coverage in (
            self.coverage,
            self.skill_coverage,
            self.infrastructure_coverage,
            self.organization_coverage,
        ):
            if type(coverage) is not SupplyCoverage:
                raise SupplyChainError("supply_chain_invalid_policy")

    @property
    def row_count(self) -> int:
        return len(self.rows)


def _event_location(event: WorldEvent, notices: set[str]) -> str:
    occurrence = event.occurrence
    if occurrence is None or occurrence.origin_location_id is None:
        notices.add("unresolved_location")
        return NONE_TOKEN
    return occurrence.origin_location_id.value


def _item_creation(
    event: WorldEvent, details: object, notices: set[str]
) -> SupplyItemCreation | None:
    if isinstance(details, ResourceHarvested) and details.success:
        if details.created_item_id is None:
            return None
        return SupplyItemCreation(
            item_token=details.created_item_id.value,
            recipe_id=details.recipe_id.value,
            location_token=_event_location(event, notices),
            tick=event.tick,
        )
    if isinstance(details, ItemCrafted):
        return SupplyItemCreation(
            item_token=details.created_item_id.value,
            recipe_id=details.recipe_id.value,
            location_token=_event_location(event, notices),
            tick=event.tick,
        )
    return None


def _normalize_skills(values: object) -> tuple[SupplySkillLevel, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise SupplyChainError("supply_chain_invalid_recipe_spec")
    levels: list[SupplySkillLevel] = []
    for value in values:
        if type(value) is SupplySkillLevel:
            levels.append(value)
            continue
        side = getattr(value, "side", None)
        if side is not None and getattr(side, "value", side) != "objective":
            continue
        agent = getattr(value, "agent_id", None)
        token = getattr(agent, "value", agent)
        domain = getattr(value, "domain", None)
        level = getattr(value, "level", None)
        if token is None or domain is None or level is None:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        levels.append(
            SupplySkillLevel(
                agent_token=str(token),
                domain=str(domain),
                level=float(level),
            )
        )
    deduped: dict[tuple[str, str], SupplySkillLevel] = {}
    for level in levels:
        deduped[(level.agent_token, level.domain)] = level
    return tuple(deduped[key] for key in sorted(deduped))


def _normalize_infrastructure(values: object) -> tuple[SupplyInfrastructureFact, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise SupplyChainError("supply_chain_invalid_recipe_spec")
    by_location: dict[str, set[str]] = {}
    for value in values:
        if type(value) is SupplyInfrastructureFact:
            by_location.setdefault(value.location_token, set()).update(value.kinds)
            continue
        status = getattr(value, "status", None)
        if status is not None and getattr(status, "value", status) != "operational":
            continue
        location = getattr(value, "location_token", None) or getattr(
            value, "location_id", None
        )
        token = getattr(location, "value", location)
        kinds = getattr(value, "kinds", None)
        if kinds is None:
            kind = getattr(value, "kind", None)
            kind_value = getattr(kind, "value", kind)
            kinds = () if kind_value in (None, "") else (str(kind_value),)
        if token is None:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        by_location.setdefault(str(token), set()).update(str(kind) for kind in kinds)
    return tuple(
        SupplyInfrastructureFact(
            location_token=location,
            kinds=tuple(sorted(kinds)),
        )
        for location, kinds in sorted(by_location.items())
        if kinds
    )


def _normalize_organizations(values: object) -> tuple[SupplyOrganizationClaim, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise SupplyChainError("supply_chain_invalid_recipe_spec")
    claims: list[SupplyOrganizationClaim] = []
    for value in values:
        if type(value) is SupplyOrganizationClaim:
            claims.append(value)
            continue
        organization = getattr(value, "organization_token", None) or getattr(
            value, "organization_id", None
        )
        if organization is None:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        command_kinds = getattr(value, "command_kinds", None)
        if command_kinds is None:
            command_kind = getattr(value, "command_kind", None)
            command_kinds = () if command_kind is None else (str(command_kind),)
        actor_tokens = getattr(value, "actor_tokens", None)
        if actor_tokens is None:
            actor = getattr(value, "actor_id", None)
            actor_tokens = () if actor is None else (str(actor),)
        claims.append(
            SupplyOrganizationClaim(
                organization_token=str(organization),
                command_kinds=tuple(str(kind) for kind in command_kinds),
                actor_tokens=tuple(str(actor) for actor in actor_tokens),
                first_tick=getattr(value, "first_tick", None),
                last_tick=getattr(value, "last_tick", None),
                claim_count=int(getattr(value, "claim_count", 0)),
            )
        )
    return tuple(sorted(claims, key=lambda claim: claim.organization_token))


def _coverage_for(rows: Sequence[object], notices: set[str]) -> SupplyCoverage:
    if not rows:
        return SupplyCoverage.MISSING
    if notices:
        return SupplyCoverage.PARTIAL
    return SupplyCoverage.COMPLETE


def _optional_coverage(
    values: Sequence[object], notice: str, notices: set[str]
) -> SupplyCoverage:
    if not values:
        notices.add(notice)
        return SupplyCoverage.MISSING
    return SupplyCoverage.COMPLETE


def supply_evidence_from_events(
    events: Sequence[WorldEvent],
    *,
    policy: SupplyChainAnalysisPolicy,
    recipes: Sequence[SupplyRecipeSpec],
    skill_levels: object | None = None,
    infrastructure: object | None = None,
    organization_claims: object | None = None,
) -> SupplyEvidenceHarvest:
    """Reconstruct bounded stage evidence from committed events only."""
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise SupplyChainError("supply_chain_invalid_recipe_spec")
    ordered = sorted(events, key=lambda item: (item.tick, item.sequence))
    seen: set[str] = set()
    for event in ordered:
        token = event.event_id.value
        if token in seen:
            raise SupplyChainError("supply_chain_duplicate_event")
        seen.add(token)

    recipes_by_id: dict[str, SupplyRecipeSpec] = {}
    for recipe in recipes:
        if type(recipe) is not SupplyRecipeSpec:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        if recipe.recipe_id in recipes_by_id:
            raise SupplyChainError("supply_chain_invalid_recipe_spec")
        recipes_by_id[recipe.recipe_id] = recipe

    notices: set[str] = set()
    creations: dict[str, SupplyItemCreation] = {}
    for event in ordered:
        creation = _item_creation(event, event.details, notices)
        if creation is not None:
            creations[creation.item_token] = creation

    item_name_by_id: dict[str, str] = {}
    for creation in creations.values():
        spec = recipes_by_id.get(creation.recipe_id)
        if spec is not None:
            item_name_by_id[creation.item_token] = spec.output_name

    def resolve_names(item_ids: Sequence[object]) -> tuple[str, ...]:
        names: list[str] = []
        for raw in item_ids:
            token = getattr(raw, "value", raw)
            name = item_name_by_id.get(str(token))
            if name is None:
                notices.add("unresolved_item_name")
                names.append(NONE_TOKEN)
            else:
                names.append(name)
        return tuple(names)

    rows: list[SupplyStageObservation] = []
    pending: dict[
        tuple[str, str], list[tuple[int, tuple[str, ...], tuple[str, ...], int]]
    ] = {}
    ignored: set[str] = set()

    for event in ordered:
        details = event.details
        location = _event_location(event, notices)
        actor = NONE_TOKEN if event.actor_id is None else event.actor_id.value
        tick = event.tick
        sequence = event.sequence
        if isinstance(details, ResourceHarvested):
            spec = recipes_by_id.get(details.recipe_id.value)
            if spec is None:
                notices.add("unknown_recipe")
                continue
            rows.append(
                SupplyStageObservation(
                    tick=tick,
                    sequence=sequence,
                    window_index=window_index_for_tick(tick, policy),
                    recipe_id=spec.recipe_id,
                    action=spec.action,
                    location_token=location,
                    actor_token=actor,
                    item_names=(),
                    completed=details.success,
                    attempt=True,
                    started_success=None,
                    duration_ticks=details.duration_ticks,
                    created_item_token=(
                        NONE_TOKEN
                        if details.created_item_id is None
                        else details.created_item_id.value
                    ),
                    cause="harvest",
                )
            )
            continue
        if isinstance(details, CraftStarted):
            spec = recipes_by_id.get(details.recipe_id.value)
            if spec is None:
                notices.add("unknown_recipe")
                continue
            names = resolve_names(details.consumed_item_ids) if details.success else ()
            tokens = (
                tuple(item.value for item in details.consumed_item_ids)
                if details.success
                else ()
            )
            rows.append(
                SupplyStageObservation(
                    tick=tick,
                    sequence=sequence,
                    window_index=window_index_for_tick(tick, policy),
                    recipe_id=spec.recipe_id,
                    action=spec.action,
                    location_token=location,
                    actor_token=actor,
                    item_names=names,
                    completed=False,
                    attempt=True,
                    started_success=details.success,
                    duration_ticks=details.duration_ticks,
                    created_item_token=NONE_TOKEN,
                    cause="craft",
                    item_tokens=tokens,
                )
            )
            if details.success:
                pending.setdefault((actor, spec.recipe_id), []).append(
                    (tick, names, tokens, details.duration_ticks)
                )
            continue
        if isinstance(details, ItemCrafted):
            spec = recipes_by_id.get(details.recipe_id.value)
            if spec is None:
                notices.add("unknown_recipe")
                continue
            holder = details.resulting_holder_id.value
            paired_names: tuple[str, ...] = ()
            paired_tokens: tuple[str, ...] = ()
            duration = details.duration_ticks
            candidates = pending.get((holder, spec.recipe_id), [])
            for index, (
                started_tick,
                started_names,
                started_tokens,
                started_duration,
            ) in enumerate(candidates):
                if started_tick < tick:
                    paired_names = started_names
                    paired_tokens = started_tokens
                    duration = started_duration
                    del candidates[index]
                    break
            else:
                notices.add("unresolved_craft_inputs")
            rows.append(
                SupplyStageObservation(
                    tick=tick,
                    sequence=sequence,
                    window_index=window_index_for_tick(tick, policy),
                    recipe_id=spec.recipe_id,
                    action=spec.action,
                    location_token=location,
                    actor_token=holder,
                    item_names=paired_names,
                    completed=True,
                    attempt=False,
                    started_success=True,
                    duration_ticks=duration,
                    created_item_token=details.created_item_id.value,
                    cause="craft",
                    item_tokens=paired_tokens,
                )
            )
            continue
        if isinstance(details, (StructureBuilt, StructureRepaired)):
            spec = recipes_by_id.get(details.recipe_id.value)
            if spec is None:
                notices.add("unknown_recipe")
                continue
            names = resolve_names((details.consumed_item_id,))
            rows.append(
                SupplyStageObservation(
                    tick=tick,
                    sequence=sequence,
                    window_index=window_index_for_tick(tick, policy),
                    recipe_id=spec.recipe_id,
                    action=spec.action,
                    location_token=location,
                    actor_token=actor,
                    item_names=names,
                    completed=True,
                    attempt=False,
                    started_success=True,
                    duration_ticks=details.duration_ticks,
                    created_item_token=(
                        details.structure_id.value
                        if isinstance(details, StructureBuilt)
                        else NONE_TOKEN
                    ),
                    cause="structure",
                    item_tokens=(details.consumed_item_id.value,),
                )
            )
            continue
        if isinstance(details, ItemStored):
            spec = recipes_by_id.get(details.recipe_id.value)
            if spec is None:
                notices.add("unknown_recipe")
                continue
            names = resolve_names((details.consumed_item_id,))
            rows.append(
                SupplyStageObservation(
                    tick=tick,
                    sequence=sequence,
                    window_index=window_index_for_tick(tick, policy),
                    recipe_id=spec.recipe_id,
                    action=spec.action,
                    location_token=location,
                    actor_token=actor,
                    item_names=names,
                    completed=True,
                    attempt=False,
                    started_success=True,
                    duration_ticks=details.duration_ticks,
                    created_item_token=NONE_TOKEN,
                    cause="storage",
                    item_tokens=(details.consumed_item_id.value,),
                )
            )
            continue
        if isinstance(details, (Given, Taken, Dropped, Transported)):
            continue
        kind = getattr(details, "kind", type(details).__name__)
        if len(ignored) < 20:
            ignored.add(str(kind))
            _LOG.debug("supply_chain_event_ignored event_kind=%s", kind)

    skill_rows = _normalize_skills(skill_levels)
    infra_rows = _normalize_infrastructure(infrastructure)
    organization_rows = _normalize_organizations(organization_claims)
    skill_coverage = _optional_coverage(skill_rows, "missing_skill_levels", notices)
    infrastructure_coverage = _optional_coverage(
        infra_rows, "missing_infrastructure", notices
    )
    organization_coverage = _optional_coverage(
        organization_rows, "missing_organization_claims", notices
    )
    if len(rows) > policy.max_evidence_rows:
        rows = rows[: policy.max_evidence_rows]
        notices.add("evidence_truncated")
        _LOG.warning(
            "supply_chain_evidence_truncated retained=%s cap=%s",
            len(rows),
            policy.max_evidence_rows,
        )
    rows.sort(key=lambda row: (row.tick, row.sequence, row.recipe_id))
    row_tokens_missing = any(
        row.location_token == NONE_TOKEN
        or NONE_TOKEN in row.item_names
        or row.actor_token == NONE_TOKEN
        for row in rows
    )
    if row_tokens_missing:
        notices.add("unresolved_evidence_tokens")
    evidence_coverage = _coverage_for(rows, notices)
    if notices:
        _LOG.warning(
            "supply_chain_evidence_partial notices=%s",
            ",".join(sorted(notices)),
        )
    _LOG.debug(
        "supply_chain_evidence_rows rows=%s windows=%s",
        len(rows),
        len({row.window_index for row in rows}),
    )
    return SupplyEvidenceHarvest(
        rows=tuple(rows),
        item_creations=tuple(creations[token] for token in sorted(creations)),
        skill_levels=skill_rows,
        infrastructure=infra_rows,
        organization_claims=organization_rows,
        recipes=tuple(recipes_by_id[key] for key in sorted(recipes_by_id)),
        coverage=evidence_coverage,
        skill_coverage=skill_coverage,
        infrastructure_coverage=infrastructure_coverage,
        organization_coverage=organization_coverage,
        notices=tuple(sorted(notices)),
    )
