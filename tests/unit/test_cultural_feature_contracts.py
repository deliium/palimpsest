"""Unit tests for cultural feature kind / channel / belief / audit contracts."""

from __future__ import annotations

import logging

import pytest

from agents.cognition.cultural_features import (
    CULTURAL_FEATURE_FIRST_HOP_INDEX,
    CULTURAL_FEATURE_POLICY_VERSION,
    CulturalFeatureAudit,
    CulturalFeatureKindId,
    CulturalFeatureLedger,
    CulturalTransmissionChannelId,
    SubjectiveCulturalBelief,
    empty_cultural_feature_ledger,
    parse_cultural_feature_kind,
    parse_cultural_transmission_channel,
    require_owner_cultural_features,
)
from agents.models import AgentId
from simulation.new_agent_initialization import (
    BLANK_SLATE_SUBJECTIVE_STORES,
    SUBJECTIVE_COPY_DENY_LIST,
    BlankSlateStoreCounts,
    assert_blank_slate_subjective_state,
)

_LOG = logging.getLogger("tests.cultural_feature_contracts")


def test_closed_feature_kind_and_channel_ids() -> None:
    _LOG.debug("case_id=closed_feature_kind_and_channel_ids")
    assert {k.value for k in CulturalFeatureKindId} == {
        "practice",
        "narrative_element",
        "term",
        "production_technique",
        "social_expectation",
        "symbolic_association",
    }
    assert {c.value for c in CulturalTransmissionChannelId} == {
        "observation",
        "teaching",
        "communication",
        "artifact",
        "imitation",
        "independent_rediscovery",
    }
    assert CULTURAL_FEATURE_FIRST_HOP_INDEX == 0


def test_forbidden_feature_kind_aliases_rejected() -> None:
    _LOG.debug("case_id=forbidden_feature_kind_aliases")
    for alias in (
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "global_culture",
        "tradition_law",
        "myth_object",
        "language_authority",
        "society_culture",
        "encyclopedia_download",
    ):
        with pytest.raises(
            ValueError,
            match=r"forbidden_feature_kind_alias|unknown_feature_kind",
        ):
            parse_cultural_feature_kind(alias)


def test_forbidden_channel_aliases_rejected() -> None:
    _LOG.debug("case_id=forbidden_channel_aliases")
    for alias in (
        "culture_pack",
        "encyclopedia",
        "society_memory",
        "global_culture",
        "tradition_law",
        "myth_object",
        "language_authority",
    ):
        with pytest.raises(
            ValueError, match=r"forbidden_channel_alias|unknown_channel"
        ):
            parse_cultural_transmission_channel(alias)


def test_empty_ledger_construct_logs_zero_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _LOG.debug("case_id=empty_ledger_construct")
    owner = AgentId("learner-c1")
    with caplog.at_level(logging.DEBUG, logger="agents.cognition.cultural_features"):
        ledger = empty_cultural_feature_ledger(owner)
    assert ledger.beliefs == ()
    assert ledger.policy_version == CULTURAL_FEATURE_POLICY_VERSION
    assert "belief_count=0" in caplog.text
    assert_blank_slate_subjective_state(
        owner,
        BlankSlateStoreCounts(cultural_features=len(ledger.beliefs)),
    )


def test_blank_slate_includes_cultural_features() -> None:
    _LOG.debug("case_id=blank_slate_includes_cultural_features")
    assert "cultural_features" in BLANK_SLATE_SUBJECTIVE_STORES
    for alias in (
        "culture_pack",
        "global_culture",
        "society_culture",
        "encyclopedia_download",
        "cultural_features",
    ):
        assert alias in SUBJECTIVE_COPY_DENY_LIST


def test_provenance_less_belief_rejected(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=provenance_less_belief_rejected")
    with caplog.at_level(logging.ERROR, logger="agents.cognition.cultural_features"):
        with pytest.raises(ValueError, match="provenance_required"):
            SubjectiveCulturalBelief(
                belief_id="belief:1",
                owner_agent_id=AgentId("bob"),
                feature_kind=CulturalFeatureKindId.PRACTICE,
                content_key="practice:forge",
                content_fingerprint="fp:bob:practice:forge",
                channel=CulturalTransmissionChannelId.OBSERVATION,
                confidence=0.4,
                parent_belief_ids=(),
                hop_index=CULTURAL_FEATURE_FIRST_HOP_INDEX,
                mutated=False,
                recombined=False,
                evidence_refs=(),
                acquired_tick=2,
                last_updated_tick=2,
            )
    assert "provenance_required" in caplog.text


def test_independent_rediscovery_root_ok() -> None:
    _LOG.debug("case_id=independent_rediscovery_root")
    owner = AgentId("carol")
    belief = SubjectiveCulturalBelief(
        belief_id="belief:rediscover:1",
        owner_agent_id=owner,
        feature_kind=CulturalFeatureKindId.TERM,
        content_key="term:river",
        content_fingerprint="fp:carol:term:river",
        channel=CulturalTransmissionChannelId.INDEPENDENT_REDISCOVERY,
        confidence=0.5,
        parent_belief_ids=(),
        hop_index=CULTURAL_FEATURE_FIRST_HOP_INDEX,
        mutated=False,
        recombined=False,
        evidence_refs=(),
        acquired_tick=1,
        last_updated_tick=1,
    )
    ledger = CulturalFeatureLedger(owner_id=owner, beliefs=(belief,))
    require_owner_cultural_features(ledger, owner, field_name="cultural_features")
    assert belief.hop_index == 0


def test_belief_and_audit_construct_ok() -> None:
    _LOG.debug("case_id=belief_and_audit_construct")
    owner = AgentId("bob")
    belief = SubjectiveCulturalBelief(
        belief_id="belief:obs:1",
        owner_agent_id=owner,
        feature_kind=CulturalFeatureKindId.SOCIAL_EXPECTATION,
        content_key="expect:queue",
        content_fingerprint="fp:bob:expect:queue",
        channel=CulturalTransmissionChannelId.COMMUNICATION,
        confidence=0.7,
        parent_belief_ids=("belief:alice:1",),
        hop_index=1,
        mutated=False,
        recombined=False,
        evidence_refs=("evt:42",),
        acquired_tick=3,
        last_updated_tick=5,
    )
    audit = CulturalFeatureAudit(
        owner_id=owner,
        feature_kind=belief.feature_kind,
        channel=belief.channel,
        hop_index=belief.hop_index,
        mutated=belief.mutated,
        recombined=belief.recombined,
        parent_count=len(belief.parent_belief_ids),
        confidence_band="high",
        digest_id_token="fp:bob:expect:queue",
        tick=5,
        reason_code="uptake_ok",
    )
    ledger = CulturalFeatureLedger(owner_id=owner, beliefs=(belief,))
    assert len(ledger.beliefs) == 1
    assert audit.parent_count == 1


def test_hop_cap_rejected(caplog: pytest.LogCaptureFixture) -> None:
    _LOG.debug("case_id=hop_cap_rejected")
    with caplog.at_level(logging.ERROR, logger="agents.cognition.cultural_features"):
        with pytest.raises(ValueError, match="cultural_feature_hop_cap"):
            SubjectiveCulturalBelief(
                belief_id="belief:deep",
                owner_agent_id=AgentId("dave"),
                feature_kind=CulturalFeatureKindId.PRACTICE,
                content_key="practice:x",
                content_fingerprint="fp:dave:practice:x",
                channel=CulturalTransmissionChannelId.IMITATION,
                confidence=0.3,
                parent_belief_ids=("p1",),
                hop_index=9,
                mutated=True,
                recombined=False,
                evidence_refs=("evt:9",),
                acquired_tick=1,
                last_updated_tick=1,
            )
    assert "cultural_feature_hop_cap" in caplog.text


def test_no_culture_type_in_module() -> None:
    _LOG.debug("case_id=no_culture_type")
    import agents.cognition.cultural_features as mod

    assert not hasattr(mod, "Culture")
    assert not hasattr(mod, "SocietyCulture")
