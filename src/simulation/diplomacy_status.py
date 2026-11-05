"""Derive composer-visible treaty statuses from owner-scoped diplomacy ledgers.

This module belongs to the simulation contract layer so detached composition can
consume derived statuses without importing cognition directly. It is a pure
read: it never mutates a ledger or constructs a command.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from agents.cognition import default_diplomacy_policy, diplomacy_treaty_statuses
from agents.cognition.diplomacy import DiplomacyLedger

__all__ = ["TreatyStatusRow", "derive_treaty_statuses"]


@dataclass(frozen=True, slots=True)
class TreatyStatusRow:
    """One composer-visible treaty version status derived from owner beliefs."""

    treaty_id: str
    version_id: str
    status: str
    acceptance_basis: str


def derive_treaty_statuses(
    ledgers: Sequence[object],
    representation_ledgers: Sequence[object] = (),
    *,
    tick: int,
) -> tuple[TreatyStatusRow, ...]:
    """Return status rows for every retained treaty version in ``ledgers``."""

    representation_by_owner = {
        getattr(ledger, "owner_id", None): ledger
        for ledger in representation_ledgers
    }
    rows: list[TreatyStatusRow] = []
    for ledger in ledgers:
        if type(ledger) is not DiplomacyLedger:
            continue
        representation = representation_by_owner.get(ledger.owner_id)
        for treaty in ledger.treaties:
            for version_id, status, basis in diplomacy_treaty_statuses(
                treaty,
                ledger.treaty_versions,
                ledger.treaty_declarations,
                tick=tick,
                policy=default_diplomacy_policy(),
                representation=representation,
                envoys=ledger.envoys,
                subject_kind=treaty.subject_kind,
            ):
                rows.append(
                    TreatyStatusRow(
                        treaty_id=treaty.treaty_id,
                        version_id=version_id,
                        status=status.value,
                        acceptance_basis=basis.value,
                    )
                )
    rows.sort(key=lambda row: (row.treaty_id, row.version_id))
    return tuple(rows)
