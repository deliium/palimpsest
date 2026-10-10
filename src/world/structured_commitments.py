"""Objective declaration legality. Not a collected contract.

The engine never reads ledgers, kinship, norms, or reputation when it
admits ``DeclareCommitment``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

__all__ = [
    "COMMITMENT_ACTS",
    "COMMITMENT_DUE_KINDS",
    "COMMITMENT_KINDS",
    "COMMITMENT_OWED_BY",
    "COMMITMENT_SERVICES",
    "StructuredCommitmentsRuleContext",
]

_LOG = logging.getLogger(__name__)

COMMITMENT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "promise",
        "future_exchange",
        "debt",
        "service_obligation",
        "conditional_agreement",
    }
)
COMMITMENT_ACTS: Final[frozenset[str]] = frozenset(
    {
        "propose",
        "accept",
        "report_fulfilled",
        "report_partial",
        "report_violated",
        "report_dispute",
    }
)
COMMITMENT_OWED_BY: Final[frozenset[str]] = frozenset({"self", "counterparty"})
COMMITMENT_SERVICES: Final[frozenset[str]] = frozenset(
    {"none", "help", "feed", "transport"}
)
COMMITMENT_DUE_KINDS: Final[frozenset[str]] = frozenset(
    {"none", "by_tick", "when_next_colocated", "if_counterpart_gives"}
)


@dataclass(frozen=True, slots=True)
class StructuredCommitmentsRuleContext:
    """Ephemeral speech gate. Horizon only. No ledger."""

    allow_declare: bool = True
    horizon_ticks: int = 8

    def __post_init__(self) -> None:
        if type(self.allow_declare) is not bool:
            raise TypeError("allow_declare must be bool")
        if type(self.horizon_ticks) is not int or isinstance(self.horizon_ticks, bool):
            raise TypeError("horizon_ticks must be int")
        if self.horizon_ticks < 1 or self.horizon_ticks > 64:
            raise ValueError("horizon_ticks must be in [1, 64]")
        _LOG.debug(
            "structured_commitments_rule_context allow_declare=%s horizon_ticks=%s",
            self.allow_declare,
            self.horizon_ticks,
        )
