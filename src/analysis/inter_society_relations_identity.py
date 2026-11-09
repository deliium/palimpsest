"""Content-addressed ``isr-`` identity minting for society pairs.

Pair ids are researcher labels over ordered ``msoc-`` endpoints plus window
evidence. Overlapping membership between societies is legal. Nothing here mints
nations or rewrites V4-02 lineage.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Final

from analysis.inter_society_relations_contract import (
    INTER_SOCIETY_RELATIONS_ID_PREFIX,
    InterSocietyAvailability,
    InterSocietyDomain,
    InterSocietyPairStatus,
    InterSocietyRelationsError,
    derive_inter_society_pair_id,
    ordered_society_pair,
    require_inter_society_pair_id,
)
from analysis.inter_society_relations_evidence import InterSocietyDomainPanel
from analysis.inter_society_relations_layers import InterSocietyPairCandidate
from world.identifiers import require_exact_nonneg_int

__all__ = [
    "INTER_SOCIETY_RELATIONS_ID_PREFIX",
    "mint_inter_society_pair",
    "pair_status_from_panels",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.inter_society_relations.identity"
)


def pair_status_from_panels(
    panels: Sequence[InterSocietyDomainPanel],
) -> InterSocietyPairStatus:
    """Derive pair status from domain availability without inventing a score."""
    if not panels:
        return InterSocietyPairStatus.EMPTY
    present = sum(
        1 for panel in panels if panel.availability is InterSocietyAvailability.PRESENT
    )
    absent = sum(
        1 for panel in panels if panel.availability is InterSocietyAvailability.ABSENT
    )
    if present == 0 and absent == len(panels):
        return InterSocietyPairStatus.EMPTY
    if absent > 0 or present < len(panels):
        return InterSocietyPairStatus.PARTIAL
    return InterSocietyPairStatus.OBSERVED


def mint_inter_society_pair(
    *,
    society_a: str,
    society_b: str,
    window_tick: int,
    panels: Sequence[InterSocietyDomainPanel],
    overlap_member_count: int = 0,
    members_a: Sequence[str] = (),
    members_b: Sequence[str] = (),
) -> InterSocietyPairCandidate:
    """Mint one content-addressed ``isr-`` candidate for an ordered society pair."""
    left, right = ordered_society_pair(society_a, society_b)
    tick = require_exact_nonneg_int("window_tick", window_tick)
    overlap = require_exact_nonneg_int("overlap_member_count", overlap_member_count)
    if members_a or members_b:
        overlap = len(set(members_a) & set(members_b))
    panel_tuple = tuple(sorted(panels, key=lambda panel: panel.domain.value))
    if {panel.domain for panel in panel_tuple} != set(InterSocietyDomain):
        raise InterSocietyRelationsError("inter_society_relations_invalid_domain")
    domain_signature = tuple(
        panel.domain.value
        for panel in panel_tuple
        if panel.availability is not InterSocietyAvailability.ABSENT
    )
    pair_id = derive_inter_society_pair_id(
        window_tick=tick,
        society_a=left,
        society_b=right,
        domain_signature=domain_signature,
    )
    status = pair_status_from_panels(panel_tuple)
    candidate = InterSocietyPairCandidate(
        pair_id=require_inter_society_pair_id(pair_id),
        society_a=left,
        society_b=right,
        window_tick=tick,
        status=status.value,
        overlap_member_count=overlap,
        panels=panel_tuple,
    )
    _LOG.debug(
        "inter_society_relations_pair_minted status=%s domain_present=%s",
        status.value,
        len(domain_signature),
    )
    return candidate
