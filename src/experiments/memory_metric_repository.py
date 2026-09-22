"""In-memory metric-set / truth-spec repositories for unit tests."""

from __future__ import annotations

from experiments.persistence import (
    MetricDocumentRecord,
    MetricSetLifecycle,
    MetricSetRecord,
    TruthSpecRecord,
)

_ALLOWED: dict[MetricSetLifecycle, frozenset[MetricSetLifecycle]] = {
    MetricSetLifecycle.PENDING: frozenset(
        {MetricSetLifecycle.RUNNING, MetricSetLifecycle.FAILED}
    ),
    MetricSetLifecycle.RUNNING: frozenset(
        {
            MetricSetLifecycle.COMPLETE,
            MetricSetLifecycle.PARTIAL,
            MetricSetLifecycle.FAILED,
        }
    ),
    MetricSetLifecycle.PARTIAL: frozenset(
        {
            MetricSetLifecycle.COMPLETE,
            MetricSetLifecycle.FAILED,
            MetricSetLifecycle.RUNNING,
        }
    ),
    MetricSetLifecycle.COMPLETE: frozenset(),
    MetricSetLifecycle.FAILED: frozenset(),
}


class InMemoryTruthSpecRepository:
    __slots__ = ("_rows",)

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], TruthSpecRecord] = {}

    async def append_truth_spec(self, record: TruthSpecRecord) -> None:
        key = (record.run_id, record.claim_id)
        existing = self._rows.get(key)
        if existing is not None:
            if existing == record:
                return
            raise ValueError("truth_spec_conflict")
        self._rows[key] = record

    async def get_truth_spec(
        self, *, run_id: str, claim_id: str
    ) -> TruthSpecRecord | None:
        return self._rows.get((run_id, claim_id))

    async def list_truth_specs(
        self, *, run_id: str
    ) -> tuple[TruthSpecRecord, ...]:
        items = [item for item in self._rows.values() if item.run_id == run_id]
        items.sort(key=lambda item: item.claim_id)
        return tuple(items)


class InMemoryMetricSetRepository:
    __slots__ = ("_rows",)

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], MetricSetRecord] = {}

    async def upsert_metric_set(self, record: MetricSetRecord) -> MetricSetRecord:
        key = (record.run_id, record.metric_set_id)
        existing = self._rows.get(key)
        if existing is not None:
            if existing == record:
                return existing
            raise ValueError("metric_set_conflict")
        self._rows[key] = record
        return record

    async def get_metric_set(
        self, *, run_id: str, metric_set_id: str
    ) -> MetricSetRecord | None:
        return self._rows.get((run_id, metric_set_id))

    async def transition_metric_set(
        self,
        *,
        run_id: str,
        metric_set_id: str,
        expected_version: int,
        to_state: MetricSetLifecycle,
    ) -> MetricSetRecord:
        key = (run_id, metric_set_id)
        current = self._rows.get(key)
        if current is None:
            raise KeyError("metric_set_missing")
        if current.lifecycle_version != expected_version:
            raise ValueError("version_conflict")
        if current.lifecycle_state == to_state:
            return current
        if to_state not in _ALLOWED.get(current.lifecycle_state, frozenset()):
            raise ValueError("illegal_metric_set_transition")
        updated = MetricSetRecord(
            run_id=current.run_id,
            metric_set_id=current.metric_set_id,
            lifecycle_state=to_state,
            evidence_manifest_hash=current.evidence_manifest_hash,
            lifecycle_version=expected_version + 1,
        )
        self._rows[key] = updated
        return updated


class InMemoryMetricDocumentRepository:
    __slots__ = ("_rows", "_sets")

    def __init__(
        self, metric_sets: InMemoryMetricSetRepository | None = None
    ) -> None:
        self._rows: dict[tuple[str, str, str], MetricDocumentRecord] = {}
        self._sets = metric_sets

    async def append_metric_document(self, record: MetricDocumentRecord) -> None:
        if self._sets is not None:
            metric_set = await self._sets.get_metric_set(
                run_id=record.run_id, metric_set_id=record.metric_set_id
            )
            if metric_set is None:
                raise ValueError("metric_set_missing")
            if metric_set.evidence_manifest_hash != record.evidence_manifest_hash:
                raise ValueError("evidence_revision_mismatch")
        key = (record.run_id, record.metric_set_id, record.metric_family)
        existing = self._rows.get(key)
        if existing is not None:
            if existing == record:
                return
            raise ValueError("metric_document_conflict")
        self._rows[key] = record

    async def get_metric_document(
        self, *, run_id: str, metric_set_id: str, metric_family: str
    ) -> MetricDocumentRecord | None:
        return self._rows.get((run_id, metric_set_id, metric_family))

    async def list_metric_documents(
        self, *, run_id: str, metric_set_id: str | None = None
    ) -> tuple[MetricDocumentRecord, ...]:
        items = [
            item
            for item in self._rows.values()
            if item.run_id == run_id
            and (metric_set_id is None or item.metric_set_id == metric_set_id)
        ]
        items.sort(key=lambda item: (item.metric_set_id, item.metric_family))
        return tuple(items)
