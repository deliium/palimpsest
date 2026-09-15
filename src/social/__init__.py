"""Typed communication envelopes between agents."""

from social.contracts import EnvelopeSender
from social.models import (
    CommunicationEnvelope,
    EnvelopeId,
    Relationship,
    RelationshipId,
)

__all__ = [
    "CommunicationEnvelope",
    "EnvelopeId",
    "EnvelopeSender",
    "Relationship",
    "RelationshipId",
]
