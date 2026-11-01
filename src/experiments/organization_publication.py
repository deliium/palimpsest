"""The only bridge from organization analysis to the published artifact.

The bridge composes detached analysis into one canonical snapshot and injects it
through the publication port. It never runs inside simulation, API, or
persistence, never mutates the snapshot after encoding, and a storage failure
changes only the publication receipt, never scientific status.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Final

from agents.cognition import organization_publication_operation_id
from analysis.organization_detection import OrganizationCandidate
from analysis.organization_identity import OrganizationRecord
from analysis.organization_operations import organization_operation_sources
from experiments.organization_harvest import OrganizationHarvest
from simulation.organization_codec import (
    compute_organization_publication_id,
    decode_organization_snapshot,
    encode_organization_snapshot,
    organization_digest,
)
from simulation.organization_models import (
    MAX_CANDIDATE_OPERATIONS,
    MAX_SNAPSHOT_MEMBERS,
    MAX_SNAPSHOT_OPERATIONS,
    ORGANIZATION_SNAPSHOT_POLICY_VERSION,
    ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
    OrganizationArtifactError,
    OrganizationCandidateRecord,
    OrganizationCoverage,
    OrganizationLineageEdgeRecord,
    OrganizationMemberRecord,
    OrganizationObjectiveRow,
    OrganizationOperationRecord,
    OrganizationSnapshot,
    OrganizationStructuralRecord,
    OrganizationWindowRecord,
    upgrade_organization_snapshot,
)
from simulation.organization_ports import (
    OrganizationPublication,
    OrganizationPublicationPort,
)

__all__ = [
    "OrganizationHarvestResult",
    "build_organization_harvest_result",
    "organization_publication_document",
    "publish_organization_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger("experiments.organization_publication")

_STATUS_RANK: Final[dict[str, int]] = {
    "explicit": 0,
    "disputed": 1,
    "perceived": 2,
    "unknown": 3,
    "former": 4,
}
_STRENGTH: Final[dict[str, float]] = {
    "explicit": 1.0,
    "disputed": 0.5,
    "perceived": 0.75,
    "unknown": 0.25,
    "former": 0.1,
}
_OBJECTIVE_ANCHOR_KINDS: Final[frozenset[str]] = frozenset(
    {
        "item",
        "resource",
        "artifact",
        "structure",
        "repository",
        "collective_project",
        "commitment",
    }
)
_FAMILY_DOMAINS: Final[dict[str, str]] = {
    "admissions": "membership_admission",
    "departures": "membership_departure",
    "assignments": "role_assignment",
    "procedures": "procedure_action",
    "commitments": "internal_commitment",
}
_KNOWN_AUTHORITY: Final[frozenset[str]] = frozenset(
    {"self_authored", "role_belief", "decision_belief", "procedure_belief"}
)
_OPERATION_SOURCES: Final[tuple[str, ...]] = (
    "controls",
    "admissions",
    "departures",
    "assignments",
    "procedures",
    "commitments",
    "decisions",
    "actions",
)


@dataclass(frozen=True, slots=True)
class OrganizationHarvestResult:
    snapshot: OrganizationSnapshot
    publication_id: str
    snapshot_bytes: bytes
    provenance_code: str
    schema_version: str = ORGANIZATION_SNAPSHOT_SCHEMA_VERSION
    operation_count: int = 0
    contested_operation_count: int = 0

    @property
    def snapshot_digest(self) -> str:
        return organization_digest(self.snapshot_bytes)


def _member_records(
    candidate: OrganizationCandidate,
) -> tuple[tuple[OrganizationMemberRecord, ...], bool]:
    members = [
        OrganizationMemberRecord(
            member_id=claim.member_id,
            status=claim.status.value,
            basis=claim.basis,
            temporal_scope=claim.temporal_scope.value,
            first_tick=candidate.first_tick,
            last_tick=candidate.last_tick,
            strength=_STRENGTH.get(claim.status.value, 0.25),
            owner_support_count=max(1, len(claim.owner_ids)),
        )
        for claim in candidate.member_claims
    ]
    members.sort(
        key=lambda item: (
            _STATUS_RANK.get(item.status, 9),
            -item.strength,
            item.member_id,
        )
    )
    truncated = len(members) > MAX_SNAPSHOT_MEMBERS
    return tuple(members[:MAX_SNAPSHOT_MEMBERS]), truncated


def _structural_rows(
    candidate: OrganizationCandidate,
) -> tuple[OrganizationStructuralRecord, ...]:
    rows: list[OrganizationStructuralRecord] = []
    for kind, anchors in (
        ("role", candidate.role_anchor_ids),
        ("goal", candidate.goal_anchor_ids),
        ("resource", candidate.resource_anchor_ids),
        ("procedure", candidate.procedure_anchor_ids),
        ("record", candidate.record_anchor_ids),
        ("commitment", candidate.commitment_ids),
        ("identity", candidate.identity_tokens),
    ):
        for anchor in anchors:
            rows.append(
                OrganizationStructuralRecord(
                    kind=kind,
                    anchor_id=anchor,
                    status=candidate.status.value,
                    first_tick=candidate.first_tick,
                    last_tick=candidate.last_tick,
                )
            )
    return tuple(rows)


def _row_domain(family: str, row: object) -> str:
    if family in ("controls", "decisions"):
        domain = getattr(row, "domain", None)
        if isinstance(domain, str) and domain:
            return domain
        return "resource_control"
    return _FAMILY_DOMAINS[family]


def _row_contested(row: object) -> bool:
    return getattr(row, "stance", None) == "disputed" or (
        getattr(row, "contest_count", None) or 0
    ) > 0 or (getattr(row, "oppose_count", None) or 0) > 0


def _row_authority(row: object) -> str:
    authority = getattr(row, "authority_basis", None)
    if isinstance(authority, str) and authority in _KNOWN_AUTHORITY:
        return authority
    if authority == "observation" or authority == "record_reference":
        return "observation"
    return "unknown"


def _row_anchor(family: str, row: object) -> tuple[str, str | None, bool]:
    if family not in ("controls", "decisions", "actions"):
        return ("owner_local", None, True)
    kind = getattr(row, "anchor_kind", None)
    anchor_id = getattr(row, "anchor_id", None)
    if isinstance(kind, str) and kind in _OBJECTIVE_ANCHOR_KINDS:
        if isinstance(anchor_id, str) and anchor_id:
            return (kind, anchor_id, True)
    if kind == "unknown" or kind is None or not isinstance(anchor_id, str):
        return ("unknown", None, False)
    return ("owner_local", None, True)


def _stance_token(act: str, *, disputed: bool, unknown_authority: bool) -> str:
    if act in ("authorize_control", "revoke_control", "invoke_procedure"):
        return "disputed" if disputed else "claimed"
    if act == "admit":
        return "disputed" if disputed else "claimed"
    if act == "depart":
        return "disputed" if disputed else "departed"
    if act in ("assign", "remove"):
        return "removed" if act == "remove" else ("disputed" if disputed else "claimed")
    if act in ("declare_commitment", "fulfill_commitment"):
        return "disputed" if disputed else "declared"
    if unknown_authority:
        return "unknown"
    return "contested" if disputed else "supported"


def _act_for(family: str, row: object) -> str:
    if family == "controls":
        return "revoke_control" if getattr(row, "stance", None) == "former" else (
            "authorize_control"
        )
    if family == "admissions":
        return "admit"
    if family == "departures":
        return "depart"
    if family == "assignments":
        return "remove" if getattr(row, "stance", None) == "removed" else "assign"
    if family == "procedures":
        return "invoke_procedure"
    if family == "commitments":
        return (
            "fulfill_commitment"
            if getattr(row, "stance", None) == "fulfilled"
            else "declare_commitment"
        )
    act = getattr(row, "act", None)
    if isinstance(act, str) and act:
        return act
    return "record_decision"


def _outcome_for(family: str, row: object) -> str:
    if family == "commitments" and getattr(row, "stance", None) == "fulfilled":
        return "completed"
    outcome = getattr(row, "outcome", None)
    if family in ("procedures", "actions") and isinstance(outcome, str) and outcome:
        return outcome
    return "observed"


def _provenance_for(family: str, row: object, *, contested: bool) -> str:
    if family in ("decisions", "actions"):
        code = getattr(row, "provenance_code", None)
        if isinstance(code, str) and code:
            return code
        return "unknown_authority"
    if contested:
        return "contested"
    authority = _row_authority(row)
    if family == "procedures":
        if authority == "procedure_belief":
            return "procedure_recognized"
        if authority == "observation":
            return "observed_effect"
        return "unknown_authority"
    return {
        "self_authored": "self_authored",
        "role_belief": "role_authorized",
        "decision_belief": "decision_supported",
    }.get(authority, "unknown_authority")


def _target_for(act: str, anchor_id: str | None) -> str:
    if act in ("admit", "depart"):
        return "member"
    if act in ("assign", "remove"):
        return "office"
    return "anchor" if anchor_id is not None else "none"


def _ticks(family: str, row: object) -> tuple[int, int, int]:
    if family in ("decisions", "actions"):
        tick = getattr(row, "tick", None)
        value = tick if isinstance(tick, int) and tick >= 0 else 0
        return value, value, value
    first = getattr(row, "first_tick", None)
    last = getattr(row, "last_tick", None)
    first_tick = first if isinstance(first, int) and first >= 0 else 0
    last_tick = (
        last if isinstance(last, int) and last >= first_tick else first_tick
    )
    return last_tick, first_tick, last_tick


def _draft_operation(
    organization_id: str, family: str, row: object
) -> dict[str, object]:
    domain = _row_domain(family, row)
    act = _act_for(family, row)
    contested = _row_contested(row)
    authority = _row_authority(row)
    anchor_kind, anchor_id, resolved = _row_anchor(family, row)
    tick, first_tick, last_tick = _ticks(family, row)
    if family == "procedures":
        stance = "disputed" if contested else "claimed"
    elif family == "commitments":
        stance_value = getattr(row, "stance", None)
        stance = stance_value if isinstance(stance_value, str) and stance_value else (
            "disputed" if contested else "declared"
        )
    elif family in ("decisions", "actions"):
        if act == "record_decision":
            if contested:
                stance = "contested"
            elif authority == "unknown":
                stance = "unknown"
            else:
                stance = "supported"
        else:
            stance = _stance_token(
                act,
                disputed=contested,
                unknown_authority=authority == "unknown",
            )
    else:
        stored = getattr(row, "stance", None)
        stance = stored if isinstance(stored, str) and stored else (
            "disputed" if contested else _stance_token(
                act, disputed=contested, unknown_authority=False
            )
        )
    support = getattr(row, "owner_support_count", None)
    support_count = support if isinstance(support, int) and support >= 0 else 0
    contest = getattr(row, "contest_count", None)
    contest_count = contest if isinstance(contest, int) and contest >= 0 else 0
    if family in ("decisions", "actions"):
        oppose = getattr(row, "oppose_count", None)
        contest_count = max(
            contest_count, oppose if isinstance(oppose, int) and oppose >= 0 else 0
        )
        support = getattr(row, "support_count", None)
        if isinstance(support, int) and support >= 0:
            support_count = support
    command_kind = getattr(row, "command_kind", None)
    return {
        "domain": domain,
        "act": act,
        "stance": stance,
        "authority_basis": authority,
        "provenance_code": _provenance_for(family, row, contested=contested),
        "outcome": _outcome_for(family, row),
        "command_kind": (
            command_kind
            if isinstance(command_kind, str) and command_kind
            else "none"
        ),
        "target_kind": _target_for(act, anchor_id),
        "anchor_kind": anchor_kind,
        "anchor_id": anchor_id,
        "tick": tick,
        "first_tick": first_tick,
        "last_tick": last_tick,
        "support_count": support_count,
        "contest_count": contest_count,
        "resolved": resolved,
    }


def _draft_int(draft: dict[str, object], name: str) -> int:
    value = draft[name]
    if type(value) is not int:
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _draft_str(draft: dict[str, object], name: str) -> str:
    value = draft[name]
    if not isinstance(value, str):
        raise OrganizationArtifactError("organization_invalid_value")
    return value


def _content_digest(draft: dict[str, object]) -> str:
    encoded = json.dumps(draft, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _operation_records(
    organization_id: str,
    entries: tuple[tuple[str, object], ...],
) -> tuple[tuple[OrganizationOperationRecord, ...], bool]:
    drafts: dict[str, dict[str, object]] = {}
    for family, row in entries:
        draft = _draft_operation(organization_id, family, row)
        drafts.setdefault(_content_digest(draft), draft)
    ordered = sorted(
        drafts.items(),
        key=lambda item: (
            _draft_int(item[1], "tick"),
            _draft_str(item[1], "domain"),
            item[0],
        ),
    )
    truncated = len(ordered) > MAX_CANDIDATE_OPERATIONS
    records: list[OrganizationOperationRecord] = []
    for ordinal, (content_digest, draft) in enumerate(
        ordered[:MAX_CANDIDATE_OPERATIONS]
    ):
        domain = _draft_str(draft, "domain")
        operation_id = organization_publication_operation_id(
            organization_id,
            domain,
            _draft_int(draft, "tick"),
            ordinal,
            content_digest,
        )
        anchor_value = draft["anchor_id"]
        records.append(
            OrganizationOperationRecord(
                operation_id=operation_id,
                domain=domain,
                act=_draft_str(draft, "act"),
                stance=_draft_str(draft, "stance"),
                authority_basis=_draft_str(draft, "authority_basis"),
                provenance_code=_draft_str(draft, "provenance_code"),
                outcome=_draft_str(draft, "outcome"),
                command_kind=_draft_str(draft, "command_kind"),
                target_kind=_draft_str(draft, "target_kind"),
                anchor_kind=_draft_str(draft, "anchor_kind"),
                anchor_id=(
                    None if anchor_value is None else str(anchor_value)
                ),
                tick=_draft_int(draft, "tick"),
                first_tick=_draft_int(draft, "first_tick"),
                last_tick=_draft_int(draft, "last_tick"),
                support_count=_draft_int(draft, "support_count"),
                contest_count=_draft_int(draft, "contest_count"),
                resolved=bool(draft["resolved"]),
            )
        )
    return (
        tuple(
            sorted(
                records,
                key=lambda item: (item.tick, item.domain, item.operation_id),
            )
        ),
        truncated,
    )


def _candidate_record(
    candidate: OrganizationCandidate,
    record: OrganizationRecord,
    operations: tuple[OrganizationOperationRecord, ...] = (),
) -> tuple[OrganizationCandidateRecord, bool]:
    members, truncated = _member_records(candidate)
    return (
        OrganizationCandidateRecord(
            organization_id=record.organization_id,
            creation_tick=record.creation_tick,
            first_tick=record.first_tick,
            last_tick=record.last_tick,
            status=candidate.status.value,
            temporal_scope=candidate.temporal_scope.value,
            self_identified=candidate.self_identified,
            members=members,
            structure=_structural_rows(candidate),
            window_indexes=record.window_indexes,
            operations=operations,
        ),
        truncated,
    )


def _dissolved_record(
    record: OrganizationRecord,
    operations: tuple[OrganizationOperationRecord, ...] = (),
) -> OrganizationCandidateRecord:
    return OrganizationCandidateRecord(
        organization_id=record.organization_id,
        creation_tick=record.creation_tick,
        first_tick=record.first_tick,
        last_tick=record.last_tick,
        status="dissolved",
        temporal_scope="unknown",
        self_identified=False,
        members=tuple(
            OrganizationMemberRecord(
                member_id=member_id,
                status="former",
                basis="inference",
                temporal_scope="unknown",
                first_tick=record.first_tick,
                last_tick=record.last_tick,
                strength=0.1,
                owner_support_count=1,
            )
            for member_id in record.member_ids
        ),
        window_indexes=record.window_indexes,
        operations=operations,
    )


def _trim_snapshot_operations(
    records: list[OrganizationCandidateRecord],
) -> tuple[tuple[OrganizationCandidateRecord, ...], bool]:
    total = sum(len(record.operations) for record in records)
    if total <= MAX_SNAPSHOT_OPERATIONS:
        return tuple(records), False
    remaining = MAX_SNAPSHOT_OPERATIONS
    trimmed: list[OrganizationCandidateRecord] = []
    for record in sorted(records, key=lambda item: item.organization_id):
        keep = record.operations[:remaining]
        remaining -= len(keep)
        trimmed.append(
            record
            if len(keep) == len(record.operations)
            else OrganizationCandidateRecord(
                organization_id=record.organization_id,
                creation_tick=record.creation_tick,
                first_tick=record.first_tick,
                last_tick=record.last_tick,
                status=record.status,
                temporal_scope=record.temporal_scope,
                self_identified=record.self_identified,
                members=record.members,
                structure=record.structure,
                window_indexes=record.window_indexes,
                operations=keep,
            )
        )
    return tuple(trimmed), True


def build_organization_harvest_result(
    harvest: OrganizationHarvest,
) -> OrganizationHarvestResult:
    """Build one canonical snapshot from a completed-run harvest."""
    analysis = harvest.analysis
    assignment = harvest.assignment
    if analysis is None or assignment is None:
        snapshot = OrganizationSnapshot(
            schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
            policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
            run_id=harvest.run_id,
            input_revision=harvest.input_revision,
            generated_tick=harvest.generated_tick,
            publication_id="",
            coverage=OrganizationCoverage(observed=0, expected=0, ratio=None),
            provenance_code="ok",
        )
        return _finalize(snapshot, harvest)
    mapping = dict(assignment.candidate_ids)
    latest: dict[str, OrganizationCandidate] = {}
    for window in analysis.windows:
        for candidate in window.candidates:
            organization_id = mapping.get(candidate.candidate_key)
            if organization_id is not None:
                latest[organization_id] = candidate
    sources = dict(
        organization_operation_sources(harvest.operation_rows, assignment)
    )
    records: list[OrganizationCandidateRecord] = []
    truncated = False
    operations_truncated = False
    seen_ids: set[str] = set()
    for organization_id in sorted(latest):
        record = assignment.record_for(organization_id)
        if record is None:
            continue
        operations, cut = _operation_records(
            organization_id, sources.get(organization_id, ())
        )
        operations_truncated = operations_truncated or cut
        candidate_record, member_cut = _candidate_record(
            latest[organization_id], record, operations
        )
        records.append(candidate_record)
        truncated = truncated or member_cut
        seen_ids.add(organization_id)
    for record in analysis.records:
        if record.organization_id in seen_ids:
            continue
        operations, cut = _operation_records(
            record.organization_id, sources.get(record.organization_id, ())
        )
        operations_truncated = operations_truncated or cut
        records.append(_dissolved_record(record, operations))
        seen_ids.add(record.organization_id)
    trimmed_records, global_cut = _trim_snapshot_operations(records)

    windows = tuple(
        OrganizationWindowRecord(
            window_index=window.window_index,
            start_tick=window.start_tick,
            end_tick=window.end_tick,
            candidate_ids=tuple(
                sorted(
                    mapping[candidate.candidate_key]
                    for candidate in window.candidates
                    if candidate.candidate_key in mapping
                )
            ),
            member_count=sum(
                len(candidate.member_claims) for candidate in window.candidates
            ),
            overlap_member_count=len(window.overlap_person_ids),
            lane_presence=window.lane_presence,
            operation_count=sum(
                1
                for record in trimmed_records
                if record.organization_id
                in {
                    mapping[candidate.candidate_key]
                    for candidate in window.candidates
                    if candidate.candidate_key in mapping
                }
                for operation in record.operations
                if window.start_tick <= operation.tick <= window.end_tick
            ),
            contested_operation_count=sum(
                1
                for record in trimmed_records
                if record.organization_id
                in {
                    mapping[candidate.candidate_key]
                    for candidate in window.candidates
                    if candidate.candidate_key in mapping
                }
                for operation in record.operations
                if window.start_tick <= operation.tick <= window.end_tick
                and (
                    operation.stance == "disputed" or operation.contest_count > 0
                )
            ),
        )
        for window in analysis.windows
    )
    edges = tuple(
        OrganizationLineageEdgeRecord(
            kind=edge.kind.value,
            tick=edge.tick,
            from_id=edge.from_id,
            to_id=edge.to_id,
            jaccard=edge.jaccard,
            containment=edge.containment,
        )
        for edge in analysis.edges
    )
    objective_rows: tuple[OrganizationObjectiveRow, ...] = ()
    if analysis.layer_view is not None:
        objective_rows = tuple(
            OrganizationObjectiveRow(
                window_index=row.window_index,
                tick=row.tick,
                member_count=row.member_count,
                role_count=row.role_count,
                goal_count=row.goal_count,
                resource_count=row.resource_count,
                procedure_count=row.procedure_count,
                record_count=row.record_count,
                commitment_count=row.commitment_count,
                identity_count=row.identity_count,
                resolved_anchor_count=row.resolved_anchor_count,
                unresolved_anchor_count=row.unresolved_anchor_count,
                operation_action_count=row.operation_action_count,
            )
            for row in analysis.layer_view.objective
        )
    coverage = OrganizationCoverage(
        observed=analysis.coverage.observed,
        expected=analysis.coverage.expected,
        ratio=analysis.coverage.ratio,
    )
    provenance = "member_list_truncated" if truncated else harvest.provenance_code
    if operations_truncated or global_cut:
        provenance = "operations_truncated"
    snapshot = OrganizationSnapshot(
        schema_version=ORGANIZATION_SNAPSHOT_SCHEMA_VERSION,
        policy_version=ORGANIZATION_SNAPSHOT_POLICY_VERSION,
        run_id=harvest.run_id,
        input_revision=harvest.input_revision,
        generated_tick=harvest.generated_tick,
        publication_id="",
        coverage=coverage,
        windows=windows,
        candidates=trimmed_records,
        edges=edges,
        objective_rows=objective_rows,
        provenance_code=provenance,
    )
    return _finalize(upgrade_organization_snapshot(snapshot), harvest)


def _finalize(
    snapshot: OrganizationSnapshot, harvest: OrganizationHarvest
) -> OrganizationHarvestResult:
    from dataclasses import replace

    publication_id = compute_organization_publication_id(snapshot)
    published = replace(snapshot, publication_id=publication_id)
    payload = encode_organization_snapshot(published)
    if payload != encode_organization_snapshot(decode_organization_snapshot(payload)):
        raise OrganizationArtifactError("organization_digest_mismatch")
    operation_count = sum(
        len(candidate.operations) for candidate in published.candidates
    )
    contested_count = sum(
        candidate.contested_operation_count for candidate in published.candidates
    )
    if published.provenance_code != "ok":
        _LOG.warning(
            "organization_publication_partial run_id=%s reason=%s",
            harvest.run_id,
            published.provenance_code,
        )
    _LOG.info(
        "organization_publication_built run_id=%s publication_id=%s "
        "schema=%s candidates=%s edges=%s operations=%s bytes=%s",
        harvest.run_id,
        publication_id,
        published.schema_version,
        len(published.candidates),
        len(published.edges),
        operation_count,
        len(payload),
    )
    return OrganizationHarvestResult(
        snapshot=published,
        publication_id=publication_id,
        snapshot_bytes=payload,
        provenance_code=published.provenance_code,
        schema_version=published.schema_version,
        operation_count=operation_count,
        contested_operation_count=contested_count,
    )


def publish_organization_snapshot(
    result: OrganizationHarvestResult,
    port: OrganizationPublicationPort,
) -> None:
    """Inject exactly one publication through the publication port."""
    if type(result) is not OrganizationHarvestResult:
        raise OrganizationArtifactError("organization_invalid_value")
    port.publish(
        OrganizationPublication(
            run_id=result.snapshot.run_id,
            publication_id=result.publication_id,
            snapshot_digest=result.snapshot_digest,
            payload=result.snapshot_bytes,
            generated_tick=result.snapshot.generated_tick,
        )
    )


def organization_publication_document(
    result: OrganizationHarvestResult,
    *,
    status: str = "published",
) -> dict[str, object]:
    """Return safe receipt fields; never ids, labels, or anchors."""
    coverage = result.snapshot.coverage
    return {
        "status": status,
        "schema_version": result.snapshot.schema_version,
        "publication_id": result.publication_id,
        "window_count": len(result.snapshot.windows),
        "candidate_count": len(result.snapshot.candidates),
        "edge_count": len(result.snapshot.edges),
        "operation_count": result.operation_count,
        "contested_operation_count": result.contested_operation_count,
        "coverage_observed": coverage.observed,
        "coverage_expected": coverage.expected,
        "coverage_ratio": coverage.ratio,
        "provenance_code": result.provenance_code,
        "snapshot_bytes": len(result.snapshot_bytes),
    }
