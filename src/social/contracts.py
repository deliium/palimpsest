"""Ports for typed communication envelopes."""

from __future__ import annotations

from typing import Protocol

from social.models import CommunicationEnvelope


class EnvelopeSender(Protocol):
    def send(self, envelope: CommunicationEnvelope) -> None:
        """Transmit an immutable envelope. Must not share mutable payloads."""
        ...
