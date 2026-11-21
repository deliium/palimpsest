"""Trusted composition of detached diffusion assessments into snapshots."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Final

from analysis.science_diffusion_contract import (
    DiffusionLane,
    LaneCoverage,
    ScienceVersion,
)
from analysis.science_diffusion_lineage import DiffusionAssessment
from simulation.science_diffusion_codec import science_diffusion_publication_id
from simulation.science_diffusion_models import (
    MAX_COVERAGE_ROWS,
    MAX_SECTION_ROWS,
    MAX_TOTAL_ROWS,
    ChangeRow,
    CoverageRow,
    GenealogyRow,
    ScienceDiffusionSnapshot,
    ScienceDiffusionSnapshotOverflow,
    TransmissionRow,
    VersionRow,
)

__all__ = [
    "compose_science_diffusion_snapshot",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "experiments.science_diffusion_publication"
)

_ALLOWED_STATUS: Final[frozenset[str]] = frozenset({"captured", "captured_sealed"})


def _opaque(domain: str, *parts: str) -> str:
    material = "\x1f".join(("science-diffusion.snapshot.v1", domain, *parts))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return f"sdfo:{digest[:32]}"


def _input_revision(
    coverage: Sequence[LaneCoverage],
    versions: Sequence[ScienceVersion],
    assessment: DiffusionAssessment,
) -> str:
    document = {
        "coverage": [
            [
                row.lane.value,
                row.start_tick,
                row.end_tick_exclusive,
                row.state.value,
                "" if row.reason is None else row.reason.value,
                row.observed,
            ]
            for row in coverage
        ],
        "versions": [
            [
                row.key.token(),
                row.key.kind.value,
                row.key.revision_index,
                row.first_observed_boundary,
            ]
            for row in versions
        ],
        "transmissions": [
            [
                row.transmission_key,
                row.stage,
                row.tick,
                row.resolution,
                "" if row.reason is None else row.reason,
            ]
            for row in assessment.transmissions
        ],
    }
    material = json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return f"sdfo:{hashlib.sha256(material).hexdigest()}"


def compose_science_diffusion_snapshot(
    *,
    run_id: str,
    config_fingerprint: str,
    capture_status: str,
    boundary_tick: int,
    coverage: Sequence[LaneCoverage],
    versions: Sequence[ScienceVersion],
    assessment: DiffusionAssessment,
) -> ScienceDiffusionSnapshot:
    """Compose one canonical snapshot from a successful bounded capture."""

    if capture_status not in _ALLOWED_STATUS:
        raise ScienceDiffusionSnapshotOverflow("quota_exceeded")
    if assessment.run_id != run_id:
        raise ValueError("science_diffusion_run_mismatch")
    if not config_fingerprint:
        raise ValueError("science_diffusion_config_missing")
    if type(boundary_tick) is not int or boundary_tick < 0:
        raise ValueError("science_diffusion_boundary_invalid")

    version_keys: dict[object, str] = {}
    versions_rows: list[VersionRow] = []
    for version in sorted(versions, key=lambda row: row.key.as_tuple()):
        token = version.key.token()
        version_keys[version.key] = token
        versions_rows.append(
            VersionRow(
                row_key=token,
                kind=version.key.kind.value,
                revision_index=version.key.revision_index,
                first_observed_boundary=version.first_observed_boundary,
            )
        )

    coverage_rows = [
        CoverageRow(
            lane=row.lane.value,
            start_tick=row.start_tick,
            end_tick_exclusive=row.end_tick_exclusive,
            state=row.state.value,
            reason="" if row.reason is None else row.reason.value,
            observed=row.observed,
        )
        for row in sorted(coverage, key=lambda item: (item.lane.value, item.start_tick))
    ]
    if len(coverage_rows) > MAX_COVERAGE_ROWS:
        raise ScienceDiffusionSnapshotOverflow("quota_exceeded")

    transmission_rows: list[TransmissionRow] = []
    occurrence_map: dict[str, str] = {}
    for row in assessment.transmissions:
        occurrence_key = _opaque("occurrence", run_id, row.transmission_key)
        occurrence_map[row.transmission_key] = occurrence_key
        source_key = (
            ""
            if row.source_version is None
            else version_keys.get(row.source_version, "")
        )
        target_key = (
            ""
            if row.target_version is None
            else version_keys.get(row.target_version, "")
        )
        transmission_rows.append(
            TransmissionRow(
                row_key=occurrence_key,
                occurrence_key=occurrence_key,
                tick=row.tick,
                confirmation_boundary=row.confirmation_boundary,
                stage=row.stage,
                from_version_key=source_key,
                to_version_key=target_key,
                source_owner_key=(
                    ""
                    if row.actor_id is None
                    else _opaque("owner", run_id, row.actor_id)
                ),
                recipient_owner_key=(
                    ""
                    if row.counterparty_id is None
                    else _opaque("owner", run_id, row.counterparty_id)
                ),
                carrier_kind="",
                carrier_key=(
                    ""
                    if row.carrier_id is None
                    else _opaque("carrier", run_id, row.carrier_id)
                ),
                content_revision=(
                    0 if row.content_revision is None else row.content_revision
                ),
                context_flags=tuple(sorted(row.context_flags)),
                exclusions=(() if row.reason is None else (row.reason,)),
            )
        )

    change_rows = [
        ChangeRow(
            row_key=_opaque("change", run_id, row.change_key),
            kind=row.kind.value,
            from_version_key=(
                ""
                if row.from_version is None
                else version_keys.get(row.from_version, "")
            ),
            to_version_key=(
                "" if row.to_version is None else version_keys.get(row.to_version, "")
            ),
            carrier_key=(
                ""
                if row.carrier_id is None
                else _opaque("carrier", run_id, row.carrier_id)
            ),
            confirmation_boundary=row.confirmation_boundary,
            changed_fields=tuple(sorted(row.changed_fields)),
        )
        for row in assessment.changes
    ]
    genealogy_rows = [
        GenealogyRow(
            row_key=_opaque("genealogy", run_id, row.transmission_key),
            transmission_key=occurrence_map.get(
                row.transmission_key,
                _opaque("occurrence", run_id, row.transmission_key),
            ),
            v3_node_key=_opaque("v3", run_id, row.v3_node_key),
            origin=row.origin,
            relation=row.relation,
            ambiguity="ambiguous" if row.ambiguous else "exact",
        )
        for row in assessment.v3_links
    ]
    if len(transmission_rows) > MAX_SECTION_ROWS or len(change_rows) > MAX_SECTION_ROWS:
        raise ScienceDiffusionSnapshotOverflow("quota_exceeded")
    total = (
        len(coverage_rows)
        + len(versions_rows)
        + len(transmission_rows)
        + len(change_rows)
        + len(genealogy_rows)
    )
    if total > MAX_TOTAL_ROWS:
        raise ScienceDiffusionSnapshotOverflow("quota_exceeded")
    input_revision = _input_revision(coverage, versions, assessment)
    draft = ScienceDiffusionSnapshot(
        run_id=run_id,
        publication_id="sdf-pending",
        policy_version="science-diffusion.v1",
        input_revision=input_revision,
        boundary_tick=boundary_tick,
        coverage=tuple(coverage_rows),
        versions=tuple(versions_rows),
        transmissions=tuple(transmission_rows),
        changes=tuple(change_rows),
        genealogy=tuple(genealogy_rows),
    )
    publication_id = science_diffusion_publication_id(draft)
    snapshot = ScienceDiffusionSnapshot(
        run_id=run_id,
        publication_id=publication_id,
        policy_version=draft.policy_version,
        input_revision=input_revision,
        boundary_tick=boundary_tick,
        coverage=draft.coverage,
        versions=draft.versions,
        transmissions=draft.transmissions,
        changes=draft.changes,
        genealogy=draft.genealogy,
    )
    if len(snapshot.coverage) and any(
        row.lane not in {lane.value for lane in DiffusionLane}
        for row in snapshot.coverage
    ):
        raise ValueError("science_diffusion_lane_invalid")
    _LOG.debug(
        "science_diffusion_snapshot_composed run_id=%s publication_id=%s rows=%s",
        run_id,
        publication_id,
        snapshot.row_count,
    )
    return snapshot
