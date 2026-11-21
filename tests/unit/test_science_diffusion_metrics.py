# mypy: ignore-errors
"""V4-33 diffusion metric families: counts, denominators, availability."""

from __future__ import annotations

import pytest

from analysis.models import MetricAvailability
from analysis.science_diffusion_contract import (
    DiffusionLane,
    LaneCoverageState,
)
from analysis.science_diffusion_lineage import (
    CarrierClosureWitness,
    RediscoveryRoot,
    V3Link,
    derive_science_diffusion,
)
from analysis.science_diffusion_metrics import (
    compute_science_diffusion_channels,
    compute_science_diffusion_fidelity,
    compute_science_diffusion_genealogy,
    compute_science_diffusion_persistence,
)
from analysis.specifications import MetricFamilyId, all_metric_specifications
from tests.unit.test_science_diffusion_lineage import (
    _coverage,
    _inputs,
    _occurrence,
    _version,
)

pytestmark = pytest.mark.unit

RUN = "run-sdf-metrics"
FAMILIES = (
    MetricFamilyId.SCIENCE_DIFFUSION_CHANNELS,
    MetricFamilyId.SCIENCE_DIFFUSION_FIDELITY,
    MetricFamilyId.SCIENCE_DIFFUSION_PERSISTENCE,
    MetricFamilyId.SCIENCE_DIFFUSION_GENEALOGY,
)


def test_four_families_append_to_275_once() -> None:
    specs = all_metric_specifications()
    assert len(specs) == 275
    ids = [spec.family_id for spec in specs]
    for family in FAMILIES:
        assert ids.count(family) == 1


def test_channels_counts_and_present_availability() -> None:
    source = _version(tick=0)
    occurrence = _occurrence(tick=2, source=source.key)
    assessment = derive_science_diffusion(
        _inputs(versions=(source,), occurrences=(occurrence,))
    )
    document = compute_science_diffusion_channels(
        assessment, run_id=RUN, input_revision="rev"
    )
    assert document.availability is MetricAvailability.PRESENT
    assert document.values["delivered_count"] == 1
    assert document.values["speech_count"] == 1
    assert document.values["adopted_count"] == 0


def test_incomplete_coverage_is_partial() -> None:
    assessment = derive_science_diffusion(
        _inputs(
            coverage=_coverage(
                state=LaneCoverageState.PARTIAL,
                lanes=(DiffusionLane.SCIENCE, DiffusionLane.SPEECH),
            )
        )
    )
    document = compute_science_diffusion_channels(
        assessment, run_id=RUN, input_revision="rev"
    )
    assert document.availability is MetricAvailability.PARTIAL
    assert document.coverage.expected == len(assessment.windows)


def test_fidelity_keeps_mutation_and_translation_separate() -> None:
    first = _version(revision=0)
    second = _version(revision=1, tick=4, predicted="failure")
    from analysis.science_diffusion_contract import DiffusionContextFlag

    translated = _occurrence(
        tick=5,
        source=second.key,
        context_flags=(DiffusionContextFlag.TRANSLATION_APPLIED,),
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(first, second), occurrences=(translated,))
    )
    document = compute_science_diffusion_fidelity(
        assessment, run_id=RUN, input_revision="rev"
    )
    assert document.values["mutation_count"] == 1
    assert document.values["bound_translation_count"] == 1
    assert document.values["comparable_pair_count"] == 1


def test_persistence_and_genealogy_counts() -> None:
    lost = _version(tick=0, status="retired")
    regained = _version(owner="agent-b", tick=100, observed=100)
    root = RediscoveryRoot(
        version_key=regained.key,
        root_kind="experiment",
        root_ref="evt-77",
        affirmative=True,
        committed=True,
    )
    closure = CarrierClosureWitness(
        witness_boundary=0,
        holders_closed=True,
        carriers_closed=True,
        version_key=lost.key,
    )
    assessment = derive_science_diffusion(
        _inputs(versions=(lost, regained)),
        v3_links=(
            V3Link(
                transmission_key="evt-1",
                v3_node_key="knowledge:agent-b:entry-1",
                origin="teaching",
                relation="teaching_uptake",
            ),
        ),
        closure_witnesses=(closure,),
        rediscovery_roots=(root,),
    )
    persistence = compute_science_diffusion_persistence(
        assessment, run_id=RUN, input_revision="rev"
    )
    assert persistence.values["scoped_loss_count"] >= 1
    assert persistence.values["confirmed_observed_loss_count"] == 1
    assert persistence.values["independent_rediscovery_count"] == 1
    genealogy = compute_science_diffusion_genealogy(
        assessment, run_id=RUN, input_revision="rev"
    )
    assert genealogy.values["exact_link_count"] == 1
    assert genealogy.values["teaching_link_count"] == 1
    assert genealogy.values["ambiguous_link_count"] == 0


def test_wrong_assessment_type_is_rejected() -> None:
    with pytest.raises(ValueError):
        compute_science_diffusion_channels(
            object(), run_id=RUN, input_revision="rev"
        )
