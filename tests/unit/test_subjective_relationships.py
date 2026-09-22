"""Unit tests for asymmetric subjective relationship profiles."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from agents.models import AgentId
from social.relationships import (
    RelationshipDimension,
    RelationshipFormationPolicy,
    RelationshipInteractionSignal,
    RelationshipProfileStore,
    RelationshipRevisionRequest,
    RelationshipSignalKind,
    merge_relationship_revision,
    profile_id_for,
    project_legacy_relationship,
)
from social.service import (
    InMemoryRelationshipService,
    RelationshipServiceError,
    RelationshipServiceErrorCode,
)


def _signal(
    *,
    counterpart: str = "bob",
    kind: RelationshipSignalKind = RelationshipSignalKind.HELP_RECEIVED,
    memory_ref: str = "m-1",
    strength: float = 0.8,
    tick: int = 1,
) -> RelationshipInteractionSignal:
    return RelationshipInteractionSignal(
        counterpart_id=AgentId(counterpart),
        kind=kind,
        strength=strength,
        memory_ref=memory_ref,
        lineage_root_ref=memory_ref,
        source_tick=tick,
    )


def _policy() -> RelationshipFormationPolicy:
    return RelationshipFormationPolicy(policy_id="rel-test", version="1")


def test_alice_to_bob_without_reverse() -> None:
    history, created, changed, _ = merge_relationship_revision(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        signals=(_signal(counterpart="bob"),),
        prior=None,
        logical_tick=1,
        operation_id="op-1",
        policy=_policy(),
    )
    assert created
    assert changed >= 1
    assert history.profile.source_id.value == "alice"
    assert history.profile.target_id.value == "bob"
    assert profile_id_for(
        source_id=AgentId("alice"), target_id=AgentId("bob")
    ) != profile_id_for(source_id=AgentId("bob"), target_id=AgentId("alice"))


def test_updating_one_direction_does_not_create_reverse() -> None:
    store = RelationshipProfileStore(AgentId("alice"))
    history, _, _, _ = merge_relationship_revision(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        signals=(_signal(),),
        prior=None,
        logical_tick=1,
        operation_id="op-1",
        policy=_policy(),
    )
    store.write(history)
    assert len(store.snapshot()) == 1
    bob_store = RelationshipProfileStore(AgentId("bob"))
    assert bob_store.snapshot() == ()


def test_self_target_fails_closed() -> None:
    with pytest.raises(ValueError, match="self_target"):
        merge_relationship_revision(
            source_id=AgentId("alice"),
            target_id=AgentId("alice"),
            signals=(),
            prior=None,
            logical_tick=0,
            operation_id="op",
            policy=_policy(),
        )


def test_no_high_level_social_category_fields() -> None:
    history, _, _, _ = merge_relationship_revision(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        signals=(_signal(kind=RelationshipSignalKind.HARM_RECEIVED),),
        prior=None,
        logical_tick=1,
        operation_id="op-1",
        policy=_policy(),
    )
    fields = set(history.profile.__dataclass_fields__)
    for banned in ("friend", "enemy", "leader", "group", "morality", "culture"):
        assert banned not in fields
    dims = {item.dimension for item in history.profile.dimensions}
    assert (
        RelationshipDimension.FEAR in dims or RelationshipDimension.RESENTMENT in dims
    )
    legacy = project_legacy_relationship(history.profile)
    assert legacy.kind == "directed_profile"


def test_repr_omits_dimension_values() -> None:
    history, _, _, _ = merge_relationship_revision(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        signals=(_signal(strength=0.9),),
        prior=None,
        logical_tick=1,
        operation_id="op-1",
        policy=_policy(),
    )
    rendered = repr(history.profile) + repr(history.profile.dimensions[0])
    # Values are numeric; ensure we don't dump affinity-like narrative labels.
    assert "friend" not in rendered
    assert "enemy" not in rendered
    assert "trust=" not in rendered


@pytest.mark.asyncio
async def test_service_idempotent_and_asymmetric() -> None:
    alice = InMemoryRelationshipService(AgentId("alice"), policy=_policy())
    bob = InMemoryRelationshipService(AgentId("bob"), policy=_policy())
    request = RelationshipRevisionRequest(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        operation_id="op-a",
        logical_tick=2,
        signals=(_signal(counterpart="bob", memory_ref="m-a"),),
        policy=_policy().as_ref(),
    )
    first = await alice.revise(request)
    second = await alice.revise(request)
    assert first.idempotent is False
    assert second.idempotent is True
    assert first.relationship_id == second.relationship_id
    assert len(await alice.snapshot()) == 1
    assert await bob.snapshot() == ()
    assert await alice.get_directed(target_id=AgentId("bob")) is not None
    reader = alice.as_reader()
    assert len(reader.snapshot()) == 1
    assert reader.snapshot()[0].source_id == AgentId("alice")
    assert reader.snapshot()[0].target_id == AgentId("bob")


@pytest.mark.asyncio
async def test_service_logs_are_metadata_only(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    service = InMemoryRelationshipService(AgentId("alice"), policy=_policy())
    secret_ref = "secret-memory-payload-xyz"
    with caplog.at_level(logging.DEBUG, logger="social.service"):
        await service.revise(
            RelationshipRevisionRequest(
                source_id=AgentId("alice"),
                target_id=AgentId("bob"),
                operation_id="op-log",
                logical_tick=1,
                signals=(_signal(memory_ref=secret_ref, strength=0.91),),
                policy=_policy().as_ref(),
            )
        )
    joined = " ".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert secret_ref not in joined
    assert "0.91" not in joined
    assert "friend" not in joined
    assert "enemy" not in joined


@pytest.mark.asyncio
async def test_foreign_source_rejected() -> None:
    service = InMemoryRelationshipService(AgentId("alice"), policy=_policy())
    with pytest.raises(RelationshipServiceError) as excinfo:
        await service.revise(
            RelationshipRevisionRequest(
                source_id=AgentId("carol"),
                target_id=AgentId("bob"),
                operation_id="op-x",
                logical_tick=1,
                signals=(_signal(counterpart="bob"),),
                policy=_policy().as_ref(),
            )
        )
    assert excinfo.value.code is RelationshipServiceErrorCode.OWNERSHIP


@given(
    left=st.sampled_from(list(RelationshipSignalKind)),
    right=st.sampled_from(list(RelationshipSignalKind)),
)
def test_reverse_independence_property(
    left: RelationshipSignalKind, right: RelationshipSignalKind
) -> None:
    a_to_b, _, _, _ = merge_relationship_revision(
        source_id=AgentId("alice"),
        target_id=AgentId("bob"),
        signals=(_signal(counterpart="bob", kind=left, memory_ref="m-1"),),
        prior=None,
        logical_tick=1,
        operation_id="op-ab",
        policy=_policy(),
    )
    b_to_a, _, _, _ = merge_relationship_revision(
        source_id=AgentId("bob"),
        target_id=AgentId("alice"),
        signals=(_signal(counterpart="alice", kind=right, memory_ref="m-2"),),
        prior=None,
        logical_tick=1,
        operation_id="op-ba",
        policy=_policy(),
    )
    assert a_to_b.profile.relationship_id != b_to_a.profile.relationship_id
