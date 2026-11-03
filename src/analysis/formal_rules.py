"""Detached formal-rule rows harvested from exported owner ledgers.

Rows are owner-valued and read-only. Harvesting never mutates a ledger, never
mints an analytical identity, and never reads cognition, world state, events, or
commands.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, cast

from analysis.formal_rule_contract import (
    FORMAL_RULE_MAX_HARVEST_RULES,
    FormalRuleAnalysisError,
)

__all__ = [
    "FormalRuleEvidenceRow",
    "FormalRuleHarvestRows",
    "FormalRuleOwnerRow",
    "FormalRulePositionRow",
    "FormalRuleResponseRow",
    "FormalRuleRow",
    "FormalRuleSystemRow",
    "FormalRuleVersionRow",
    "harvest_formal_rule_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.formal_rules")


def _fail() -> None:
    raise FormalRuleAnalysisError("formal_rule_harvest_invalid")


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail()
    return cast(str, value)


def _enum_value(value: object) -> str:
    token = getattr(value, "value", None)
    if not isinstance(token, str) or not token:
        _fail()
    return cast(str, token)


def _tick(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _fail()
    return cast(int, value)


def _token(value: object, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if type(value) is not str or not value:
        _fail()
    return cast(str, value)


def _owner_value(value: object) -> str:
    token = getattr(value, "value", None)
    if not isinstance(token, str) or not token:
        _fail()
    return cast(str, token)


@dataclass(frozen=True, slots=True)
class FormalRuleOwnerRow:
    owner_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text(self.owner_id))


@dataclass(frozen=True, slots=True)
class FormalRuleSystemRow:
    owner_id: str
    system_id: str
    scope_kind: str
    scope_digest: str
    authority_kind: str
    rule_ids: tuple[str, ...]
    status: str
    competing_system_ids: tuple[str, ...]
    first_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "owner_id", _text(self.owner_id))
        object.__setattr__(self, "system_id", _text(self.system_id))
        object.__setattr__(self, "scope_kind", _text(self.scope_kind))
        object.__setattr__(self, "scope_digest", _text(self.scope_digest))
        object.__setattr__(self, "authority_kind", _text(self.authority_kind))
        object.__setattr__(self, "rule_ids", tuple(sorted(set(self.rule_ids))))
        object.__setattr__(self, "status", _text(self.status))
        object.__setattr__(
            self,
            "competing_system_ids",
            tuple(sorted(set(self.competing_system_ids))),
        )
        object.__setattr__(self, "first_tick", _tick(self.first_tick))
        object.__setattr__(self, "last_tick", _tick(self.last_tick))


@dataclass(frozen=True, slots=True)
class FormalRuleRow:
    owner_id: str
    rule_id: str
    system_id: str
    stage: str
    constraint_kind: str
    action_token: str
    scope_kind: str
    scope_digest: str
    authority_kind: str
    recognition: str
    status: str
    strength: float
    version_count: int
    written_status: str
    sanction_kinds: tuple[str, ...]
    exception_count: int

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "rule_id",
            "system_id",
            "stage",
            "constraint_kind",
            "action_token",
            "scope_kind",
            "scope_digest",
            "authority_kind",
            "recognition",
            "status",
            "written_status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        if type(self.strength) is not float:
            _fail()
        if self.version_count < 1 or self.exception_count < 0:
            _fail()
        object.__setattr__(
            self, "sanction_kinds", tuple(sorted(set(self.sanction_kinds)))
        )


@dataclass(frozen=True, slots=True)
class FormalRuleVersionRow:
    owner_id: str
    rule_id: str
    version_id: str
    version_number: int
    stage: str
    constraint_kind: str
    scope_kind: str
    scope_digest: str
    action_token: str
    authority_kind: str
    recognition: str
    written_status: str
    tick: int
    revision_kind: str

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "rule_id",
            "version_id",
            "stage",
            "constraint_kind",
            "scope_kind",
            "scope_digest",
            "action_token",
            "authority_kind",
            "recognition",
            "written_status",
            "revision_kind",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "version_number", _tick(self.version_number))
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class FormalRulePositionRow:
    owner_id: str
    rule_id: str
    position_id: str
    actor_id: str
    stance: str
    provenance: str
    tick: int

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "rule_id",
            "position_id",
            "actor_id",
            "stance",
            "provenance",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class FormalRuleResponseRow:
    owner_id: str
    rule_id: str
    response_id: str
    actor_id: str
    kind: str
    provenance: str
    tick: int

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "rule_id",
            "response_id",
            "actor_id",
            "kind",
            "provenance",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "tick", _tick(self.tick))


@dataclass(frozen=True, slots=True)
class FormalRuleEvidenceRow:
    owner_id: str
    rule_id: str
    evidence_id: str
    channel: str
    provenance: str
    tick: int
    artifact_present: bool
    repository_present: bool

    def __post_init__(self) -> None:
        for name in (
            "owner_id",
            "rule_id",
            "evidence_id",
            "channel",
            "provenance",
        ):
            object.__setattr__(self, name, _text(getattr(self, name)))
        object.__setattr__(self, "tick", _tick(self.tick))
        if type(self.artifact_present) is not bool:
            _fail()
        if type(self.repository_present) is not bool:
            _fail()


@dataclass(frozen=True, slots=True)
class FormalRuleHarvestRows:
    owners: tuple[FormalRuleOwnerRow, ...] = ()
    systems: tuple[FormalRuleSystemRow, ...] = ()
    rules: tuple[FormalRuleRow, ...] = ()
    versions: tuple[FormalRuleVersionRow, ...] = ()
    positions: tuple[FormalRulePositionRow, ...] = ()
    responses: tuple[FormalRuleResponseRow, ...] = ()
    evidence: tuple[FormalRuleEvidenceRow, ...] = ()
    window_ticks: int = 100

    def __post_init__(self) -> None:
        if type(self.window_ticks) is not int or self.window_ticks < 1:
            _fail()
        for name in (
            "owners",
            "systems",
            "rules",
            "versions",
            "positions",
            "responses",
            "evidence",
        ):
            values = tuple(getattr(self, name))
            if len(set(map(id, values))) != len(values):
                _fail()
            object.__setattr__(self, name, values)


def _ledger_owner(ledger: object) -> str:
    return _owner_value(getattr(ledger, "owner_id", None))


def harvest_formal_rule_rows(
    ledgers: Sequence[object],
    *,
    window_ticks: int,
) -> FormalRuleHarvestRows:
    """Normalize exported ledgers into sorted, duplicate-free detached rows."""

    if type(window_ticks) is not int or window_ticks < 1:
        _fail()
    if isinstance(ledgers, (str, bytes)) or not isinstance(ledgers, Sequence):
        _fail()
    owners: list[FormalRuleOwnerRow] = []
    systems: list[FormalRuleSystemRow] = []
    rules: list[FormalRuleRow] = []
    versions: list[FormalRuleVersionRow] = []
    positions: list[FormalRulePositionRow] = []
    responses: list[FormalRuleResponseRow] = []
    evidence: list[FormalRuleEvidenceRow] = []
    seen_owners: set[str] = set()
    seen_rules: set[str] = set()
    for ledger in ledgers:
        owner_id = _ledger_owner(ledger)
        if owner_id in seen_owners:
            _fail()
        seen_owners.add(owner_id)
        owners.append(FormalRuleOwnerRow(owner_id=owner_id))
        for system in getattr(ledger, "systems", ()) or ():
            scope = getattr(system, "scope", None)
            systems.append(
                FormalRuleSystemRow(
                    owner_id=owner_id,
                    system_id=_text(getattr(system, "system_id", None)),
                    scope_kind=_enum_value(getattr(scope, "kind", None)),
                    scope_digest=_text(getattr(scope, "digest", None)),
                    authority_kind=_enum_value(getattr(system, "authority", None)),
                    rule_ids=tuple(
                        sorted(
                            _text(rule_id)
                            for rule_id in getattr(system, "rule_ids", ())
                        )
                    ),
                    status=_enum_value(getattr(system, "status", None)),
                    competing_system_ids=tuple(
                        sorted(
                            _text(system_id)
                            for system_id in getattr(
                                system, "competing_system_ids", ()
                            )
                        )
                    ),
                    first_tick=_tick(getattr(system, "first_tick", None)),
                    last_tick=_tick(getattr(system, "last_tick", None)),
                )
            )
        for rule in getattr(ledger, "rules", ()) or ():
            rule_id = _text(getattr(rule, "rule_id", None))
            if rule_id in seen_rules:
                _fail()
            seen_rules.add(rule_id)
            if len(rules) >= FORMAL_RULE_MAX_HARVEST_RULES:
                _fail()
            rule_versions = tuple(getattr(rule, "versions", ()) or ())
            if not rule_versions:
                _fail()
            last_version = rule_versions[-1]
            written = getattr(last_version, "written", None)
            scope = getattr(rule, "scope", None)
            rules.append(
                FormalRuleRow(
                    owner_id=owner_id,
                    rule_id=rule_id,
                    system_id=_text(getattr(rule, "system_id", None)),
                    stage=_enum_value(getattr(rule, "stage", None)),
                    constraint_kind=_enum_value(getattr(rule, "constraint", None)),
                    action_token=_text(getattr(rule, "action_token", None)),
                    scope_kind=_enum_value(getattr(scope, "kind", None)),
                    scope_digest=_text(getattr(scope, "digest", None)),
                    authority_kind=_enum_value(getattr(rule, "authority", None)),
                    recognition=_enum_value(getattr(rule, "recognition", None)),
                    status=_enum_value(getattr(rule, "status", None)),
                    strength=float(getattr(rule, "strength", 0.0)),
                    version_count=len(rule_versions),
                    written_status=(
                        "none"
                        if written is None
                        else _enum_value(getattr(written, "status", None))
                    ),
                    sanction_kinds=tuple(
                        sorted(
                            _enum_value(getattr(item, "kind", None))
                            for item in getattr(rule, "sanctions", ()) or ()
                        )
                    ),
                    exception_count=len(getattr(rule, "exceptions", ()) or ()),
                )
            )
            for version in rule_versions:
                version_scope = getattr(version, "scope", None)
                version_written = getattr(version, "written", None)
                versions.append(
                    FormalRuleVersionRow(
                        owner_id=owner_id,
                        rule_id=rule_id,
                        version_id=_text(getattr(version, "version_id", None)),
                        version_number=_tick(
                            getattr(version, "version_number", None)
                        ),
                        stage=_enum_value(getattr(version, "stage", None)),
                        constraint_kind=_enum_value(
                            getattr(version, "constraint", None)
                        ),
                        scope_kind=_enum_value(getattr(version_scope, "kind", None)),
                        scope_digest=_text(
                            getattr(version_scope, "digest", None)
                        ),
                        action_token=_text(getattr(rule, "action_token", None)),
                        authority_kind=_enum_value(getattr(version, "authority", None)),
                        recognition=_enum_value(getattr(version, "recognition", None)),
                        written_status=(
                            "none"
                            if version_written is None
                            else _enum_value(getattr(version_written, "status", None))
                        ),
                        tick=_tick(getattr(version, "tick", None)),
                        revision_kind=_enum_value(
                            getattr(version, "revision_kind", None)
                        ),
                    )
                )
            for position in getattr(rule, "proponents", ()) or ():
                positions.append(
                    FormalRulePositionRow(
                        owner_id=owner_id,
                        rule_id=rule_id,
                        position_id=_text(getattr(position, "position_id", None)),
                        actor_id=_text(getattr(position, "actor_id", None)),
                        stance=_enum_value(getattr(position, "stance", None)),
                        provenance=_enum_value(getattr(position, "provenance", None)),
                        tick=_tick(getattr(position, "tick", None)),
                    )
                )
            for response in getattr(rule, "responses", ()) or ():
                responses.append(
                    FormalRuleResponseRow(
                        owner_id=owner_id,
                        rule_id=rule_id,
                        response_id=_text(getattr(response, "response_id", None)),
                        actor_id=_text(getattr(response, "actor_id", None)),
                        kind=_enum_value(getattr(response, "kind", None)),
                        provenance=_enum_value(getattr(response, "provenance", None)),
                        tick=_tick(getattr(response, "tick", None)),
                    )
                )
            for item in getattr(rule, "evidence", ()) or ():
                lineage_ref = getattr(item, "lineage_ref", None)
                evidence.append(
                    FormalRuleEvidenceRow(
                        owner_id=owner_id,
                        rule_id=rule_id,
                        evidence_id=_text(getattr(item, "evidence_id", None)),
                        channel=_enum_value(getattr(item, "channel", None)),
                        provenance=_enum_value(getattr(item, "provenance", None)),
                        tick=_tick(getattr(item, "tick", None)),
                        artifact_present=getattr(item, "artifact_id", None)
                        is not None,
                        repository_present=isinstance(lineage_ref, str)
                        and lineage_ref.startswith("repository:"),
                    )
                )
    rows = FormalRuleHarvestRows(
        owners=tuple(sorted(owners, key=lambda item: item.owner_id)),
        systems=tuple(sorted(systems, key=lambda item: item.system_id)),
        rules=tuple(sorted(rules, key=lambda item: item.rule_id)),
        versions=tuple(
            sorted(versions, key=lambda item: (item.rule_id, item.version_number))
        ),
        positions=tuple(sorted(positions, key=lambda item: item.position_id)),
        responses=tuple(sorted(responses, key=lambda item: item.response_id)),
        evidence=tuple(sorted(evidence, key=lambda item: item.evidence_id)),
        window_ticks=window_ticks,
    )
    _LOG.info(
        "formal_rule_harvest owners=%s rules=%s windows=%s",
        len(rows.owners),
        len(rows.rules),
        0,
    )
    return rows
