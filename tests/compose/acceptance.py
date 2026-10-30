"""Required-versus-optional gating for published-image acceptance lanes.

Release acceptance sets ``PALIMPSEST_V3_ACCEPTANCE_REQUIRED=1``. In that mode a
missing Docker CLI, browser driver or application image is a failure: a skipped
required lane must never look like a green release gate. Optional local runs
keep the convenience skip and report the reason explicitly.
"""

from __future__ import annotations

import os
from typing import Final, NoReturn

import pytest

ACCEPTANCE_REQUIRED_ENV: Final[str] = "PALIMPSEST_V3_ACCEPTANCE_REQUIRED"


def acceptance_required() -> bool:
    """Return whether this run must execute every acceptance lane."""

    return os.environ.get(ACCEPTANCE_REQUIRED_ENV, "").strip() == "1"


def require_prerequisite(prerequisite: str) -> NoReturn:
    """Stop the lane: skip when optional, fail closed when acceptance is required."""

    if acceptance_required():
        pytest.fail(
            f"{prerequisite}; required release acceptance cannot skip "
            f"({ACCEPTANCE_REQUIRED_ENV}=1)"
        )
    pytest.skip(prerequisite)
