"""Detached contact-family inputs shared by composition and metric assembly."""

from __future__ import annotations

from dataclasses import dataclass

from analysis.contact_cultural_change import ContactCulturalChangeResult
from analysis.contact_hybrid_practice import ContactHybridPracticeResult
from analysis.contact_knowledge_transfer import ContactKnowledgeTransferResult
from analysis.contact_lexical_borrowing import ContactLexicalBorrowingResult
from analysis.contact_reputation_transfer import ContactReputationTransferResult
from analysis.society_contact import SocietyContactResult

__all__ = ["ContactAnalysisInputs"]


@dataclass(frozen=True, slots=True)
class ContactAnalysisInputs:
    contact: SocietyContactResult
    cultural_change: ContactCulturalChangeResult
    hybrid_practice: ContactHybridPracticeResult
    knowledge_transfer: ContactKnowledgeTransferResult
    lexical_borrowing: ContactLexicalBorrowingResult
    reputation_transfer: ContactReputationTransferResult
