"""Composition root for matrix experiment CLI (no HTTP / no api imports)."""

from research_runner.composition import resolve_code_revision, resolve_package_version
from research_runner.dispute_composition import (
    DisputeProducerOptions,
    producer_options_from_args,
    publish_dispute_harvest,
    write_dispute_receipt,
)
from research_runner.evidence_testimony_composition import (
    EvidenceTestimonyProducerOptions,
    publish_evidence_testimony_harvest,
    write_evidence_testimony_receipt,
)
from research_runner.evidence_testimony_composition import (
    producer_options_from_args as evidence_producer_options_from_args,
)

__all__ = [
    "DisputeProducerOptions",
    "EvidenceTestimonyProducerOptions",
    "evidence_producer_options_from_args",
    "producer_options_from_args",
    "publish_dispute_harvest",
    "publish_evidence_testimony_harvest",
    "resolve_code_revision",
    "resolve_package_version",
    "write_dispute_receipt",
    "write_evidence_testimony_receipt",
]
