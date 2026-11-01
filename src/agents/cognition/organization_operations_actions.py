"""Closed classification of existing commands against operational beliefs.

These helpers only recognize that an already-selected ordinary command is
consistent with an owner's operational belief. They never construct, return,
rewrite, or submit a command, and they never create a physical effect. Every
world change remains an ordinary agent command admitted by ``WorldEngine``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from agents.cognition.organization_operations import (
    OrganizationAdmissionStance,
    OrganizationAssignmentStance,
    OrganizationCommitmentStance,
    OrganizationControlStance,
    OrganizationDepartureStance,
    OrganizationOperationDomain,
    OrganizationOperationLedger,
)
from world.actions import (
    Amend,
    AnnotateRecord,
    Build,
    ContributeCollectiveProject,
    CopyRecord,
    DepositRecord,
    Drop,
    EstablishRepository,
    Give,
    Help,
    Inscribe,
    MaintainPublicGood,
    MaintainRepository,
    Repair,
    RetrieveRecord,
    Store,
    Take,
    Talk,
    Tell,
    TransferArtifact,
)

__all__ = [
    "ORGANIZATION_DOMAIN_COMMANDS",
    "organization_commitment_follow_through",
    "organization_domain_allows",
    "organization_operation_command_support",
]

ORGANIZATION_DOMAIN_COMMANDS: Final[
    Mapping[OrganizationOperationDomain, tuple[type, ...]]
] = MappingProxyType(
    {
        OrganizationOperationDomain.RESOURCE_CONTROL: (Give, Take, Drop, Store),
        OrganizationOperationDomain.STORAGE: (
            Store,
            Take,
            DepositRecord,
            RetrieveRecord,
        ),
        OrganizationOperationDomain.RECORD_KEEPING: (
            Inscribe,
            Amend,
            CopyRecord,
            AnnotateRecord,
            TransferArtifact,
            DepositRecord,
        ),
        OrganizationOperationDomain.MEMBERSHIP_ADMISSION: (Talk, Tell),
        OrganizationOperationDomain.MEMBERSHIP_DEPARTURE: (Talk, Tell),
        OrganizationOperationDomain.ROLE_ASSIGNMENT: (Talk, Tell),
        OrganizationOperationDomain.PROCEDURE_ACTION: (
            Help,
            ContributeCollectiveProject,
            MaintainPublicGood,
            MaintainRepository,
            EstablishRepository,
            Build,
            Repair,
        ),
        OrganizationOperationDomain.INTERNAL_COMMITMENT: (
            Give,
            ContributeCollectiveProject,
            DepositRecord,
        ),
    }
)

_CONTROL_DOMAIN_STANCES: Final[
    Mapping[OrganizationOperationDomain, frozenset[str]]
] = MappingProxyType(
    {
        OrganizationOperationDomain.RESOURCE_CONTROL: frozenset(
            {
                OrganizationControlStance.CLAIMED.value,
                OrganizationControlStance.RECOGNIZED.value,
                OrganizationControlStance.SHARED.value,
                OrganizationControlStance.DISPUTED.value,
            }
        ),
        OrganizationOperationDomain.STORAGE: frozenset(
            {
                OrganizationControlStance.CLAIMED.value,
                OrganizationControlStance.RECOGNIZED.value,
                OrganizationControlStance.SHARED.value,
                OrganizationControlStance.DISPUTED.value,
            }
        ),
        OrganizationOperationDomain.RECORD_KEEPING: frozenset(
            {
                OrganizationControlStance.CLAIMED.value,
                OrganizationControlStance.RECOGNIZED.value,
                OrganizationControlStance.SHARED.value,
                OrganizationControlStance.DISPUTED.value,
            }
        ),
    }
)

_ADMISSION_STANCES: Final[frozenset[str]] = frozenset(
    {
        OrganizationAdmissionStance.ADMITTED.value,
        OrganizationAdmissionStance.CLAIMED.value,
        OrganizationAdmissionStance.SELF_JOINED.value,
        OrganizationAdmissionStance.DISPUTED.value,
    }
)
_DEPARTURE_STANCES: Final[frozenset[str]] = frozenset(
    {
        OrganizationDepartureStance.RESIGNED.value,
        OrganizationDepartureStance.EXPELLED.value,
        OrganizationDepartureStance.DEPARTED.value,
        OrganizationDepartureStance.DISPUTED.value,
    }
)
_ASSIGNMENT_STANCES: Final[frozenset[str]] = frozenset(
    {
        OrganizationAssignmentStance.ASSIGNED.value,
        OrganizationAssignmentStance.CLAIMED.value,
        OrganizationAssignmentStance.DISPUTED.value,
    }
)
_COMMITMENT_STANCES: Final[frozenset[str]] = frozenset(
    {
        OrganizationCommitmentStance.DECLARED.value,
        OrganizationCommitmentStance.ACCEPTED.value,
        OrganizationCommitmentStance.FULFILLED.value,
        OrganizationCommitmentStance.DISPUTED.value,
    }
)


def organization_domain_allows(
    domain: OrganizationOperationDomain, command: object
) -> bool:
    """Return whether this domain's allowlist contains the command class."""

    if type(domain) is not OrganizationOperationDomain:
        raise TypeError("domain must be OrganizationOperationDomain")
    return type(command) in ORGANIZATION_DOMAIN_COMMANDS[domain]


def _counterpart(command: object) -> str | None:
    for name in ("recipient_id", "target_id", "item_id", "project_id", "repository_id"):
        value = getattr(command, name, None)
        if value is not None and hasattr(value, "value"):
            return value.value
    return None


def _control_anchor(command: object) -> str | None:
    for name in ("item_id", "target_id", "artifact_id", "repository_id"):
        value = getattr(command, name, None)
        if value is not None and hasattr(value, "value"):
            return value.value
    return None


def _domain_is_active(
    concept: object,
    domain: OrganizationOperationDomain,
    *,
    owner_value: str,
    counterpart: str | None,
) -> bool:
    if domain in _CONTROL_DOMAIN_STANCES:
        return any(
            control.domain is domain
            and control.stance.value in _CONTROL_DOMAIN_STANCES[domain]
            for control in concept.controls
        )
    if domain is OrganizationOperationDomain.MEMBERSHIP_ADMISSION:
        return any(
            record.stance.value in _ADMISSION_STANCES
            and (counterpart is None or record.member_id == counterpart)
            for record in concept.admissions
        )
    if domain is OrganizationOperationDomain.MEMBERSHIP_DEPARTURE:
        return any(
            record.stance.value in _DEPARTURE_STANCES
            and (counterpart is None or record.member_id == counterpart)
            for record in concept.departures
        )
    if domain is OrganizationOperationDomain.ROLE_ASSIGNMENT:
        return any(
            record.stance.value in _ASSIGNMENT_STANCES
            and (counterpart is None or record.occupant_id == counterpart)
            for record in concept.assignments
        )
    if domain is OrganizationOperationDomain.PROCEDURE_ACTION:
        return bool(concept.procedures)
    if domain is OrganizationOperationDomain.INTERNAL_COMMITMENT:
        return any(
            record.stance.value in _COMMITMENT_STANCES
            and (counterpart is None or record.counterpart_id == counterpart)
            for record in concept.commitments
        )
    return False


def organization_operation_command_support(
    ledger: object | None, command: object
) -> tuple[OrganizationOperationDomain, ...]:
    """Return active operational domains consistent with this command."""

    if type(ledger) is not OrganizationOperationLedger:
        return ()
    owner_value = ledger.owner_id.value
    counterpart = _counterpart(command)
    supported: list[OrganizationOperationDomain] = []
    for domain in OrganizationOperationDomain:
        if type(command) not in ORGANIZATION_DOMAIN_COMMANDS[domain]:
            continue
        if any(
            _domain_is_active(
                concept,
                domain,
                owner_value=owner_value,
                counterpart=counterpart,
            )
            for concept in ledger.concepts
        ):
            supported.append(domain)
    return tuple(supported)


def organization_commitment_follow_through(
    ledger: object | None, command: object
) -> str | None:
    """Return the exact commitment id a selected command would fulfill."""

    if type(ledger) is not OrganizationOperationLedger:
        return None
    if type(command) is Give:
        target = command.recipient_id.value
        allowed_commands = Give
    elif type(command) is ContributeCollectiveProject:
        target = command.project_id.value
        allowed_commands = ContributeCollectiveProject
    elif type(command) is DepositRecord:
        target = command.repository_id.value
        allowed_commands = DepositRecord
    else:
        return None
    if type(command) is not allowed_commands:
        return None
    for concept in ledger.concepts:
        for record in concept.commitments:
            if record.counterpart_id != target:
                continue
            if record.stance.value in (
                OrganizationCommitmentStance.FULFILLED.value,
                OrganizationCommitmentStance.FORGOTTEN.value,
                OrganizationCommitmentStance.VIOLATED.value,
            ):
                continue
            return record.commitment_id
    return None
