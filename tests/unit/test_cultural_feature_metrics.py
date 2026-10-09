"""Cultural feature provenance / diffusion / mutation metric families."""

from __future__ import annotations

from agents.cognition.cultural_features import (
    CulturalFeatureAudit,
    CulturalFeatureKindId,
    CulturalTransmissionChannelId,
)
from agents.models import AgentId
from analysis.cultural_feature_metrics import (
    CULTURAL_FEATURE_MUTATION_METRIC_VERSION,
    CULTURAL_FEATURE_PROVENANCE_METRIC_VERSION,
    CULTURAL_TRAIT_DIFFUSION_METRIC_VERSION,
    compute_cultural_feature_mutation,
    compute_cultural_feature_provenance,
    compute_cultural_trait_diffusion,
)
from analysis.cultural_traits import compute_analytical_cultural_traits
from analysis.models import MetricAvailability
from analysis.specifications import METRIC_FAMILY_COUNT, all_metric_specifications


def _audit(*, mutated: bool = False, recombined: bool = False) -> CulturalFeatureAudit:
    return CulturalFeatureAudit(
        owner_id=AgentId("bob"),
        feature_kind=CulturalFeatureKindId.PRACTICE,
        channel=CulturalTransmissionChannelId.OBSERVATION,
        hop_index=1,
        mutated=mutated,
        recombined=recombined,
        parent_count=2 if recombined else 0,
        confidence_band="mid",
        digest_id_token="dig-practice",
        tick=2,
        reason_code="channel_formed",
    )


def test_metric_family_count_includes_cultural_features() -> None:
    specs = all_metric_specifications()
    assert len(specs) == METRIC_FAMILY_COUNT == 71
    ids = {spec.family_id.value for spec in specs}
    assert {
        "cultural_feature_provenance",
        "cultural_trait_diffusion",
        "cultural_feature_mutation",
    } <= ids


def test_provenance_diffusion_and_mutation_documents() -> None:
    audits = (
        _audit(),
        _audit(mutated=True),
        _audit(recombined=True),
    )
    provenance = compute_cultural_feature_provenance(
        audits, run_id="run-al", input_revision="rev-1"
    )
    assert provenance.availability is MetricAvailability.PRESENT
    assert CULTURAL_FEATURE_PROVENANCE_METRIC_VERSION.endswith("@1")
    assert provenance.values["audit_count"] == 3

    diffusion = compute_cultural_trait_diffusion(
        audits, run_id="run-al", input_revision="rev-1"
    )
    assert diffusion.availability is MetricAvailability.PRESENT
    assert CULTURAL_TRAIT_DIFFUSION_METRIC_VERSION.endswith("@1")

    mutation = compute_cultural_feature_mutation(
        audits, run_id="run-al", input_revision="rev-1"
    )
    assert mutation.availability is MetricAvailability.PRESENT
    assert mutation.values["mutated_count"] == 1
    assert CULTURAL_FEATURE_MUTATION_METRIC_VERSION.endswith("@1")

    traits = compute_analytical_cultural_traits(audits)
    assert traits
    assert traits[0].feature_kind == "practice"
