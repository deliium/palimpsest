"""Durable experiment metric collection and compatible comparison (Task 16).

Separates metric-set lifecycle from objective run completion. Persists each
family idempotently through neutral repository protocols. May import analysis.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Final

from analysis.metric_service import (
    MetricBundle,
    MetricComputationInputs,
    assemble_metric_documents,
    compare_metric_documents,
    documents_compatible,
)
from analysis.models import MetricDocument
from analysis.serialization import encode_metric_document, metric_document_fingerprint
from experiments.persistence import (
    MetricDocumentRecord,
    MetricDocumentRepository,
    MetricSetLifecycle,
    MetricSetRecord,
    MetricSetRepository,
)
from simulation.evidence import EvidenceManifest, opaque_envelope_from_payload
from world.identifiers import require_stable_id

__all__ = [
    "MetricCollectionResult",
    "MetricCollectionService",
    "compare_compatible_bundles",
    "inputs_with_opt_in_metric_rows",
    "inputs_with_spatial_rows",
    "persist_metric_bundle",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.metric_collection")


@dataclass(frozen=True, slots=True)
class MetricCollectionResult:
    """Outcome of one metric-set computation and optional persistence."""

    metric_set_id: str
    lifecycle_state: MetricSetLifecycle
    bundle: MetricBundle
    persisted_families: tuple[str, ...]
    experiment_id: str | None = None
    condition_id: str | None = None


async def persist_metric_bundle(
    *,
    bundle: MetricBundle,
    manifest: EvidenceManifest,
    metric_sets: MetricSetRepository,
    metric_documents: MetricDocumentRepository,
    metric_set_id: str | None = None,
) -> MetricCollectionResult:
    """Upsert metric-set lifecycle and append documents idempotently."""
    run_id = bundle.run_id
    set_id = metric_set_id or f"metrics-{manifest.manifest_hash[:16]}"
    set_id = require_stable_id("metric_set_id", set_id)
    manifest_hash = manifest.manifest_hash

    existing = await metric_sets.get_metric_set(run_id=run_id, metric_set_id=set_id)
    if existing is None:
        record = await metric_sets.upsert_metric_set(
            MetricSetRecord(
                run_id=run_id,
                metric_set_id=set_id,
                lifecycle_state=MetricSetLifecycle.PENDING,
                evidence_manifest_hash=manifest_hash,
                lifecycle_version=0,
            )
        )
        _LOG.info(
            "metric_set_created",
            extra={
                "operation": "persist_metric_bundle",
                "run_id": run_id,
                "metric_set_id": set_id,
                "lifecycle_state": record.lifecycle_state.value,
            },
        )
    else:
        record = existing
        if record.evidence_manifest_hash != manifest_hash:
            raise ValueError("metric_set_manifest_mismatch")

    if record.lifecycle_state is MetricSetLifecycle.PENDING:
        record = await metric_sets.transition_metric_set(
            run_id=run_id,
            metric_set_id=set_id,
            expected_version=record.lifecycle_version,
            to_state=MetricSetLifecycle.RUNNING,
        )
        _LOG.info(
            "metric_set_running",
            extra={
                "operation": "persist_metric_bundle",
                "run_id": run_id,
                "metric_set_id": set_id,
                "lifecycle_state": record.lifecycle_state.value,
            },
        )

    persisted: list[str] = []
    failed = False
    for document in bundle.documents:
        envelope = opaque_envelope_from_payload(
            schema_version=document.schema_version,
            payload=encode_metric_document(document),
        )
        try:
            await metric_documents.append_metric_document(
                MetricDocumentRecord(
                    run_id=run_id,
                    metric_set_id=set_id,
                    metric_family=document.metric_family,
                    evidence_manifest_hash=manifest_hash,
                    envelope=envelope,
                )
            )
            persisted.append(document.metric_family)
            _LOG.debug(
                "metric_document_persisted",
                extra={
                    "operation": "persist_metric_bundle",
                    "run_id": run_id,
                    "metric_set_id": set_id,
                    "metric_family": document.metric_family,
                    "hash_prefix": envelope.content_hash[:12],
                },
            )
        except Exception:
            failed = True
            _LOG.error(
                "metric_document_persist_failed",
                extra={
                    "operation": "persist_metric_bundle",
                    "run_id": run_id,
                    "metric_set_id": set_id,
                    "metric_family": document.metric_family,
                    "reason_code": "persist_failed",
                },
            )
            raise

    if failed:
        final_state = MetricSetLifecycle.FAILED
    elif len(persisted) < len(bundle.documents):
        final_state = MetricSetLifecycle.PARTIAL
    else:
        final_state = MetricSetLifecycle.COMPLETE

    if record.lifecycle_state is MetricSetLifecycle.RUNNING:
        record = await metric_sets.transition_metric_set(
            run_id=run_id,
            metric_set_id=set_id,
            expected_version=record.lifecycle_version,
            to_state=final_state,
        )
        _LOG.info(
            "metric_set_transitioned",
            extra={
                "operation": "persist_metric_bundle",
                "run_id": run_id,
                "metric_set_id": set_id,
                "lifecycle_state": record.lifecycle_state.value,
                "persisted_count": len(persisted),
            },
        )

    return MetricCollectionResult(
        metric_set_id=set_id,
        lifecycle_state=record.lifecycle_state,
        bundle=bundle,
        persisted_families=tuple(persisted),
    )


def inputs_with_spatial_rows(
    inputs: MetricComputationInputs,
    events: Sequence[object] | None,
    *,
    claim_ledgers: Sequence[object] | None = None,
) -> MetricComputationInputs:
    """Attach event-log action rows. Absent events leave the family out.

    Claim rows are attached only when detached ledgers were harvested. A
    disabled run that still has an event log passes action rows and an empty
    claim sequence, so ``claim_contest`` stays absent. Neither sequence is
    written onto ``runner-result-v2``.
    """
    if events is None:
        return inputs
    from experiments.composition import (
        claim_rows_from_ledgers,
        spatial_action_rows_from_events,
    )

    action_rows = spatial_action_rows_from_events(events)
    claim_rows = () if claim_ledgers is None else claim_rows_from_ledgers(claim_ledgers)
    _LOG.debug(
        "spatial_rows_attached action_rows=%s claim_rows=%s",
        len(action_rows),
        len(claim_rows),
    )
    return replace(
        inputs,
        spatial_action_rows=action_rows,
        spatial_claim_rows=claim_rows,
    )


def inputs_with_opt_in_metric_rows(
    inputs: MetricComputationInputs,
    *,
    events: Sequence[object] | None = None,
    claim_ledgers: Sequence[object] | None = None,
    world_model_audits: Sequence[object] | None = None,
    physical_rules: object | None = None,
    belief_convergence_claims: Sequence[object] | None = None,
    cultural_naming_rows: Sequence[object] | None = None,
    cultural_norms_rows: Sequence[object] | None = None,
    cultural_conventions_rows: Sequence[object] | None = None,
    cultural_narratives_rows: Sequence[object] | None = None,
    reputation_ledgers: Sequence[object] | None = None,
    reputation_neighborhoods: Mapping[str, str] | None = None,
    reputation_target_id: str | None = None,
    survival_cohort_map: Mapping[str, Sequence[str]] | None = None,
) -> MetricComputationInputs:
    """Attach opt-in family inputs from harvested evidence when present.

    Missing harvests leave the corresponding family out of assembly (not
    zeros). Spatial rows still follow ``inputs_with_spatial_rows``.
    """
    updated = inputs_with_spatial_rows(
        inputs, events, claim_ledgers=claim_ledgers
    )
    from experiments.composition import (
        calibration_rows_from_world_model_audits,
        territorial_control_rows_from_spatial_actions,
        territorial_presence_rows_from_spatial_actions,
    )

    attached: dict[str, int] = {}
    presence = None
    control = None
    if updated.spatial_action_rows is not None:
        presence = territorial_presence_rows_from_spatial_actions(
            updated.spatial_action_rows
        )
        control = territorial_control_rows_from_spatial_actions(
            updated.spatial_action_rows
        )
        attached["territorial_presence"] = len(presence)
        attached["territorial_control"] = len(control)
        updated = replace(
            updated,
            territorial_presence_rows=presence,
            territorial_control_rows=control,
        )
    else:
        _LOG.debug(
            "opt_in_metric_skip",
            extra={"reason_code": "no_spatial_events", "block": "territorial"},
        )

    calibration = None
    if (
        world_model_audits is not None
        and events is not None
        and physical_rules is not None
    ):
        calibration = calibration_rows_from_world_model_audits(
            world_model_audits,
            events,
            physical_rules=physical_rules,
        )
        attached["prediction_calibration"] = len(calibration)
        updated = replace(updated, prediction_calibration_rows=calibration)
    elif world_model_audits is not None:
        _LOG.warning(
            "opt_in_metric_skip",
            extra={
                "reason_code": "calibration_inputs_incomplete",
                "block": "prediction_calibration",
            },
        )

    if belief_convergence_claims is not None:
        attached["belief_convergence"] = len(belief_convergence_claims)
        updated = replace(
            updated, belief_convergence_claims=belief_convergence_claims
        )
    if cultural_naming_rows is not None:
        attached["cultural_naming"] = len(cultural_naming_rows)
        updated = replace(updated, cultural_naming_rows=cultural_naming_rows)
    if cultural_norms_rows is not None:
        attached["cultural_norms"] = len(cultural_norms_rows)
        updated = replace(updated, cultural_norms_rows=cultural_norms_rows)
    if cultural_conventions_rows is not None:
        attached["cultural_conventions"] = len(cultural_conventions_rows)
        updated = replace(
            updated, cultural_conventions_rows=cultural_conventions_rows
        )
    if cultural_narratives_rows is not None:
        attached["cultural_narratives"] = len(cultural_narratives_rows)
        updated = replace(
            updated, cultural_narratives_rows=cultural_narratives_rows
        )
    if reputation_ledgers is not None:
        attached["reputation"] = len(reputation_ledgers)
        updated = replace(
            updated,
            reputation_ledgers=reputation_ledgers,
            reputation_neighborhoods=reputation_neighborhoods,
            reputation_target_id=reputation_target_id,
        )
    if survival_cohort_map is not None:
        attached["survival_cohort"] = len(survival_cohort_map)
        updated = replace(updated, survival_cohort_map=survival_cohort_map)

    _LOG.debug(
        "opt_in_metric_rows_attached",
        extra={"operation": "inputs_with_opt_in_metric_rows", "blocks": attached},
    )
    return updated


def compare_compatible_bundles(
    left: MetricBundle, right: MetricBundle
) -> Mapping[str, Mapping[str, object] | None]:
    """Compare same-family documents when schema/algorithm revisions match."""
    right_by_family = {doc.metric_family: doc for doc in right.documents}
    results: dict[str, Mapping[str, object] | None] = {}
    for left_doc in left.documents:
        right_doc = right_by_family.get(left_doc.metric_family)
        if right_doc is None:
            results[left_doc.metric_family] = None
            continue
        if not documents_compatible(left_doc, right_doc):
            _LOG.warning(
                "metric_bundle_incompatible_family",
                extra={
                    "operation": "compare_compatible_bundles",
                    "metric_family": left_doc.metric_family,
                    "reason_code": "incompatible",
                },
            )
            results[left_doc.metric_family] = None
            continue
        results[left_doc.metric_family] = compare_metric_documents(left_doc, right_doc)
    return results


class MetricCollectionService:
    """Assemble + optionally persist run-level metrics for experiment arms."""

    __slots__ = ("_sets", "_documents")

    def __init__(
        self,
        *,
        metric_sets: MetricSetRepository | None = None,
        metric_documents: MetricDocumentRepository | None = None,
    ) -> None:
        self._sets = metric_sets
        self._documents = metric_documents

    def compute(self, inputs: MetricComputationInputs) -> MetricBundle:
        return assemble_metric_documents(inputs)

    async def compute_and_persist(
        self,
        *,
        inputs: MetricComputationInputs,
        manifest: EvidenceManifest,
        experiment_id: str | None = None,
        condition_id: str | None = None,
        metric_set_id: str | None = None,
    ) -> MetricCollectionResult:
        bundle = assemble_metric_documents(inputs)
        # Same manifest → same canonical hashes.
        again = assemble_metric_documents(inputs)
        if again.fingerprints != bundle.fingerprints:
            raise ValueError("metric_nondeterministic")
        if self._sets is None or self._documents is None:
            return MetricCollectionResult(
                metric_set_id=metric_set_id or f"ephemeral-{manifest.manifest_hash[:16]}",
                lifecycle_state=MetricSetLifecycle.COMPLETE,
                bundle=bundle,
                persisted_families=(),
                experiment_id=experiment_id,
                condition_id=condition_id,
            )
        result = await persist_metric_bundle(
            bundle=bundle,
            manifest=manifest,
            metric_sets=self._sets,
            metric_documents=self._documents,
            metric_set_id=metric_set_id,
        )
        return MetricCollectionResult(
            metric_set_id=result.metric_set_id,
            lifecycle_state=result.lifecycle_state,
            bundle=result.bundle,
            persisted_families=result.persisted_families,
            experiment_id=experiment_id,
            condition_id=condition_id,
        )


def collector_fields_from_documents(
    documents: Sequence[MetricDocument],
) -> tuple[tuple[str, str | int | float], ...]:
    """Metadata-only collector fields (counts/fingerprints, never payloads)."""
    fields: list[tuple[str, str | int | float]] = [
        ("document_count", len(documents)),
    ]
    for document in sorted(documents, key=lambda item: item.metric_family):
        fields.append(
            (
                f"{document.metric_family}_fingerprint_prefix",
                metric_document_fingerprint(document)[:12],
            )
        )
        fields.append((f"{document.metric_family}_availability", document.availability.value))
    return tuple(fields)
