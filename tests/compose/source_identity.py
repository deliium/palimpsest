"""Pure parsing of release-image source attestation labels.

The producer never invents cleanliness: a revision plus exactly one of a true
clean assertion or a canonical SHA-256 source digest is required. All failure
modes raise closed, payload-free codes.
"""

from __future__ import annotations

from collections.abc import Mapping

__all__ = ["parse_source_identity_labels"]

_DIGEST_CHARS = frozenset("0123456789abcdef")


def parse_source_identity_labels(labels: Mapping[str, object]) -> tuple[str, list[str]]:
    """Return the verified revision and the exact producer source arguments."""
    revision = str(labels.get("org.opencontainers.image.revision") or "")
    clean = str(labels.get("io.palimpsest.source-clean") or "")
    digest = str(labels.get("io.palimpsest.source-artifact-digest") or "")
    if revision == "" or revision == "unknown":
        raise RuntimeError("source_revision_missing")
    if clean == "true" and digest:
        raise RuntimeError("source_assertion_conflicting")
    if clean == "true":
        return revision, ["--source-clean"]
    if digest:
        if len(digest) != 64 or any(
            character not in _DIGEST_CHARS for character in digest
        ):
            raise RuntimeError("source_digest_invalid")
        return revision, ["--source-artifact-digest", digest]
    raise RuntimeError("source_assertion_missing")
