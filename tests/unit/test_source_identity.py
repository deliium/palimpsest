"""Release-image source attestation labels never invent cleanliness."""

from __future__ import annotations

import pytest

from tests.compose.source_identity import parse_source_identity_labels

_DIGEST = "a" * 64


def test_clean_checkout_forwards_the_clean_assertion_only() -> None:
    revision, arguments = parse_source_identity_labels(
        {
            "org.opencontainers.image.revision": "abc123",
            "io.palimpsest.source-clean": "true",
            "io.palimpsest.source-artifact-digest": "",
        }
    )
    assert revision == "abc123"
    assert arguments == ["--source-clean"]


def test_dirty_checkout_forwards_the_exact_digest() -> None:
    revision, arguments = parse_source_identity_labels(
        {
            "org.opencontainers.image.revision": "abc123",
            "io.palimpsest.source-clean": "false",
            "io.palimpsest.source-artifact-digest": _DIGEST,
        }
    )
    assert revision == "abc123"
    assert arguments == ["--source-artifact-digest", _DIGEST]


@pytest.mark.parametrize(
    "labels, code",
    (
        ({"org.opencontainers.image.revision": ""}, "source_revision_missing"),
        ({"org.opencontainers.image.revision": "unknown"}, "source_revision_missing"),
        (
            {
                "org.opencontainers.image.revision": "abc123",
                "io.palimpsest.source-clean": "true",
                "io.palimpsest.source-artifact-digest": _DIGEST,
            },
            "source_assertion_conflicting",
        ),
        (
            {"org.opencontainers.image.revision": "abc123"},
            "source_assertion_missing",
        ),
        (
            {
                "org.opencontainers.image.revision": "abc123",
                "io.palimpsest.source-artifact-digest": "not-a-digest",
            },
            "source_digest_invalid",
        ),
        (
            {
                "org.opencontainers.image.revision": "abc123",
                "io.palimpsest.source-artifact-digest": "A" * 64,
            },
            "source_digest_invalid",
        ),
    ),
)
def test_missing_invalid_or_conflicting_attestations_fail_closed(
    labels: dict[str, object], code: str
) -> None:
    with pytest.raises(RuntimeError, match=code):
        parse_source_identity_labels(labels)
