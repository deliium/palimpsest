"""Argparse CLI for reproducible experiment matrices (no FastAPI)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from experiments.matrix_aggregate import (
    build_matrix_aggregate,
    encode_matrix_aggregate,
)
from experiments.matrix_expand import expand_matrix
from experiments.matrix_models import matrix_spec_fingerprint
from experiments.matrix_runner import MatrixBatchRunner
from experiments.matrix_serialization import decode_matrix_spec
from research_runner.composition import (
    build_batch_dependencies,
    build_manifest_store,
)

_LOG: Final[logging.Logger] = logging.getLogger("research_runner.cli")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s %(message)s",
    )


def _load_spec(path: Path):
    payload = path.read_bytes()
    return decode_matrix_spec(payload)


def _cmd_run(args: argparse.Namespace) -> int:
    spec = _load_spec(Path(args.matrix))
    store = build_manifest_store(Path(args.manifest_root))
    deps = build_batch_dependencies(code_revision=args.code_revision)
    runner = MatrixBatchRunner(deps)
    _LOG.info(
        "cli_matrix_run",
        extra={
            "experiment": {
                "command": "run",
                "matrix_id": spec.matrix_id,
                "manifest_root": str(args.manifest_root),
            }
        },
    )
    result = asyncio.run(runner.run(spec, store))
    aggregate = build_matrix_aggregate(
        matrix_id=spec.matrix_id,
        matrix_fingerprint=result.matrix_fingerprint,
        cells=result.cells,
        arm_results=result.arm_results,
    )
    out = Path(args.manifest_root) / "aggregate.json"
    out.write_bytes(encode_matrix_aggregate(aggregate))
    _LOG.info(
        "cli_matrix_run_complete",
        extra={
            "experiment": {
                "completed": result.completed,
                "failed": result.failed,
                "skipped_valid": result.skipped_valid,
            }
        },
    )
    if args.print_fingerprint:
        print(result.matrix_fingerprint)
    return 0 if result.failed == 0 else 1


def _cmd_resume(args: argparse.Namespace) -> int:
    # Resume is identical to run against an existing manifest root.
    return _cmd_run(args)


def _cmd_status(args: argparse.Namespace) -> int:
    store = build_manifest_store(Path(args.manifest_root))
    header = store.open()
    records = store.list_cells()
    counts: dict[str, int] = {}
    for record in records:
        counts[record.state.value] = counts.get(record.state.value, 0) + 1
    _LOG.info(
        "cli_matrix_status",
        extra={
            "experiment": {
                "command": "status",
                "matrix_id": header.matrix_id,
                "cell_counts": counts,
            }
        },
    )
    print(f"matrix_id={header.matrix_id}")
    print(f"fingerprint_prefix={header.matrix_fingerprint[:12]}")
    for state, count in sorted(counts.items()):
        print(f"{state}={count}")
    if args.print_fingerprint:
        print(header.matrix_fingerprint)
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    spec = _load_spec(Path(args.matrix))
    _definition, cells = expand_matrix(spec)
    store = build_manifest_store(Path(args.manifest_root))
    header = store.open()
    fingerprint = matrix_spec_fingerprint(spec)
    if header.matrix_fingerprint != fingerprint:
        _LOG.error(
            "cli_aggregate_fingerprint_mismatch",
            extra={"experiment": {"reason_code": "fingerprint_mismatch"}},
        )
        return 2
    # Aggregate from completion sidecars only when arm results unavailable —
    # status-only aggregate emits empty arm_results refs from completed cells.
    aggregate = build_matrix_aggregate(
        matrix_id=spec.matrix_id,
        matrix_fingerprint=fingerprint,
        cells=cells,
        arm_results=(),
    )
    out = Path(args.aggregate_out or (Path(args.manifest_root) / "aggregate.json"))
    out.write_bytes(encode_matrix_aggregate(aggregate))
    _LOG.info(
        "cli_matrix_aggregate",
        extra={
            "experiment": {
                "command": "aggregate",
                "matrix_id": spec.matrix_id,
                "cell_count": len(cells),
            }
        },
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="palimpsest-matrix",
        description="Run resumable experiment matrices (no HTTP).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )
    parser.add_argument(
        "--print-fingerprint",
        action="store_true",
        help="Print matrix fingerprint (metadata only)",
    )
    parser.add_argument(
        "--code-revision",
        default=None,
        help="Optional injected code revision (else PALIMPSEST_CODE_REVISION)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Expand and run a matrix batch")
    run_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    run_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    run_p.set_defaults(func=_cmd_run)

    resume_p = sub.add_parser("resume", help="Resume an existing matrix batch")
    resume_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    resume_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    resume_p.set_defaults(func=_cmd_resume)

    status_p = sub.add_parser("status", help="Show cell state counts")
    status_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    status_p.set_defaults(func=_cmd_status)

    agg_p = sub.add_parser("aggregate", help="Write matrix-aggregate-v1 JSON")
    agg_p.add_argument("--matrix", required=True, help="Path to matrix JSON")
    agg_p.add_argument(
        "--manifest-root",
        required=True,
        help="Directory for manifest.json + cells/",
    )
    agg_p.add_argument(
        "--aggregate-out",
        default=None,
        help="Optional aggregate output path",
    )
    agg_p.set_defaults(func=_cmd_aggregate)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    _configure_logging(args.verbose)
    _LOG.info(
        "cli_start",
        extra={"experiment": {"command": args.command}},
    )
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
