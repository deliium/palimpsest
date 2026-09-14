"""Typed communication envelopes between agents."""

from social.contracts import EnvelopeSender
from social.models import CommunicationEnvelope, EnvelopeId

__all__ = ["CommunicationEnvelope", "EnvelopeId", "EnvelopeSender"]
