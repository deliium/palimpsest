"""Metadata-only export projection for owner border ledgers.

This module stays inside ``simulation`` so ``experiments`` can compose exported
rows without importing cognition. Inputs are duck-typed ledger rows; no
cognition type is imported here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

__all__ = [
    "BorderExportRow",
    "border_anchor_token",
    "border_export_digest",
    "border_location_token",
    "border_owner_token",
    "export_border_rows",
]


def _short(prefix: str, material: str) -> str:
    return f"{prefix}{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _owner(owner: object) -> str:
    value = getattr(owner, "value", owner)
    if type(value) is not str or not value:
        raise ValueError("owner: invalid_identifier")
    return value


def border_owner_token(owner: object) -> str:
    return _short("bown-", _owner(owner))


def border_location_token(location: object) -> str:
    value = getattr(location, "value", location)
    if type(value) is not str or not value:
        raise ValueError("location: invalid_identifier")
    return _short("bloc-", value)


def border_anchor_token(value: object) -> str:
    if type(value) is not str or not value:
        raise ValueError("anchor: invalid_identifier")
    return _short("banc-", value)


def _edge_tokens(edges: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes)):
        return ()
    pairs: list[tuple[str, str]] = []
    for item in edges:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            left, right = item
            if type(left) is str and type(right) is str:
                pairs.append(
                    (_short("bloc-", left), _short("bloc-", right))
                )
    return tuple(pairs)


def _location_tokens(locations: object) -> tuple[str, ...]:
    if not isinstance(locations, Sequence) or isinstance(locations, (str, bytes)):
        return ()
    return tuple(
        border_location_token(item)
        for item in locations
        if type(getattr(item, "value", item)) is str
    )


@dataclass(frozen=True, slots=True)
class BorderExportRow:
    row_kind: str
    row_id: str
    owner_token: str
    domain_token: str
    location_tokens: tuple[str, ...] = ()
    edge_tokens: tuple[tuple[str, str], ...] = ()
    status: str = ""
    mode: str = ""
    anchor_token: str = ""
    counterparty_token: str = ""
    subject_token: str = ""
    provision_tokens: tuple[str, ...] = ()
    effective_tick: int | None = None
    expiry_tick: int | None = None
    strength: float = 0.0
    basis: str = ""
    recognition: str = ""


def _enum_text(value: object) -> str:
    return str(getattr(value, "value", value) or "")


def export_border_rows(ledger: object) -> tuple[BorderExportRow, ...]:
    """Project one owner ledger into metadata-only rows."""
    owner_token = border_owner_token(getattr(ledger, "owner_id", None))
    rows: list[BorderExportRow] = []
    for item in getattr(ledger, "domains", ()) or ():
        rows.append(
            BorderExportRow(
                row_kind="claim",
                row_id=str(getattr(item, "domain_id", "")),
                owner_token=owner_token,
                domain_token=str(getattr(item, "domain_id", "")),
                location_tokens=_location_tokens(
                    getattr(item, "location_ids", ())
                ),
                edge_tokens=_edge_tokens(getattr(item, "boundary_edges", ())),
                status=_enum_text(getattr(item, "status", "")),
                anchor_token=(
                    ""
                    if getattr(item, "anchor_ref", None) is None
                    else border_anchor_token(item.anchor_ref)
                ),
                strength=float(getattr(item, "strength", 0.0) or 0.0),
            )
        )
    for item in getattr(ledger, "recognitions", ()) or ():
        rows.append(
            BorderExportRow(
                row_kind="recognition",
                row_id=str(getattr(item, "recognition_id", ""))
                or _short(
                    "bdr-",
                    f"{getattr(item, 'domain_id', '')}|"
                    f"{_enum_text(getattr(item, 'basis', ''))}",
                ),
                owner_token=owner_token,
                domain_token=str(getattr(item, "domain_id", "")),
                edge_tokens=_edge_tokens(
                    getattr(item, "boundary_edges", ())
                ),
                status=_enum_text(getattr(item, "status", "")),
                basis=_enum_text(getattr(item, "basis", "")),
            )
        )
    for item in getattr(ledger, "access_expectations", ()) or ():
        rows.append(
            BorderExportRow(
                row_kind="access",
                row_id=str(getattr(item, "expectation_id", "")),
                owner_token=owner_token,
                domain_token=str(getattr(item, "domain_id", "")),
                status=_enum_text(getattr(item, "status", "")),
                mode=_enum_text(getattr(item, "mode", "")),
                subject_token=(
                    ""
                    if getattr(item, "subject_ref", None) is None
                    else _short("bsub-", str(item.subject_ref))
                ),
            )
        )
    for item in getattr(ledger, "agreements", ()) or ():
        rows.append(
            BorderExportRow(
                row_kind="agreement",
                row_id=str(getattr(item, "agreement_id", "")),
                owner_token=owner_token,
                domain_token=str(getattr(item, "domain_id", "")),
                status=_enum_text(getattr(item, "status", "")),
                counterparty_token=(
                    ""
                    if getattr(item, "counterparty_ref", None) is None
                    else _short("bcp-", str(item.counterparty_ref))
                ),
                provision_tokens=tuple(
                    _enum_text(value)
                    for value in getattr(item, "provisions", ())
                ),
                effective_tick=getattr(item, "effective_tick", None),
                expiry_tick=getattr(item, "expiry_tick", None),
                recognition=_enum_text(getattr(item, "recognition", "")),
            )
        )
    for item in getattr(ledger, "disputes", ()) or ():
        rows.append(
            BorderExportRow(
                row_kind="dispute",
                row_id=str(getattr(item, "dispute_id", "")),
                owner_token=owner_token,
                domain_token=str(getattr(item, "domain_id", "")),
                location_tokens=_location_tokens(
                    getattr(item, "contested_location_ids", ())
                ),
                status=_enum_text(getattr(item, "status", "")),
                counterparty_token=(
                    ""
                    if getattr(item, "counterparty_ref", None) is None
                    else _short("bcp-", str(item.counterparty_ref))
                ),
            )
        )
    rows.sort(key=lambda item: (item.row_kind, item.row_id))
    return tuple(rows)


def border_export_digest(rows: Sequence[BorderExportRow]) -> str:
    lines: list[str] = []
    for item in rows:
        lines.append(
            "|".join(
                (
                    item.row_kind,
                    item.row_id,
                    item.owner_token,
                    item.domain_token,
                    ",".join(item.location_tokens),
                    ",".join(f"{a}>{b}" for a, b in item.edge_tokens),
                    item.status,
                    item.mode,
                    item.anchor_token,
                    item.counterparty_token,
                    item.subject_token,
                    ",".join(item.provision_tokens),
                    str(item.effective_tick),
                    str(item.expiry_tick),
                    f"{item.strength:.6f}",
                    item.basis,
                    item.recognition,
                )
            )
        )
    lines.sort()
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


_ = Mapping
