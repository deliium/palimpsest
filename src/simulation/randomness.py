"""Isolated random streams derived from an explicit simulation seed.

This is the only module allowed to import :mod:`random`. Callers receive
private :class:`random.Random` instances; module-level ``random.*`` functions
are never used.
"""

from __future__ import annotations

import random
from typing import Final

DERIVATION_VERSION: Final[str] = "v1"


def create_rng(seed: int) -> random.Random:
    """Return a private ``Random`` instance for ``seed``.

    The process-global random module state is not read or written.
    """
    return random.Random(seed)


__all__ = ["DERIVATION_VERSION", "create_rng"]
