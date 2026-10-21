"""Bounded institutional mark and speech frame codec."""

from __future__ import annotations

import pytest

from agents.cognition import institutional_memory_frames as frames
from agents.cognition.institutional_memory import (
    InstitutionalBindingKind,
    InstitutionalFact,
)
from agents.cognition.institutional_memory_frames import (
    INSTITUTIONAL_FRAME_SUBJECT,
    INSTITUTIONAL_TEACH_PREDICATE,
    INSTITUTIONAL_TRANSMIT_PREDICATE,
    NONE_FRAME_PARENT,
    InstitutionalMemoryFrame,
    decode_institutional_marks,
    encode_institutional_marks,
    institutional_frame_relation,
    parse_institutional_frame_relation,
)
from world.artifacts import ArtifactContent
from world.communications import CommunicationContent, CommunicationRelation

_CONTEXT = "c_0123456789abcdef"
_ROOT = "r_" + "a" * 24
_PARENT = "p_" + "b" * 24


def _fact(
    subject: str = "trade", predicate: str = "owes", target: str = "grain"
) -> InstitutionalFact:
    return InstitutionalFact(subject, predicate, target)


def _frame(
    *,
    facts: tuple[InstitutionalFact, ...] | None = None,
    declared: int | None = None,
    parent: str = NONE_FRAME_PARENT,
) -> InstitutionalMemoryFrame:
    return InstitutionalMemoryFrame(
        binding_kind=InstitutionalBindingKind.ROLE,
        function_token="trade",
        context_digest=_CONTEXT,
        root=_ROOT,
        parent=parent,
        facts=facts or (_fact(),),
        declared_fact_count=declared,
    )


def test_single_fact_known_answer() -> None:
    frame = _frame()
    assert encode_institutional_marks(frame) == (
        "im_v1",
        "role",
        "trade",
        _CONTEXT,
        _ROOT,
        NONE_FRAME_PARENT,
        "n_1",
        "trade",
        "owes",
        "grain",
    )
    decoded = decode_institutional_marks(encode_institutional_marks(frame))
    assert decoded == frame


def test_two_and_three_fact_known_answers() -> None:
    two = _frame(
        facts=(_fact(), _fact("trade", "owes", "salt")),
        declared=2,
    )
    marks = encode_institutional_marks(two)
    assert marks[6] == "n_2"
    assert marks[7:] == ("trade", "owes", "grain", "trade", "owes", "salt")
    assert decode_institutional_marks(marks) == two

    three = _frame(
        facts=(
            _fact(),
            _fact("trade", "owes", "salt"),
            _fact("trade", "owes", "cloth"),
        ),
        declared=3,
    )
    marks = encode_institutional_marks(three)
    assert len(marks) == 16
    assert decode_institutional_marks(marks) == three


def test_physical_artifact_accepts_full_frame() -> None:
    frame = _frame(
        facts=(
            _fact(),
            _fact("trade", "owes", "salt"),
            _fact("trade", "owes", "cloth"),
        ),
        declared=3,
    )
    marks = encode_institutional_marks(frame)
    content = ArtifactContent(marks=marks)
    assert content.marks == marks
    assert content.relations == ()
    assert decode_institutional_marks(content.marks) == frame


def test_every_truncation_point_is_bounded() -> None:
    frame = _frame(
        facts=(
            _fact(),
            _fact("trade", "owes", "salt"),
            _fact("trade", "owes", "cloth"),
        ),
        declared=3,
    )
    marks = encode_institutional_marks(frame)
    for end in range(len(marks) + 1):
        decoded = decode_institutional_marks(marks[:end])
        if end < 10:
            assert decoded is None
            continue
        assert decoded is not None
        expected = min((end - 7) // 3, 3)
        assert decoded.facts == frame.facts[:expected]
        assert decoded.declared_fact_count == 3
        assert decoded.partial is (expected < 3)


def test_duplicates_round_trip() -> None:
    frame = _frame(
        facts=(_fact(), _fact()),
        declared=2,
    )
    assert decode_institutional_marks(encode_institutional_marks(frame)) == frame


def test_long_but_valid_tokens_round_trip() -> None:
    token = "a" * 32
    frame = _frame(
        facts=(_fact(token, token, token), _fact(token, token, "b" * 32)),
        declared=2,
    )
    assert decode_institutional_marks(encode_institutional_marks(frame)) == frame


def test_invalid_headers_are_rejected() -> None:
    valid = encode_institutional_marks(_frame())
    assert decode_institutional_marks(valid[1:]) is None
    assert decode_institutional_marks(("im_v2", *valid[1:])) is None
    assert decode_institutional_marks((*valid[:6], "n_4", *valid[7:])) is None
    assert decode_institutional_marks((*valid[:3], "c_short", *valid[4:])) is None
    assert decode_institutional_marks((*valid[:5], "p_bad", *valid[6:])) is None


def test_extra_body_triples_are_rejected() -> None:
    valid = encode_institutional_marks(_frame(declared=1))
    assert decode_institutional_marks((*valid, "trade", "owes", "salt")) is None
    assert decode_institutional_marks((*valid, "trade")) is None


def test_valid_wrong_token_swap_remains_a_different_claim() -> None:
    valid = encode_institutional_marks(_frame(facts=(_fact("trade", "owes", "grain"),)))
    swapped = (*valid[:7], "grain", "owes", "trade")
    decoded = decode_institutional_marks(swapped)
    assert decoded is not None
    assert decoded.facts[0] == _fact("grain", "owes", "trade")
    assert decoded.facts[0] != _fact("trade", "owes", "grain")


def test_speech_relation_full_round_trip() -> None:
    frame = _frame()
    relation = institutional_frame_relation(frame)
    assert relation is not None
    assert relation.subject == INSTITUTIONAL_FRAME_SUBJECT
    assert relation.predicate == INSTITUTIONAL_TRANSMIT_PREDICATE
    assert parse_institutional_frame_relation(relation) == frame


def test_speech_relation_teaching_predicate() -> None:
    frame = _frame()
    relation = institutional_frame_relation(frame, teaching=True)
    assert relation is not None
    assert relation.predicate == INSTITUTIONAL_TEACH_PREDICATE
    assert parse_institutional_frame_relation(relation) == frame


def test_speech_relation_chooses_largest_whole_fact_prefix() -> None:
    token = "a" * 32
    frame = _frame(
        facts=(
            _fact(token, token, token),
            _fact(token, token, "b" * 32),
            _fact(token, token, "c" * 32),
        ),
        declared=3,
    )
    relation = institutional_frame_relation(frame)
    assert relation is not None
    assert len(relation.object) <= 256
    decoded = parse_institutional_frame_relation(relation)
    assert decoded is not None
    assert 1 <= len(decoded.facts) < 3
    assert decoded.facts == frame.facts[: len(decoded.facts)]
    assert decoded.declared_fact_count == 3
    assert decoded.partial is True
    assert all(len(item) <= 32 for item in relation.object.split("|"))


def test_speech_relation_reports_unencodable_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(frames, "_MAX_RELATION_CHARS", 50)
    assert institutional_frame_relation(_frame()) is None


def test_unrelated_relations_are_not_parsed() -> None:
    text_relation = CommunicationRelation("trade", "owes", "grain")
    assert parse_institutional_frame_relation(text_relation) is None
    other = CommunicationRelation(INSTITUTIONAL_FRAME_SUBJECT, "im_other", "role|trade")
    assert parse_institutional_frame_relation(other) is None
    assert parse_institutional_frame_relation(object()) is None  # type: ignore[arg-type]


def test_existing_content_and_relations_are_preserved() -> None:
    frame = _frame()
    relation = institutional_frame_relation(frame)
    assert relation is not None
    existing = CommunicationRelation("trade", "offers", "salt")
    content = CommunicationContent(
        text="an ordinary statement",
        relations=(existing, relation),
    )
    assert content.text == "an ordinary statement"
    assert content.relations[0] == existing
    assert parse_institutional_frame_relation(content.relations[1]) == frame


def test_body_loss_is_not_reconstructed_from_relations_or_roots() -> None:
    frame = _frame(
        facts=(
            _fact(),
            _fact("trade", "owes", "salt"),
            _fact("trade", "owes", "cloth"),
        ),
        declared=3,
    )
    content = ArtifactContent(marks=encode_institutional_marks(frame), relations=())
    damaged = ArtifactContent(marks=content.marks[:12], relations=content.relations)
    decoded = decode_institutional_marks(damaged.marks)
    assert decoded is not None
    assert len(decoded.facts) == 1
    assert decoded.facts == frame.facts[:1]
    assert damaged.relations == ()
    assert decoded.facts != frame.facts


def test_frame_repr_exposes_no_tokens_or_roots() -> None:
    frame = _frame()
    text = repr(frame)
    assert "trade" not in text
    assert _ROOT not in text
    assert _CONTEXT not in text
    assert "fact_count=1" in text
