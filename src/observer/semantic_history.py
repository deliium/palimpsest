"""Detached owner semantic-sense history projection.

Rows are retained checkpoint evidence. They never reconstruct historical
subjective state, expose label tokens, composition parts or raw referent IDs.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

SEMANTIC_HISTORY_SOURCES: Final[frozenset[str]] = frozenset({"label", "composition"})
_TERM_SOURCES: Final[frozenset[str]] = frozenset({"label", "composition"})


def _surface_digest(material: str) -> str:
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def semantic_term_digest(
    term_source: str,
    *,
    label_token: str | None = None,
    kind: str | None = None,
    parts: Sequence[str] | None = None,
) -> str:
    """Reproduce the analysis metadata surface digest without importing analysis."""
    if term_source not in _TERM_SOURCES:
        raise ValueError("invalid_term_source")
    if term_source == "label":
        if not isinstance(label_token, str) or not label_token:
            raise ValueError("invalid_label_token")
        return _surface_digest(f"label|{label_token}")
    if not isinstance(kind, str) or not kind:
        raise ValueError("invalid_composition_kind")
    checked = tuple(parts or ())
    if len(checked) != 2 or any(
        not isinstance(item, str) or not item for item in checked
    ):
        raise ValueError("invalid_composition_parts")
    return _surface_digest(
        "composition|"
        f"{kind}|{_surface_digest(checked[0])}|{_surface_digest(checked[1])}"
    )


def referent_digest(referent_kind: str, referent_id: str) -> str:
    return _surface_digest(f"referent|{referent_kind}|{referent_id}")


def symbolic_referent_digest(associated_ids: Sequence[str]) -> str | None:
    ordered = tuple(item for item in associated_ids if isinstance(item, str) and item)
    if not ordered:
        return None
    return _surface_digest("composition-referent|" + "|".join(ordered))


@dataclass(frozen=True, slots=True)
class SemanticHistoryRow:
    ordinal: int
    tick: int
    trigger: str
    term_source: str
    term_digest: str
    local_id: str
    referent_kind: str | None
    referent_digest: str | None
    associated_digests: tuple[str, ...]
    confidence: float | None


@dataclass(frozen=True, slots=True)
class SemanticHistoryTerm:
    term_source: str
    term_digest: str
    first_ordinal: int
    current_sense_revision: int


@dataclass(frozen=True, slots=True)
class ProjectedSemanticHistory:
    source: str
    rows: tuple[SemanticHistoryRow, ...]
    terms: tuple[SemanticHistoryTerm, ...]
    history_first_tick: int | None
    history_last_tick: int | None


def _enum_value(value: object) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) and raw else None


def _owner_id(owner: object) -> str:
    raw = getattr(owner, "value", owner)
    if not isinstance(raw, str) or not raw:
        raise ValueError("invalid_owner_id")
    return raw


def project_semantic_history(
    owner_id: str,
    checkpoint: object | None,
    source: Literal["label", "composition"] | str,
) -> ProjectedSemanticHistory:
    """Project one source's retained sense rows from an owner checkpoint."""
    if source not in SEMANTIC_HISTORY_SOURCES:
        raise ValueError("invalid_source")
    if not isinstance(owner_id, str) or not owner_id:
        raise ValueError("invalid_owner_id")
    rows: list[SemanticHistoryRow] = []
    term_state: dict[str, tuple[int, int]] = {}
    if checkpoint is None:
        return ProjectedSemanticHistory(source, (), (), None, None)
    if source == "label":
        ledger = getattr(checkpoint, "semantic_naming", None)
        if ledger is None:
            return ProjectedSemanticHistory(source, (), (), None, None)
        for binding in getattr(ledger, "bindings", ()) or ():
            owner = _owner_id(getattr(binding, "owner_id", ""))
            if owner != owner_id:
                continue
            token = getattr(binding, "label_token", None)
            if not isinstance(token, str) or not token:
                continue
            term_digest = semantic_term_digest("label", label_token=token)
            revision = int(getattr(binding, "sense_revision", 0))
            local_id = str(getattr(binding, "binding_id", ""))
            for record in getattr(binding, "sense_history", ()) or ():
                kind = _enum_value(getattr(record, "referent_kind", None))
                referent_id = getattr(record, "referent_id", None)
                if kind is None or not isinstance(referent_id, str):
                    continue
                associated = tuple(
                    referent_digest(kind, item)
                    for item in getattr(record, "associated_ids", ()) or ()
                    if isinstance(item, str) and item
                )
                row = SemanticHistoryRow(
                    ordinal=int(getattr(record, "ordinal", 0)),
                    tick=int(getattr(record, "tick", 0)),
                    trigger=_enum_value(getattr(record, "trigger", None)) or "",
                    term_source="label",
                    term_digest=term_digest,
                    local_id=local_id,
                    referent_kind=kind,
                    referent_digest=referent_digest(kind, referent_id),
                    associated_digests=associated,
                    confidence=_confidence(getattr(record, "confidence", None)),
                )
                rows.append(row)
                previous = term_state.get(term_digest)
                first = (
                    row.ordinal if previous is None else min(previous[0], row.ordinal)
                )
                term_state[term_digest] = (first, revision)
    else:
        ledger = getattr(checkpoint, "symbolic_language", None)
        if ledger is None:
            return ProjectedSemanticHistory(source, (), (), None, None)
        for composition in getattr(ledger, "compositions", ()) or ():
            owner = _owner_id(getattr(composition, "owner_id", ""))
            if owner != owner_id:
                continue
            parts = tuple(getattr(composition, "parts", ()) or ())
            kind = _enum_value(getattr(composition, "kind", None))
            if len(parts) != 2 or kind is None:
                continue
            term_digest = semantic_term_digest("composition", kind=kind, parts=parts)
            revision = int(getattr(composition, "sense_revision", 0))
            local_id = str(getattr(composition, "composition_id", ""))
            for record in getattr(composition, "sense_history", ()) or ():
                record_kind = _enum_value(getattr(record, "referent_kind", None))
                associated_ids = tuple(
                    item
                    for item in getattr(record, "associated_ids", ()) or ()
                    if isinstance(item, str) and item
                )
                associated = tuple(
                    referent_digest(record_kind or "unspecified", item)
                    for item in associated_ids
                )
                row = SemanticHistoryRow(
                    ordinal=int(getattr(record, "ordinal", 0)),
                    tick=int(getattr(record, "tick", 0)),
                    trigger=_enum_value(getattr(record, "trigger", None)) or "",
                    term_source="composition",
                    term_digest=term_digest,
                    local_id=local_id,
                    referent_kind=record_kind,
                    referent_digest=symbolic_referent_digest(associated_ids),
                    associated_digests=associated,
                    confidence=_confidence(getattr(record, "confidence", None)),
                )
                rows.append(row)
                previous = term_state.get(term_digest)
                first = (
                    row.ordinal if previous is None else min(previous[0], row.ordinal)
                )
                term_state[term_digest] = (first, revision)

    rows.sort(key=lambda row: (row.tick, row.ordinal, row.term_digest, row.local_id))
    terms = tuple(
        SemanticHistoryTerm(
            term_source=source,
            term_digest=digest,
            first_ordinal=value[0],
            current_sense_revision=value[1],
        )
        for digest, value in sorted(term_state.items())
    )
    first_tick = rows[0].tick if rows else None
    last_tick = rows[-1].tick if rows else None
    return ProjectedSemanticHistory(source, tuple(rows), terms, first_tick, last_tick)


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


__all__ = [
    "SEMANTIC_HISTORY_SOURCES",
    "ProjectedSemanticHistory",
    "SemanticHistoryRow",
    "SemanticHistoryTerm",
    "project_semantic_history",
    "referent_digest",
    "semantic_term_digest",
    "symbolic_referent_digest",
]
