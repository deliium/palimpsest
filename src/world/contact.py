"""Immutable optional cultural-contact contracts; no mutation or event deps."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

_LOG: Final[logging.Logger] = logging.getLogger("world.contact")


class ContactMode(StrEnum):
    DISABLED = "disabled"
    DETERMINISTIC = "deterministic"


def _fail(field_name: str, code: str) -> ValueError:
    _LOG.debug("contact_validation_failed field=%s reason_code=%s", field_name, code)
    return ValueError(f"{field_name}: {code}")


@dataclass(frozen=True, slots=True)
class CulturalContactSpec:
    """Exact contact gate. ``mode`` is the only accepted key."""

    mode: ContactMode

    def __post_init__(self) -> None:
        if type(self.mode) is not ContactMode:
            raise _fail("mode", "invalid_mode")
        _LOG.debug("contact_spec_validated mode=%s", self.mode.value)

    @property
    def enabled(self) -> bool:
        return self.mode is ContactMode.DETERMINISTIC

    def canonical(self) -> dict[str, object]:
        return {"mode": self.mode.value}


__all__ = [
    "ContactMode",
    "CulturalContactSpec",
]
