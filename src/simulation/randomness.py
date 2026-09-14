"""Isolated random streams derived from an explicit simulation seed.

This is the only module allowed to import :mod:`random`. Callers receive
private :class:`random.Random` instances; module-level ``random.*`` functions
are never used.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from simulation.models import DERIVATION_VERSION, SimulationRunConfig, require_seed


@dataclass(frozen=True, slots=True)
class StreamScope:
    """Canonical stream identity. Distinct name tuples never share a digest."""

    namespace: str
    names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("StreamScope.namespace must be a non-empty string")
        if not self.names:
            raise ValueError("StreamScope.names must contain at least one name")
        for name in self.names:
            if not name:
                raise ValueError("StreamScope names must be non-empty strings")


def canonical_scope_bytes(scope: StreamScope) -> bytes:
    """Length-prefixed encoding so ('ab','c') does not alias ('a','bc')."""
    chunks = [_length_prefixed(scope.namespace.encode("utf-8"))]
    for name in scope.names:
        chunks.append(_length_prefixed(name.encode("utf-8")))
    return b"".join(chunks)


def _length_prefixed(value: bytes) -> bytes:
    return len(value).to_bytes(4, "big") + value


def derive_stream_seed(config: SimulationRunConfig, scope: StreamScope) -> int:
    hasher = hashlib.sha256()
    hasher.update(DERIVATION_VERSION.encode("utf-8"))
    hasher.update(_length_prefixed(b"stream"))
    hasher.update(_length_prefixed(str(config.seed).encode("utf-8")))
    hasher.update(canonical_scope_bytes(scope))
    return int.from_bytes(hasher.digest(), "big")


def create_rng(seed: int) -> random.Random:
    """Return a private ``Random`` instance for ``seed``.

    The process-global random module state is not read or written.
    """
    return random.Random(require_seed(seed))


def create_named_stream(
    config: SimulationRunConfig, scope: StreamScope
) -> random.Random:
    """Derive an independent stream from canonical seed and scope inputs."""
    return random.Random(derive_stream_seed(config, scope))


def sample_stream(
    config: SimulationRunConfig, scope: StreamScope, count: int
) -> tuple[int, ...]:
    """Draw ``count`` bounded integers from a fresh named stream."""
    rng = create_named_stream(config, scope)
    return tuple(rng.randrange(1_000_000_000) for _ in range(count))
