"""Metadata-only harvest rows for detached diplomacy analysis."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from analysis.diplomacy_contract import (
    DIPLOMACY_PARTY_KINDS,
    DIPLOMACY_STATUSES,
    DiplomacyAnalysisError,
    DiplomacyCoverage,
    diplomacy_agent_token,
    diplomacy_party_token,
    diplomacy_subject_token,
    require_diplomacy_token,
)

__all__ = [
    "DiplomacyConflictRow",
    "DiplomacyContactRow",
    "DiplomacyDeclarationRow",
    "DiplomacyEnvoyRow",
    "DiplomacyHarvestRows",
    "DiplomacyInstrumentRow",
    "DiplomacyMisrepresentationRow",
    "DiplomacyNegotiationRow",
    "DiplomacyPartyRow",
    "DiplomacyRelationRow",
    "DiplomacyTerminationRow",
    "harvest_diplomacy_rows",
]

_LOG: Final[logging.Logger] = logging.getLogger("analysis.diplomacy_rows")


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        raise DiplomacyAnalysisError("diplomacy_invalid_row")
    return value


def _text(value: object, *, max_len: int = 128) -> str:
    token = getattr(value, "value", value)
    if type(token) is not str or not token or len(token) > max_len:
        raise DiplomacyAnalysisError("diplomacy_invalid_row")
    return token


def _owner(value: object) -> str:
    return diplomacy_agent_token(value)


@dataclass(frozen=True, slots=True)
class DiplomacyRelationRow:
    owner_token: str
    relation_id: str
    party_tokens: tuple[str, ...]
    opened_tick: int
    last_tick: int
    coverage: DiplomacyCoverage

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        _text(self.relation_id)
        if len(self.party_tokens) < 2:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        _tick(self.opened_tick)
        _tick(self.last_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyPartyRow:
    owner_token: str
    party_token: str | None
    party_kind: str
    resolution: str
    first_seen_tick: int

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        if self.party_kind not in DIPLOMACY_PARTY_KINDS:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        if self.resolution not in {"resolved", "unresolved", "unknown"}:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        if self.party_token is not None:
            _text(self.party_token)
        _tick(self.first_seen_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyContactRow:
    owner_token: str
    relation_id: str
    tick: int
    contact_kind: str
    participant_count: int

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        _tick(self.tick)
        if self.participant_count < 1:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")


@dataclass(frozen=True, slots=True)
class DiplomacyEnvoyRow:
    owner_token: str
    relation_id: str
    party_token: str | None
    envoy_token: str
    status: str
    accredited_tick: int
    end_tick: int | None

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        require_diplomacy_token(self.envoy_token)
        if self.status not in DIPLOMACY_STATUSES:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        _tick(self.accredited_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyNegotiationRow:
    owner_token: str
    relation_id: str
    negotiation_id: str
    subject_token: str | None
    status: str
    opened_tick: int
    last_tick: int

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        _tick(self.opened_tick)
        _tick(self.last_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyInstrumentRow:
    owner_token: str
    relation_id: str
    instrument_id: str
    party_tokens: tuple[str, ...]
    instrument_kind: str
    term_kind: str
    subject_token: str | None
    opened_tick: int
    end_tick: int | None
    anchor_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        if self.instrument_kind not in {
            "proposal",
            "promise",
            "agreement",
            "dispute",
            "shared_project",
            "unknown",
        }:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        _tick(self.opened_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyDeclarationRow:
    owner_token: str
    instrument_id: str
    party_token: str | None
    envoy_token: str | None
    act: str
    declared_tick: int

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        if self.act not in {
            "propose",
            "accept",
            "reject",
            "withdraw",
            "promise",
            "dispute",
            "shared_project",
            "report",
        }:
            raise DiplomacyAnalysisError("diplomacy_invalid_row")
        _tick(self.declared_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyMisrepresentationRow:
    owner_token: str
    instrument_id: str
    kind: str
    observed_tick: int
    envoy_token: str

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        _tick(self.observed_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyTerminationRow:
    owner_token: str
    target_kind: str
    kind: str
    tick: int
    target_ref: str = ""

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        _tick(self.tick)


@dataclass(frozen=True, slots=True)
class DiplomacyConflictRow:
    owner_token: str
    relation_id: str
    kind: str
    observed_tick: int

    def __post_init__(self) -> None:
        require_diplomacy_token(self.owner_token)
        _tick(self.observed_tick)


@dataclass(frozen=True, slots=True)
class DiplomacyHarvestRows:
    relations: tuple[DiplomacyRelationRow, ...] = ()
    parties: tuple[DiplomacyPartyRow, ...] = ()
    contacts: tuple[DiplomacyContactRow, ...] = ()
    envoys: tuple[DiplomacyEnvoyRow, ...] = ()
    negotiations: tuple[DiplomacyNegotiationRow, ...] = ()
    instruments: tuple[DiplomacyInstrumentRow, ...] = ()
    declarations: tuple[DiplomacyDeclarationRow, ...] = ()
    misrepresentations: tuple[DiplomacyMisrepresentationRow, ...] = ()
    terminations: tuple[DiplomacyTerminationRow, ...] = ()
    conflicts: tuple[DiplomacyConflictRow, ...] = ()
    coverage: DiplomacyCoverage = DiplomacyCoverage.PARTIAL

    def __post_init__(self) -> None:
        for name in (
            "relations",
            "parties",
            "contacts",
            "envoys",
            "negotiations",
            "instruments",
            "declarations",
            "misrepresentations",
            "terminations",
            "conflicts",
        ):
            rows = getattr(self, name)
            if type(rows) is not tuple:
                raise DiplomacyAnalysisError("diplomacy_invalid_row")

    def has_any_rows(self) -> bool:
        return any(
            getattr(self, name)
            for name in (
                "relations",
                "parties",
                "contacts",
                "envoys",
                "negotiations",
                "instruments",
                "declarations",
                "misrepresentations",
                "terminations",
                "conflicts",
            )
        )


def _party_maps(ledger: object) -> tuple[dict[str, str | None], dict[str, str]]:
    tokens: dict[str, str | None] = {}
    kinds: dict[str, str] = {}
    for party in getattr(ledger, "parties", ()):
        kind = getattr(getattr(party, "kind", None), "value", "unknown")
        anchor = getattr(party, "anchor_ref", None)
        tokens[party.party_id] = diplomacy_party_token(kind, anchor)
        kinds[party.party_id] = kind
    return tokens, kinds


def harvest_diplomacy_rows(
    ledgers: Sequence[object],
    *,
    entity_to_agent: Callable[[object], object] | Mapping[Any, Any] | None = None,
    policy: object | None = None,
) -> DiplomacyHarvestRows:
    """Harvest exported owner ledgers into token-only detached rows."""

    resolve = entity_to_agent
    relations: list[DiplomacyRelationRow] = []
    parties: list[DiplomacyPartyRow] = []
    contacts: list[DiplomacyContactRow] = []
    envoys: list[DiplomacyEnvoyRow] = []
    negotiations: list[DiplomacyNegotiationRow] = []
    instruments: list[DiplomacyInstrumentRow] = []
    declarations: list[DiplomacyDeclarationRow] = []
    misrepresentations: list[DiplomacyMisrepresentationRow] = []
    terminations: list[DiplomacyTerminationRow] = []
    conflicts: list[DiplomacyConflictRow] = []
    complete = True

    for ledger in ledgers:
        owner = getattr(ledger, "owner_id", None)
        if resolve is not None:
            owner = resolve(owner) if callable(resolve) else resolve.get(owner, owner)
        owner_token = _owner(owner)
        tokens, kinds = _party_maps(ledger)
        if getattr(ledger, "notices", ()):
            complete = False
        for row in getattr(ledger, "relations", ()):
            party_tokens = tuple(
                token for token in (tokens.get(pid) for pid in row.party_ids) if token
            )
            relations.append(
                DiplomacyRelationRow(
                    owner_token=owner_token,
                    relation_id=row.relation_id,
                    party_tokens=party_tokens,
                    opened_tick=row.opened_tick,
                    last_tick=row.last_tick,
                    coverage=DiplomacyCoverage.PARTIAL,
                )
            )
        for row in getattr(ledger, "parties", ()):
            hook = getattr(row, "anchor_ref", None)
            if (
                resolve is not None
                and hook is not None
                and kinds.get(row.party_id) == "agent"
            ):
                hook = resolve(hook) if callable(resolve) else resolve.get(hook, hook)
            parties.append(
                DiplomacyPartyRow(
                    owner_token=owner_token,
                    party_token=diplomacy_party_token(
                        kinds.get(row.party_id, "unknown"), hook
                    ),
                    party_kind=kinds.get(row.party_id, "unknown"),
                    resolution=getattr(row.resolution, "value", "unknown"),
                    first_seen_tick=row.first_seen_tick,
                )
            )
        for row in getattr(ledger, "contacts", ()):
            contacts.append(
                DiplomacyContactRow(
                    owner_token=owner_token,
                    relation_id=row.relation_id,
                    tick=row.tick,
                    contact_kind=getattr(row.contact_kind, "value", "unknown"),
                    participant_count=row.participant_count,
                )
            )
        for row in getattr(ledger, "envoys", ()):
            envoys.append(
                DiplomacyEnvoyRow(
                    owner_token=owner_token,
                    relation_id=row.relation_id,
                    party_token=tokens.get(row.party_id),
                    envoy_token=diplomacy_agent_token(row.envoy_ref),
                    status=getattr(row.status, "value", "unknown"),
                    accredited_tick=row.accredited_tick,
                    end_tick=row.end_tick,
                )
            )
        for row in getattr(ledger, "negotiations", ()):
            negotiations.append(
                DiplomacyNegotiationRow(
                    owner_token=owner_token,
                    relation_id=row.relation_id,
                    negotiation_id=row.negotiation_id,
                    subject_token=diplomacy_subject_token(row.topic_subject),
                    status=getattr(row.status, "value", "unknown"),
                    opened_tick=row.opened_tick,
                    last_tick=row.last_tick,
                )
            )
        for row in getattr(ledger, "instruments", ()):
            instruments.append(
                DiplomacyInstrumentRow(
                    owner_token=owner_token,
                    relation_id=row.relation_id,
                    instrument_id=row.instrument_id,
                    party_tokens=tuple(
                        token
                        for token in (tokens.get(pid) for pid in row.party_ids)
                        if token
                    ),
                    instrument_kind=getattr(row.kind, "value", "unknown"),
                    term_kind=getattr(row.term_kind, "value", "unknown"),
                    subject_token=diplomacy_subject_token(row.topic_subject),
                    opened_tick=row.opened_tick,
                    end_tick=row.end_tick,
                    anchor_refs=tuple(row.anchor_refs),
                )
            )
        for row in getattr(ledger, "declarations", ()):
            declarations.append(
                DiplomacyDeclarationRow(
                    owner_token=owner_token,
                    instrument_id=row.instrument_id,
                    party_token=tokens.get(row.declarer_party_id),
                    envoy_token=(
                        None
                        if row.envoy_ref is None
                        else diplomacy_agent_token(row.envoy_ref)
                    ),
                    act=getattr(row.act, "value", "unknown"),
                    declared_tick=row.declared_tick,
                )
            )
        for row in getattr(ledger, "misrepresentations", ()):
            misrepresentations.append(
                DiplomacyMisrepresentationRow(
                    owner_token=owner_token,
                    instrument_id=row.instrument_id,
                    kind=getattr(row.kind, "value", "unknown"),
                    observed_tick=row.observed_tick,
                    envoy_token=diplomacy_agent_token(row.envoy_ref),
                )
            )
        for row in getattr(ledger, "terminations", ()):
            terminations.append(
                DiplomacyTerminationRow(
                    owner_token=owner_token,
                    target_kind=row.target_kind,
                    kind=getattr(row.kind, "value", "unknown"),
                    tick=row.tick,
                    target_ref=row.target_ref,
                )
            )
        for row in getattr(ledger, "conflicts", ()):
            conflicts.append(
                DiplomacyConflictRow(
                    owner_token=owner_token,
                    relation_id=row.relation_id,
                    kind=getattr(row.kind, "value", "unknown"),
                    observed_tick=row.observed_tick,
                )
            )

    def ordered(rows: list[Any], key: Callable[[Any], Any]) -> tuple[Any, ...]:
        return tuple(sorted(rows, key=key))

    harvest = DiplomacyHarvestRows(
        relations=ordered(
            relations, lambda r: (r.owner_token, r.opened_tick, r.relation_id)
        ),
        parties=ordered(
            parties, lambda r: (r.owner_token, r.first_seen_tick, str(r.party_token))
        ),
        contacts=ordered(contacts, lambda r: (r.owner_token, r.tick, r.relation_id)),
        envoys=ordered(
            envoys, lambda r: (r.owner_token, r.accredited_tick, r.envoy_token)
        ),
        negotiations=ordered(
            negotiations, lambda r: (r.owner_token, r.opened_tick, r.negotiation_id)
        ),
        instruments=ordered(
            instruments, lambda r: (r.owner_token, r.opened_tick, r.instrument_id)
        ),
        declarations=ordered(
            declarations, lambda r: (r.owner_token, r.declared_tick, r.instrument_id)
        ),
        misrepresentations=ordered(
            misrepresentations,
            lambda r: (r.owner_token, r.observed_tick, r.instrument_id),
        ),
        terminations=ordered(
            terminations, lambda r: (r.owner_token, r.tick, r.target_kind)
        ),
        conflicts=ordered(
            conflicts, lambda r: (r.owner_token, r.observed_tick, r.relation_id)
        ),
        coverage=(
            DiplomacyCoverage.COMPLETE
            if complete and ledgers
            else DiplomacyCoverage.PARTIAL
        ),
    )
    _LOG.debug(
        "diplomacy_harvest rows=%s lanes=%s",
        sum(
            len(getattr(harvest, name))
            for name in (
                "relations",
                "parties",
                "contacts",
                "envoys",
                "negotiations",
                "instruments",
                "declarations",
                "misrepresentations",
                "terminations",
                "conflicts",
            )
        ),
        6,
    )
    return harvest
