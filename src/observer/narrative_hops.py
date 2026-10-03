"""SUBJECTIVE owner narrative-ledger hop projection for presentation.

No story content tokens, fingerprints as labels, or free-form narrative text.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from observer.version import OBSERVER_PROTOCOL_VERSION

_LOGGER = logging.getLogger("observer.narrative_hops")

_EVIDENCE_CLASS = "SUBJECTIVE_TO_SELECTED_AGENT"
_LAYER = "subjective_narrative_hops"


@dataclass(frozen=True, slots=True)
class NarrativeHopVariant:
    variant_id: str
    status: str
    origin: str
    carrier_agent_ids: tuple[str, ...]
    location_ids: tuple[str, ...]
    parent_variant_ids: tuple[str, ...]
    merged_into_id: str | None
    transmission_root_id: str | None
    source_event_id: str | None
    last_communication_id: str | None
    strength_band: str


@dataclass(frozen=True, slots=True)
class NarrativeHopOverlay:
    protocol_version: str
    layer: str
    evidence_class: str
    owner_id: str
    variants: tuple[NarrativeHopVariant, ...]

    @property
    def count(self) -> int:
        return len(self.variants)


def project_narrative_hop_overlay(
    owner_id: str, ledger: object | None
) -> NarrativeHopOverlay:
    """Project hop-safe fields from an owner ``NarrativeLedger`` (duck-typed)."""
    if not isinstance(owner_id, str) or not owner_id:
        raise ValueError("owner_id: invalid")
    variants: list[NarrativeHopVariant] = []
    if ledger is not None:
        raw = getattr(ledger, "variants", ()) or ()
        for item in raw:
            variants.append(_variant(item))
    variants.sort(key=lambda row: row.variant_id)
    overlay = NarrativeHopOverlay(
        protocol_version=OBSERVER_PROTOCOL_VERSION,
        layer=_LAYER,
        evidence_class=_EVIDENCE_CLASS,
        owner_id=owner_id,
        variants=tuple(variants),
    )
    _LOGGER.debug(
        "narrative_ledger_projected owner_id=%s variant_count=%s",
        owner_id,
        overlay.count,
    )
    return overlay


def _variant(item: object) -> NarrativeHopVariant:
    strength = getattr(item, "strength", None)
    band = "mid"
    if type(strength) is float or type(strength) is int:
        if float(strength) < 0.34:
            band = "low"
        elif float(strength) >= 0.67:
            band = "high"
    origin = getattr(item, "origin", "")
    origin_text = getattr(origin, "value", origin)
    status = getattr(item, "status", "")
    status_text = getattr(status, "value", status)
    return NarrativeHopVariant(
        variant_id=str(getattr(item, "variant_id", "")),
        status=str(status_text),
        origin=str(origin_text),
        carrier_agent_ids=tuple(
            str(value) for value in (getattr(item, "carrier_agent_ids", ()) or ())
        ),
        location_ids=tuple(
            str(value) for value in (getattr(item, "location_ids", ()) or ())
        ),
        parent_variant_ids=tuple(
            str(value) for value in (getattr(item, "parent_variant_ids", ()) or ())
        ),
        merged_into_id=_optional_text(getattr(item, "merged_into_id", None)),
        transmission_root_id=_optional_text(
            getattr(item, "transmission_root_id", None)
        ),
        source_event_id=_optional_text(getattr(item, "source_event_id", None)),
        last_communication_id=_optional_text(
            getattr(item, "last_communication_id", None)
        ),
        strength_band=band,
    )


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


__all__ = [
    "NarrativeHopOverlay",
    "NarrativeHopVariant",
    "project_narrative_hop_overlay",
]
