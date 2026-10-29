"""Bounded shared index pages must never repeat or reorder entries."""

from __future__ import annotations

from simulation.lineage_store_index import (
    LINEAGE_INDEX_PAGE_SCHEMA,
    LineageIndexEntry,
    build_index_root,
    decode_lineage_index_page,
)


def _entry(index: int) -> LineageIndexEntry:
    key = f"scope|{index:08d}|00000000"
    return LineageIndexEntry(
        first_key=key,
        last_key=key,
        digest=f"{index:064x}",
        path=f"objects/sha256/aa/{index:064x}",
        row_count=1,
        byte_count=1,
        is_index=False,
    )


def test_byte_split_pages_keep_every_entry_exactly_once() -> None:
    entries = tuple(_entry(index) for index in range(40))
    _root, objects = build_index_root(
        "civilization-rows",
        entries,
        page_schema=LINEAGE_INDEX_PAGE_SCHEMA,
        max_bytes=1200,
    )
    leaves: list[str] = []
    for content in objects.values():
        page = decode_lineage_index_page(content, schema=LINEAGE_INDEX_PAGE_SCHEMA)
        if page.level != 1:
            continue
        keys = [entry.first_key for entry in page.entries]
        assert keys == sorted(keys)
        assert len(set(keys)) == len(keys)
        leaves.extend(keys)
    assert sorted(leaves) == [entry.first_key for entry in entries]
    assert len(leaves) == len(entries)
