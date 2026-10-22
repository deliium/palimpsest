"""Private immutable chunked history with structural sharing.

The sequence preserves complete ordered history. Appending a chunk allocates a
new node plus the chunk, never a copy of the prior prefix. Random indexing is
linear; exports materialize explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from typing import Final, overload


def _tick_range[T](chunk: tuple[T, ...]) -> tuple[int | None, int | None]:
    ticks: list[int] = []
    for item in chunk:
        tick = getattr(item, "tick", None)
        if type(tick) is int:
            ticks.append(tick)
    if not ticks:
        return (None, None)
    return (min(ticks), max(ticks))


class HistorySequence[T](Sequence[T]):
    """Immutable chunked sequence with O(new chunk) append cost."""

    __slots__ = ("_chunk", "_end_tick", "_length", "_previous", "_start_tick")

    def __init__(
        self,
        *,
        previous: HistorySequence[T] | None = None,
        chunk: tuple[T, ...] = (),
    ) -> None:
        self._previous: Final = previous
        self._chunk: Final = chunk
        self._length: Final = (0 if previous is None else len(previous)) + len(chunk)
        start, end = _tick_range(chunk)
        self._start_tick = start
        self._end_tick = end

    @classmethod
    def from_iterable(cls, values: Iterable[T]) -> HistorySequence[T]:
        chunk = tuple(values)
        if not chunk:
            return cls()
        return cls(chunk=chunk)

    def append(self, values: Iterable[T]) -> HistorySequence[T]:
        chunk = tuple(values)
        if not chunk:
            return self
        return HistorySequence(previous=self, chunk=chunk)

    def to_tuple(self) -> tuple[T, ...]:
        chunks: list[tuple[T, ...]] = []
        node: HistorySequence[T] | None = self
        while node is not None:
            if node._chunk:
                chunks.append(node._chunk)
            node = node._previous
        chunks.reverse()
        return tuple(item for chunk in chunks for item in chunk)

    @property
    def chunk_start_tick(self) -> int | None:
        return self._start_tick

    @property
    def chunk_end_tick(self) -> int | None:
        return self._end_tick

    def __len__(self) -> int:
        return self._length

    def __iter__(self) -> Iterator[T]:
        chunks: list[tuple[T, ...]] = []
        node: HistorySequence[T] | None = self
        while node is not None:
            if node._chunk:
                chunks.append(node._chunk)
            node = node._previous
        for chunk in reversed(chunks):
            yield from chunk

    def __reversed__(self) -> Iterator[T]:
        node: HistorySequence[T] | None = self
        while node is not None:
            yield from reversed(node._chunk)
            node = node._previous

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[T, ...]: ...

    def __getitem__(self, index: int | slice) -> T | tuple[T, ...]:
        if isinstance(index, slice):
            return self.to_tuple()[index]
        if type(index) is not int:
            raise TypeError("HistorySequence indices must be int or slice")
        normalized = index + self._length if index < 0 else index
        if normalized < 0 or normalized >= self._length:
            raise IndexError("HistorySequence index out of range")
        remaining = normalized
        for item in self:
            if remaining == 0:
                return item
            remaining -= 1
        raise IndexError("HistorySequence index out of range")

    def __repr__(self) -> str:
        return f"HistorySequence(length={self._length})"


__all__ = ["HistorySequence"]
