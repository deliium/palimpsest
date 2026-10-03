"""Kind-and-name presentation tokens. Not stored on world objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass

_LOGGER = logging.getLogger("observer.project")

_FORBIDDEN = frozenset(
    {"pixels", "sprite", "animation", "dx", "dy", "screen_x", "screen_y"}
)

_ARTIFACT_KINDS = (
    "mark",
    "sign",
    "note",
    "map",
    "record",
    "memorial",
)


@dataclass(frozen=True, slots=True)
class EntityPresentation:
    """Display tokens for one kind and name. No coordinates."""

    visual_category: str
    icon_key: str
    size_category: str
    display_label: str | None = None


def _token(
    visual_category: str,
    icon_key: str,
    size_category: str,
    *,
    display_label: str | None = None,
) -> EntityPresentation:
    fields = {
        "visual_category": visual_category,
        "icon_key": icon_key,
        "size_category": size_category,
    }
    values = set(fields.values())
    if display_label is not None:
        values.add(display_label)
    forbidden = _FORBIDDEN.intersection(fields) | _FORBIDDEN.intersection(values)
    if forbidden:
        _LOGGER.error(
            "presentation_instruction_forbidden reason_code=%s",
            "presentation_instruction_forbidden",
        )
        raise ValueError("presentation_instruction_forbidden")
    return EntityPresentation(
        visual_category=visual_category,
        icon_key=icon_key,
        size_category=size_category,
        display_label=display_label,
    )


_BY_KIND_AND_NAME: dict[tuple[str, str], EntityPresentation] = {
    ("resource", "wood"): _token("resource", "wood", "small"),
    ("resource", "stone"): _token("resource", "stone", "small"),
    ("material", "wood"): _token("material", "wood", "small"),
    ("material", "stone"): _token("material", "stone", "small"),
    ("tool", "tool"): _token("tool", "tool", "small"),
    ("food", "food"): _token("food", "food", "small"),
    ("shelter", "shelter"): _token("shelter", "shelter", "large"),
    ("store", "store"): _token("store", "store", "large"),
}
for _kind in _ARTIFACT_KINDS:
    _BY_KIND_AND_NAME[(_kind, _kind)] = _token(
        "artifact",
        f"artifact_{_kind}",
        "small",
        display_label=_kind,
    )


def entity_presentation(kind: str, name: str) -> EntityPresentation | None:
    """Return tokens for a kind and name, or None when the catalog has no row."""
    if type(kind) is not str or type(name) is not str:
        return None
    return _BY_KIND_AND_NAME.get((kind, name))


__all__ = ["EntityPresentation", "entity_presentation"]
