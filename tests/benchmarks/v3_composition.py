"""Fixed composition evidence for the V3 scale envelope.

Retirement trials come from real benchmark artifacts. Capture spooling and
physical paging are exercised by focused tests; those rows cite exact test node
identifiers and never claim benchmark-scale capacity.
"""

from __future__ import annotations

from tests.benchmarks.v3_support import CompositionStatus, CompositionTrial


def builtin_composition_trials() -> tuple[CompositionTrial, ...]:
    """Return the fixed spool and paging off/on evidence rows."""
    return (
        CompositionTrial(
            name="capture-spool",
            variant="off",
            status=CompositionStatus.TESTED,
            scope="test-level",
            evidence=(
                "tests/unit/test_evidence_spool.py::test_capture_off_never_touches_spool",
            ),
            notes=(
                "default in-memory capture; capture-off performs no spool I/O",
                "test evidence, not a benchmark measurement",
            ),
        ),
        CompositionTrial(
            name="capture-spool",
            variant="on",
            status=CompositionStatus.TESTED,
            scope="test-level",
            evidence=(
                "tests/unit/test_evidence_spool.py::test_spooled_cultural_recorder_source_parity_and_no_hot_frames",
                "tests/unit/test_evidence_spool.py::test_streamed_canonical_evidence_matches_legacy_bytes_and_digest",
                "tests/unit/test_evidence_spool.py::test_run_scoped_spool_factory_isolates_runs_and_capture_off_skips_it",
                "tests/benchmarks/test_cultural_publication_rss.py::test_streamed_publication_rss_stays_below_artifact_size",
            ),
            notes=(
                "append-only filesystem spool with streamed canonical publication",
                "RSS evidence is an opt-in synthetic benchmark, not a capacity claim",
            ),
        ),
        CompositionTrial(
            name="physical-paging",
            variant="off",
            status=CompositionStatus.TESTED,
            scope="test-level",
            evidence=(
                "tests/unit/test_lineage_filesystem.py::test_old_v1_layout_and_new_v2_layout_read_identically",
                "tests/unit/test_civilization_filesystem.py::test_v1_fallback_reads_match_v2_layout",
            ),
            notes=(
                "sealed v1 publications remain readable without a v2 root",
                "test evidence, not a benchmark measurement",
            ),
        ),
        CompositionTrial(
            name="physical-paging",
            variant="on",
            status=CompositionStatus.TESTED,
            scope="test-level",
            evidence=(
                "tests/unit/test_lineage_filesystem.py::test_v2_root_is_bounded_and_physical_objects_are_reused",
                "tests/unit/test_lineage_filesystem.py::test_high_degree_neighbors_and_capture_read_every_continuation",
                "tests/unit/test_lineage_filesystem.py::test_catalogue_pagination_reaches_every_node_across_physical_pages",
                "tests/unit/test_civilization_filesystem.py::test_v2_deep_row_read_skips_prior_shards_and_root_is_bounded",
            ),
            notes=(
                "lineage pages cap at 256 entries; civilization roots cap at 64 KiB",
                "test evidence, not a benchmark measurement",
            ),
        ),
    )


__all__ = ["builtin_composition_trials"]
