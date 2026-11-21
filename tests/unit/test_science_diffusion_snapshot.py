# mypy: ignore-errors
"""V4-33 canonical diffusion snapshot codec and composition limits."""

from __future__ import annotations

import json

import pytest

from analysis.science_diffusion_contract import (
    DiffusionInputs,
    DiffusionLane,
    DiffusionOccurrence,
    DiffusionStage,
    EvidenceKind,
    EvidenceRef,
    HypothesisDescriptor,
    LaneCoverage,
    LaneCoverageState,
    ScienceKind,
    ScienceVersion,
    ScienceVersionKey,
)
from analysis.science_diffusion_lineage import V3Link, derive_science_diffusion
from experiments.science_diffusion_publication import (
    compose_science_diffusion_snapshot,
)
from simulation.science_diffusion_codec import (
    ScienceDiffusionSnapshotError,
    canonical_science_diffusion_json,
    decode_science_diffusion_snapshot,
    encode_science_diffusion_snapshot,
    load_science_diffusion_payload,
    science_diffusion_digest,
    science_diffusion_publication_id,
)
from simulation.science_diffusion_models import (
    ScienceDiffusionSnapshot,
    ScienceDiffusionSnapshotOverflow,
    TransmissionRow,
)

pytestmark = pytest.mark.unit

RUN = "run-sdf-snapshot"


def _version(revision: int = 0, tick: int = 0, predicted: str = "success"):
    key = ScienceVersionKey(
        run_id=RUN,
        owner_id="agent-a",
        kind=ScienceKind.HYPOTHESIS,
        local_id="h1",
        revision_index=revision,
    )
    return ScienceVersion(
        key=key,
        occurrence_tick=tick,
        first_observed_boundary=tick,
        wire=tuple(
            sorted(
                (
                    ("confidence", "100"),
                    ("status", "provisional"),
                    ("reason", "formulated"),
                )
            )
        ),
        hypothesis=HypothesisDescriptor(
            operator="combine",
            operand_refs=("item:wood",),
            process="harvest",
            predicted_outcome=predicted,
            conditions=(),
        ),
        evidence=EvidenceRef(
            kind=EvidenceKind.OWNER_ROW,
            run_id=RUN,
            tick=tick,
            owner_id="agent-a",
            local_id="h1",
            revision_index=revision,
        ),
    )


def _inputs(versions, occurrences):
    return DiffusionInputs(
        run_id=RUN,
        versions=tuple(versions),
        occurrences=tuple(occurrences),
        coverage=tuple(
            LaneCoverage(
                lane=lane,
                start_tick=0,
                end_tick_exclusive=64,
                state=LaneCoverageState.COMPLETE,
            )
            for lane in DiffusionLane
        ),
    )


def _snapshot():
    first = _version()
    second = _version(revision=1, tick=3, predicted="failure")
    occurrence = DiffusionOccurrence(
        run_id=RUN,
        lane=DiffusionLane.SPEECH,
        occurrence_kind="test",
        tick=5,
        first_observed_boundary=5,
        evidence=EvidenceRef(
            kind=EvidenceKind.EVENT,
            run_id=RUN,
            tick=5,
            event_id="evt-1",
            sequence=0,
        ),
        stage=DiffusionStage.DELIVERED,
        actor_id="agent-a",
        counterparty_id="agent-b",
        source_version=second.key,
    )
    assessment = derive_science_diffusion(
        _inputs((first, second), (occurrence,)),
        v3_links=(
            V3Link(
                transmission_key=assessment_key(occurrence),
                v3_node_key="knowledge:agent-b:entry-1",
                origin="teaching",
                relation="teaching_uptake",
            ),
        ),
    )
    return compose_science_diffusion_snapshot(
        run_id=RUN,
        config_fingerprint="cfg",
        capture_status="captured",
        boundary_tick=64,
        coverage=_inputs((first, second), (occurrence,)).coverage,
        versions=(first, second),
        assessment=assessment,
    )


def assessment_key(occurrence):
    return "\x1f".join(
        (
            repr(occurrence.evidence.qualified_key()),
            occurrence.lane.value,
            occurrence.stage.value,
            occurrence.occurrence_kind,
        )
    )


def test_snapshot_is_canonical_sorted_and_self_identifying() -> None:
    snapshot = _snapshot()
    assert snapshot.version == "science-diffusion-snapshot-v1"
    assert snapshot.publication_id.startswith("sdf-")
    assert snapshot.publication_id == science_diffusion_publication_id(snapshot)
    material = canonical_science_diffusion_json(snapshot)
    assert not material.endswith(b"\n")
    payload = json.loads(material)
    assert payload["coverage"] == sorted(
        payload["coverage"], key=lambda row: (row["lane"], row["start_tick"])
    )
    assert science_diffusion_digest(snapshot) == science_diffusion_digest(
        decode_science_diffusion_snapshot(payload)
    )
    repeat = _snapshot()
    assert canonical_science_diffusion_json(repeat) == material
    assert repeat.publication_id == snapshot.publication_id


def test_duplicate_json_keys_and_unknown_row_keys_are_rejected() -> None:
    with pytest.raises(ScienceDiffusionSnapshotError):
        load_science_diffusion_payload(b'{"a":1,"a":2}')
    snapshot = _snapshot()
    payload = encode_science_diffusion_snapshot(snapshot)
    payload["versions"][0]["unknown"] = "x"
    with pytest.raises(ScienceDiffusionSnapshotError):
        decode_science_diffusion_snapshot(payload)
    payload["versions"][0].pop("unknown")
    payload["transmissions"][0]["tick"] = "5"
    with pytest.raises(ScienceDiffusionSnapshotError):
        decode_science_diffusion_snapshot(payload)


def test_dangling_foreign_keys_are_rejected() -> None:
    snapshot = _snapshot()
    with pytest.raises(ValueError):
        ScienceDiffusionSnapshot(
            run_id=snapshot.run_id,
            publication_id=snapshot.publication_id,
            policy_version=snapshot.policy_version,
            input_revision=snapshot.input_revision,
            boundary_tick=snapshot.boundary_tick,
            coverage=snapshot.coverage,
            versions=snapshot.versions,
            transmissions=(
                TransmissionRow(
                    row_key="row-1",
                    occurrence_key="occ-1",
                    tick=1,
                    confirmation_boundary=1,
                    stage="delivered",
                    from_version_key="missing",
                    to_version_key="",
                    source_owner_key="",
                    recipient_owner_key="",
                    carrier_kind="",
                    carrier_key="",
                    content_revision=0,
                    context_flags=(),
                    exclusions=(),
                ),
            ),
        )


def test_composer_rejects_inactive_capture_and_foreign_run() -> None:
    with pytest.raises(ScienceDiffusionSnapshotOverflow):
        compose_science_diffusion_snapshot(
            run_id=RUN,
            config_fingerprint="cfg",
            capture_status="capture_failed",
            boundary_tick=64,
            coverage=(),
            versions=(),
            assessment=derive_science_diffusion(
                _inputs((), ())
            ),
        )
    with pytest.raises(ValueError):
        compose_science_diffusion_snapshot(
            run_id="other-run",
            config_fingerprint="cfg",
            capture_status="captured",
            boundary_tick=64,
            coverage=(),
            versions=(),
            assessment=derive_science_diffusion(_inputs((), ())),
        )


def test_coverage_cap_is_enforced() -> None:
    from analysis.science_diffusion_contract import LaneCoverage
    from simulation.science_diffusion_models import MAX_COVERAGE_ROWS

    assessment = derive_science_diffusion(_inputs((), ()))
    coverage = tuple(
        LaneCoverage(
            lane=DiffusionLane.SCIENCE,
            start_tick=index * 2,
            end_tick_exclusive=index * 2 + 1,
            state=LaneCoverageState.COMPLETE,
        )
        for index in range(MAX_COVERAGE_ROWS + 1)
    )
    with pytest.raises(ScienceDiffusionSnapshotOverflow):
        compose_science_diffusion_snapshot(
            run_id=RUN,
            config_fingerprint="cfg",
            capture_status="captured",
            boundary_tick=1,
            coverage=coverage,
            versions=(),
            assessment=assessment,
        )
