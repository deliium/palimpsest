"""Chunked immutable history sequence laws and structural sharing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from simulation._history import HistorySequence


@dataclass(frozen=True, slots=True)
class _Item:
    tick: int
    value: str


def test_empty_append_returns_self_and_sequence_laws() -> None:
    base = HistorySequence[_Item]()
    assert base.append(()) is base
    seq = base.append((_Item(0, "a"),)).append(
        (_Item(0, "b"), _Item(1, "c"))
    )
    assert len(seq) == 3
    assert list(seq) == [
        _Item(0, "a"),
        _Item(0, "b"),
        _Item(1, "c"),
    ]
    assert list(reversed(seq)) == [
        _Item(1, "c"),
        _Item(0, "b"),
        _Item(0, "a"),
    ]
    assert seq[0] == _Item(0, "a")
    assert seq[-1] == _Item(1, "c")
    assert seq[-3] == _Item(0, "a")
    assert seq[1:] == (_Item(0, "b"), _Item(1, "c"))
    with pytest.raises(IndexError):
        _ = seq[3]
    with pytest.raises(IndexError):
        _ = seq[-4]


def test_append_does_not_mutate_prior_sequence() -> None:
    first = HistorySequence.from_iterable((_Item(0, "a"),))
    second = first.append((_Item(1, "b"),))
    assert first.to_tuple() == (_Item(0, "a"),)
    assert second.to_tuple() == (_Item(0, "a"), _Item(1, "b"))
    assert first.chunk_start_tick == 0
    assert first.chunk_end_tick == 0
    assert second.chunk_end_tick == 1


def test_100000_single_item_appends_are_iterative() -> None:
    seq = HistorySequence[_Item]()
    for index in range(100_000):
        seq = seq.append((_Item(index, str(index)),))
    assert len(seq) == 100_000
    assert seq[99_999].tick == 99_999
    assert next(reversed(seq)).tick == 99_999
    assert seq.to_tuple()[0].tick == 0


def test_slicing_materializes_only_the_result() -> None:
    seq = HistorySequence.from_iterable(
        _Item(index, str(index)) for index in range(10)
    )
    subset = seq[2:5]
    assert isinstance(subset, tuple)
    assert [item.tick for item in subset] == [2, 3, 4]
