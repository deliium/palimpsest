"""Compose completed-run analysis into ``formal-rule-snapshot-v1``."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from typing import Any, Final, cast

from experiments.formal_rule_harvest import FormalRuleHarvest
from simulation.formal_rule_codec import (
    compute_formal_rule_publication_id,
    decode_formal_rule_snapshot,
    encode_formal_rule_snapshot,
    formal_rule_digest,
)
from simulation.formal_rule_models import (
    FORMAL_RULE_SNAPSHOT_POLICY_VERSION,
    FORMAL_RULE_SNAPSHOT_SCHEMA,
    MAX_FORMAL_RULE_CANDIDATES,
    MAX_FORMAL_RULE_RULES,
    MAX_FORMAL_RULE_VERSIONS,
    FormalRuleArtifactError,
    FormalRuleCandidateRecord,
    FormalRuleCounts,
    FormalRuleCoverage,
    FormalRuleLineageEdgeRecord,
    FormalRuleObjectiveRow,
    FormalRuleRecord,
    FormalRuleSnapshot,
    FormalRuleSnapshotRef,
    FormalRuleVersionRecord,
    FormalRuleWindowRecord,
    FormalRuleWrittenRepresentationRecord,
    derive_formal_rule_rule_id,
    derive_formal_rule_version_id,
)
from simulation.formal_rule_ports import (
    FormalRulePublication,
    FormalRulePublicationPort,
)

__all__ = [
    "FormalRuleHarvestResult",
    "build_formal_rule_harvest_result",
    "formal_rule_publication_document",
    "publish_formal_rule_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.formal_rule_publication")

_PLACEHOLDER = "frule-pub-" + "0" * 16


@dataclass(frozen=True, slots=True)
class FormalRuleHarvestResult:
    snapshot: FormalRuleSnapshot
    publication_id: str
    snapshot_digest: str
    candidate_count: int
    rule_count: int
    version_count: int
    coverage: FormalRuleCoverage
    receipt: Mapping[str, object]


def _published_rule_id(row: Any, candidate_id: str) -> str:
    return derive_formal_rule_rule_id(
        candidate_id,
        row.stage,
        row.constraint_kind,
        row.action_token,
        row.authority_kind,
    )


def _version_digest(version: object) -> str:
    return hashlib.sha256(
        json.dumps(
            asdict(cast(Any, version)),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _snapshot_coverage(value: object) -> FormalRuleCoverage:
    item = cast(Any, value)
    return FormalRuleCoverage(
        observed=item.observed,
        expected=item.expected,
        partial=item.partial,
    )


def build_formal_rule_harvest_result(
    harvest: FormalRuleHarvest,
) -> FormalRuleHarvestResult:
    """Map detached analysis into one canonical immutable snapshot."""

    if type(harvest) is not FormalRuleHarvest:
        raise TypeError("harvest must be FormalRuleHarvest")
    rows = harvest.rows
    analysis = harvest.analysis
    summary = harvest.summary
    candidate_by_rule = {
        rule_id: candidate.candidate_key
        for candidate in analysis.candidates
        for rule_id in candidate.rule_ids
    }
    candidate_rows = tuple(analysis.candidates)[:MAX_FORMAL_RULE_CANDIDATES]
    kept_candidates = {item.candidate_key for item in candidate_rows}
    kept_rules = tuple(
        row
        for row in rows.rules
        if candidate_by_rule.get(row.rule_id) in kept_candidates
    )[:MAX_FORMAL_RULE_RULES]
    kept_rule_ids = {row.rule_id for row in kept_rules}
    rule_rows = kept_rules
    version_rows = tuple(
        version for version in rows.versions if version.rule_id in kept_rule_ids
    )[:MAX_FORMAL_RULE_VERSIONS]
    truncated = (
        len(analysis.candidates) > MAX_FORMAL_RULE_CANDIDATES
        or len(rows.rules) > len(rule_rows)
        or len(rows.versions) > len(version_rows)
        or harvest.truncation is not None
    )
    authority_by_candidate = {
        item.candidate_id: item for item in summary.authority
    }
    published_rule_ids = {
        row.rule_id: _published_rule_id(
            row, candidate_by_rule[row.rule_id]
        )
        for row in rule_rows
    }
    candidate_records: list[FormalRuleCandidateRecord] = []
    for candidate in candidate_rows:
        members = tuple(
            row for row in rows.rules if row.rule_id in set(candidate.rule_ids)
        )
        authority = authority_by_candidate.get(candidate.candidate_key)
        candidate_records.append(
            FormalRuleCandidateRecord(
                candidate_id=candidate.candidate_key,
                status=candidate.status.value,
                scope_kind=candidate.scope_kind,
                scope_digest=candidate.scope_digest,
                action_token=candidate.action_token,
                constraint_kinds=tuple(
                    sorted({row.constraint_kind for row in members})
                ),
                stage=(
                    max(
                        (row.stage for row in members),
                        key=lambda value: (
                            "habit",
                            "expectation",
                            "norm",
                            "documented",
                            "recognized_enforcement",
                        ).index(value),
                    )
                    if members
                    else "habit"
                ),
                authority_kinds=tuple(
                    sorted({row.authority_kind for row in members})
                ),
                system_count=authority.system_count if authority else 0,
                rule_count=len(members),
                version_count=(
                    sum(row.version_count for row in members)
                ),
                competing_candidate_ids=tuple(
                    sorted(
                        {
                            other.candidate_key
                            for other in analysis.candidates
                            if other.candidate_key != candidate.candidate_key
                            and other.scope_digest == candidate.scope_digest
                            and other.action_token == candidate.action_token
                        }
                    )
                ),
                first_tick=candidate.first_tick,
                last_tick=candidate.last_tick,
                coverage=_snapshot_coverage(candidate.coverage),
            )
        )
    rule_records: list[FormalRuleRecord] = []
    version_records: list[FormalRuleVersionRecord] = []
    for row in rule_rows:
        written = FormalRuleWrittenRepresentationRecord(
            status=row.written_status,
            artifact_present=row.written_status != "none",
            artifact_revision=(
                None if row.written_status == "none" else row.version_count
            ),
            repository_present=False,
        )
        rule_records.append(
            FormalRuleRecord(
                rule_id=published_rule_ids[row.rule_id],
                candidate_id=next(
                    candidate.candidate_key
                    for candidate in analysis.candidates
                    if row.rule_id in set(candidate.rule_ids)
                ),
                stage=row.stage,
                constraint_kind=row.constraint_kind,
                scope_kind=row.scope_kind,
                action_token=row.action_token,
                authority_kind=row.authority_kind,
                recognition=row.recognition,
                written_representation=written,
                sanction_kinds=row.sanction_kinds,
                exception_count=row.exception_count,
                version_count=row.version_count,
                latest_version=row.version_count,
                proponent_count=sum(
                    1 for position in rows.positions if position.rule_id == row.rule_id
                ),
                response_counts=tuple(
                    sorted(
                        Counter(
                            item.kind
                            for item in rows.responses
                            if item.rule_id == row.rule_id
                        ).items()
                    )
                ),
            )
        )
        for version in version_rows:
            if version.rule_id != row.rule_id:
                continue
            version_records.append(
                FormalRuleVersionRecord(
                    version_id=derive_formal_rule_version_id(
                        published_rule_ids[row.rule_id],
                        version.version_number,
                        _version_digest(version),
                    ),
                    rule_id=published_rule_ids[row.rule_id],
                    version_number=version.version_number,
                    stage=version.stage,
                    constraint_kind=version.constraint_kind,
                    scope_kind=version.scope_kind,
                    scope_digest=version.scope_digest,
                    action_token=version.action_token,
                    authority_kind=version.authority_kind,
                    recognition=version.recognition,
                    written_representation=FormalRuleWrittenRepresentationRecord(
                        status=version.written_status,
                        artifact_present=version.written_status != "none",
                        artifact_revision=(
                            None
                            if version.written_status == "none"
                            else version.version_number
                        ),
                        repository_present=False,
                    ),
                    sanction_kinds=(),
                    exception_count=0,
                    tick=version.tick,
                    revision_kind=version.revision_kind,
                    supersedes_version_id=(
                        None
                        if version.version_number == 1
                        else derive_formal_rule_version_id(
                            published_rule_ids[row.rule_id],
                            version.version_number - 1,
                            _version_digest(
                                next(
                                    item
                                    for item in version_rows
                                    if item.rule_id == row.rule_id
                                    and item.version_number
                                    == version.version_number - 1
                                )
                            ),
                        )
                    ),
                )
            )
    objective_records = tuple(
        FormalRuleObjectiveRow(
            tick=item.tick,
            observed_artifact_count=item.observed_artifact_count,
            observed_repository_count=item.observed_repository_count,
            observed_occurrence_count=item.observed_occurrence_count,
        )
        for item in harvest.layers.objective
    )
    window_records_list: list[FormalRuleWindowRecord] = []
    for window in harvest.windows:
        item = cast(Any, window)
        window_records_list.append(
            FormalRuleWindowRecord(
                start_tick=item.start_tick,
                end_tick=item.end_tick,
                owner_count=len(getattr(item, "owner_rows", ())),
                candidate_count=len(getattr(item, "rule_ids", ())),
            )
        )
    window_records = tuple(window_records_list)
    edge_records = tuple(
        FormalRuleLineageEdgeRecord(
            edge_id=edge.edge_id,
            source_candidate_id=edge.source_candidate_id,
            target_candidate_id=edge.target_candidate_id,
            kind=edge.kind.value,
            tick=edge.tick,
            jaccard=edge.jaccard,
            containment=edge.containment,
        )
        for edge in analysis.edges
    )
    coverage = harvest.coverage
    provenance_code = (
        "truncated"
        if truncated
        else "empty"
        if not candidate_records and not rule_records
        else "partial"
        if coverage.partial
        else "ok"
    )
    snapshot = FormalRuleSnapshot(
        ref=FormalRuleSnapshotRef(
            run_id=harvest.run_id,
            input_revision=harvest.input_revision,
            generated_tick=harvest.generated_tick,
            publication_id=_PLACEHOLDER,
        ),
        candidates=tuple(candidate_records),
        rules=tuple(rule_records),
        versions=tuple(version_records),
        lineage=edge_records,
        objective_rows=objective_records,
        windows=window_records,
        coverage=_snapshot_coverage(coverage),
        counts=FormalRuleCounts(
            candidates=len(candidate_records),
            rules=len(rule_records),
            versions=len(version_records),
            objective_rows=len(objective_records),
            windows=len(window_records),
        ),
        provenance_code=provenance_code,
    )
    finalized = _finalize(snapshot, truncated=truncated)
    _LOG.info(
        "formal_rule_publication_built candidates=%s rules=%s versions=%s",
        len(candidate_records),
        len(rule_records),
        len(version_records),
    )
    return finalized


def _finalize(
    snapshot: FormalRuleSnapshot, *, truncated: bool
) -> FormalRuleHarvestResult:
    provisional = replace(
        snapshot, ref=replace(snapshot.ref, publication_id=_PLACEHOLDER)
    )
    publication_id = compute_formal_rule_publication_id(provisional)
    published = replace(
        provisional, ref=replace(provisional.ref, publication_id=publication_id)
    )
    payload = encode_formal_rule_snapshot(published)
    decoded = decode_formal_rule_snapshot(payload)
    if encode_formal_rule_snapshot(decoded) != payload:
        raise FormalRuleArtifactError("formal_rule_digest_mismatch")
    digest = formal_rule_digest(payload)
    receipt = {
        "status": "published",
        "schema_version": FORMAL_RULE_SNAPSHOT_SCHEMA,
        "policy_version": FORMAL_RULE_SNAPSHOT_POLICY_VERSION,
        "candidate_count": len(published.candidates),
        "rule_count": len(published.rules),
        "version_count": len(published.versions),
        "coverage": {
            "observed": published.coverage.observed,
            "expected": published.coverage.expected,
            "partial": published.coverage.partial,
        },
        "publication_id": publication_id,
        "snapshot_digest": digest,
        "truncated": truncated,
    }
    return FormalRuleHarvestResult(
        snapshot=published,
        publication_id=publication_id,
        snapshot_digest=digest,
        candidate_count=len(published.candidates),
        rule_count=len(published.rules),
        version_count=len(published.versions),
        coverage=published.coverage,
        receipt=receipt,
    )


def publish_formal_rule_snapshot(
    built: FormalRuleHarvestResult,
    publisher: FormalRulePublicationPort,
) -> None:
    """Publish one finalized snapshot through the injected port exactly once."""
    if type(built) is not FormalRuleHarvestResult:
        raise TypeError("built must be FormalRuleHarvestResult")
    publisher.publish(
        FormalRulePublication(
            run_id=built.snapshot.ref.run_id,
            publication_id=built.publication_id,
            snapshot_digest=built.snapshot_digest,
            payload=encode_formal_rule_snapshot(built.snapshot),
            generated_tick=built.snapshot.ref.generated_tick,
        )
    )


def formal_rule_publication_document(
    built: FormalRuleHarvestResult,
) -> dict[str, object]:
    """Return a metadata-only publication receipt."""
    if type(built) is not FormalRuleHarvestResult:
        raise TypeError("built must be FormalRuleHarvestResult")
    return dict(built.receipt)
