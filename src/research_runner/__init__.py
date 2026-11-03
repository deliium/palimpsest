"""Composition root for matrix experiment CLI (no HTTP / no api imports)."""

from research_runner.composition import resolve_code_revision, resolve_package_version
from research_runner.dispute_composition import (
    DisputeProducerOptions,
    producer_options_from_args,
    publish_dispute_harvest,
    write_dispute_receipt,
)

__all__ = [
    "DisputeProducerOptions",
    "producer_options_from_args",
    "publish_dispute_harvest",
    "resolve_code_revision",
    "resolve_package_version",
    "write_dispute_receipt",
]
