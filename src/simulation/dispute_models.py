"""Bounded canonical ``dispute-resolution-snapshot-v1`` contracts.

The snapshot is an independent read-only artifact. It never grants world
authority, never creates an objective dispute identity, and never carries a
verdict, guilt, liability, ownership truth, or binding settlement.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, fields
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Final, cast

DISPUTE_SNAPSHOT_SCHEMA: Final[str] = "dispute-resolution-snapshot-v1"
DISPUTE_SNAPSHOT_POLICY_VERSION: Final[str] = "dispute-analysis.v1"
SUPPORTED_DISPUTE_SNAPSHOT_SCHEMAS: Final[tuple[str, ...]] = (DISPUTE_SNAPSHOT_SCHEMA,)
DISPUTE_SNAPSHOT_ID_HEX_LEN: Final[int] = 16
DISPUTE_CANDIDATE_ID_PREFIX: Final[str] = "disp-"
DISPUTE_ROW_ID_PREFIX: Final[str] = "disp-"
DISPUTE_CLAIM_ID_PREFIX: Final[str] = "dispcl-"
DISPUTE_RESOLUTION_ID_PREFIX: Final[str] = "dispres-"
DISPUTE_EDGE_ID_PREFIX: Final[str] = "disp-edge-"
DISPUTE_PUBLICATION_ID_PREFIX: Final[str] = "disp-pub-"

MAX_DISPUTE_SNAPSHOT_BYTES: Final[int] = 4 * 1024 * 1024
MAX_DISPUTE_CANDIDATES: Final[int] = 2048
MAX_DISPUTE_CASES: Final[int] = 4096
MAX_DISPUTE_CLAIMS: Final[int] = 8192
MAX_DISPUTE_TESTIMONY: Final[int] = 8192
MAX_DISPUTE_EVIDENCE: Final[int] = 16384
MAX_DISPUTE_RESOLUTIONS: Final[int] = 4096
MAX_DISPUTE_RESPONSES: Final[int] = 16384
MAX_DISPUTE_WINDOWS: Final[int] = 512
MAX_DISPUTE_OBJECTIVE_ROWS: Final[int] = 4096
MAX_DISPUTE_CLAIMS_PER_CANDIDATE: Final[int] = 64
MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE: Final[int] = 32
MAX_RESPONSE_BYTES: Final[int] = 2 * 1024 * 1024
MAX_PAGE_ROWS: Final[int] = 500

DISPUTE_FORBIDDEN_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "verdict",
        "judgment",
        "guilty",
        "liable",
        "true_owner",
        "winner",
        "binding",
        "enforced_by_world",
        "global_dispute_registry",
    }
)

DISPUTE_ARTIFACT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "dispute_invalid_value",
        "dispute_size_limit",
        "dispute_owner_local_id",
        "dispute_digest_mismatch",
        "dispute_page_offset",
        "dispute_page_limit",
        "dispute_publication_exists",
        "dispute_quota_exceeded",
    }
)

DISPUTE_PORT_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "dispute_cursor_purpose",
        "dispute_cursor_invalid",
        "dispute_not_found",
    }
)

_QUANTUM: Final[Decimal] = Decimal("0.000001")
_HEX64_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_OWNER_LOCAL_PREFIXES: Final[tuple[str, ...]] = (
    "dsc-",
    "dcl-",
    "dts-",
    "dev-",
    "drf-",
    "dmr-",
    "dar-",
    "drs-",
    "drp-",
)
_OTHER_CONTEXT_PREFIXES: Final[tuple[str, ...]] = (
    "frule-",
    "frul-",
    "fruv-",
    "frl-",
    "frs-",
    "frv-",
    "org-",
    "orgop-",
    "orgc-",
    "msoc-",
    "off-",
    "inst-",
    "med-",
    "evt-",
    "mem-",
    "art-",
    "rec-",
    "repo-",
    "cmt-",
    "val-",
)
_FOREIGN_CANDIDATE_PREFIXES: Final[tuple[str, ...]] = (
    "frule-",
    "org-",
    "orgop-",
    "orgc-",
    "msoc-",
    "off-",
    "inst-",
    "med-",
)

_DISPUTE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "contested_debt",
        "ownership_claim",
        "contract_interpretation",
        "injury",
        "broken_promise",
        "resource_appropriation",
        "other",
    }
)
_SUBJECT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "commitment",
        "item",
        "resource",
        "action",
        "record",
        "relationship",
        "unspecified",
    }
)
_CASE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "open",
        "evidence_gathering",
        "rule_cited",
        "mediation_referenced",
        "resolution_proposed",
        "contested",
        "apparently_resolved",
        "withdrawn",
        "abandoned",
        "reopened",
        "expired",
    }
)
_CLAIM_ROLES: Final[frozenset[str]] = frozenset(
    {"claim", "counterclaim", "supplementary"}
)
_CLAIM_KINDS: Final[frozenset[str]] = frozenset(
    {
        "debt_owed",
        "item_owned",
        "term_meaning",
        "harm_caused",
        "promise_broken",
        "resource_taken",
        "other",
    }
)
_POLARITIES: Final[frozenset[str]] = frozenset({"affirm", "deny", "uncertain"})
_TESTIMONY_CHANNELS: Final[frozenset[str]] = frozenset({"direct", "communicated"})
_EVIDENCE_CHANNELS: Final[frozenset[str]] = frozenset(
    {"observed", "communicated", "remembered", "recorded", "derived", "unknown"}
)
_EVIDENCE_REFERENCE_KINDS: Final[frozenset[str]] = frozenset(
    {
        "observed_occurrence",
        "observed_communication",
        "memory_trace",
        "reconstructed_memory",
        "artifact",
        "durable_record",
        "repository_entry",
        "commitment",
        "valuation",
        "mediation_record",
        "rule_record",
        "office_record",
        "institution_record",
        "organization_record",
        "unknown",
    }
)
_RULE_APPLICABILITIES: Final[frozenset[str]] = frozenset(
    {"applies", "does_not_apply", "uncertain"}
)
_RULE_INTERPRETATIONS: Final[frozenset[str]] = frozenset(
    {"literal", "narrow", "broad", "custom", "unknown"}
)
_RULE_STATUSES: Final[frozenset[str]] = frozenset(
    {"resolved", "orphaned", "version_mismatch", "contested", "retired"}
)
_AUTHORITY_KINDS: Final[frozenset[str]] = frozenset(
    {
        "self",
        "office",
        "institution",
        "organization",
        "collective_decision",
        "procedure",
        "written_record",
        "custom",
        "unknown",
    }
)
_MEDIATION_LINK_STATUSES: Final[frozenset[str]] = frozenset(
    {"linked", "stale", "orphaned", "disputed"}
)
_RESOLUTION_SOURCES: Final[frozenset[str]] = frozenset(
    {"negotiated", "mediator", "unilateral", "custom", "unknown"}
)
_RESOLUTION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "proposed",
        "partially_accepted",
        "apparently_accepted",
        "contested",
        "withdrawn",
        "expired",
        "superseded",
    }
)
_RESPONSE_KINDS: Final[frozenset[str]] = frozenset(
    {"accept", "reject", "counterpropose", "defer", "withdraw"}
)
_CANDIDATE_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "emerging",
        "active",
        "contested",
        "fragmented",
        "apparently_resolved",
        "dissolved",
        "unknown",
    }
)
_LINEAGE_KINDS: Final[frozenset[str]] = frozenset(
    {"continued", "transformed", "split", "merge", "dissolved", "emerged"}
)
_PROVENANCE_CODES: Final[frozenset[str]] = frozenset(
    {"ok", "partial", "truncated", "empty"}
)


class DisputeArtifactError(ValueError):
    """Stable-code snapshot contract violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DISPUTE_ARTIFACT_ERROR_CODES:
            raise ValueError("dispute_invalid_error_code")
        self.code: str = code
        super().__init__(code)


class DisputePortError(ValueError):
    """Stable-code read/publication port violation with no payload detail."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if code not in DISPUTE_PORT_ERROR_CODES:
            raise ValueError("dispute_invalid_error_code")
        self.code: str = code
        super().__init__(code)


def _fail(code: str = "dispute_invalid_value") -> None:
    raise DisputeArtifactError(code)


def _text(value: object) -> str:
    if type(value) is not str or not value:
        _fail()
    return cast(str, value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _tick(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail()
    return cast(int, value)


def _count(value: object) -> int:
    if type(value) is not int or isinstance(value, bool) or value < 0:
        _fail()
    return cast(int, value)


def _unit(value: object) -> float:
    if type(value) is not float:
        _fail()
    if value != value or value in (float("inf"), float("-inf")):
        _fail()
    quantized = float(Decimal(str(value)).quantize(_QUANTUM, rounding=ROUND_HALF_UP))
    if quantized < 0.0 or quantized > 1.0:
        _fail()
    return quantized


def _ratio_value(observed: int, expected: int) -> float | None:
    if expected == 0:
        return None
    return float(
        (Decimal(observed) / Decimal(expected)).quantize(
            _QUANTUM, rounding=ROUND_HALF_UP
        )
    )


def _hex64(value: object) -> str:
    if type(value) is not str or _HEX64_PATTERN.match(value) is None:
        _fail()
    return cast(str, value)


def _require_enum(value: object, allowed: frozenset[str]) -> str:
    token = _text(value)
    if token not in allowed:
        _fail()
    return token


def _require_id(value: object, prefix: str) -> str:
    token = _text(value)
    pattern = re.compile(
        rf"^{re.escape(prefix)}[0-9a-f]{{{DISPUTE_SNAPSHOT_ID_HEX_LEN}}}$"
    )
    if pattern.match(token) is None:
        _fail()
    return token


def _require_tokens(value: object) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        _fail()
    tokens = tuple(sorted({_text(item) for item in cast("tuple[object, ...]", value)}))
    return tokens


def _reject_owner_ids(token: str) -> None:
    if token.startswith(_OWNER_LOCAL_PREFIXES):
        raise DisputeArtifactError("dispute_owner_local_id")


def _reject_context_ids(token: str) -> None:
    if token.startswith(_OTHER_CONTEXT_PREFIXES):
        _fail()


def require_dispute_snapshot_digest(value: object) -> str:
    return _hex64(value)


def require_dispute_candidate_id(value: object) -> str:
    return _require_id(value, DISPUTE_CANDIDATE_ID_PREFIX)


def require_dispute_claim_id(value: object) -> str:
    return _require_id(value, DISPUTE_CLAIM_ID_PREFIX)


def require_dispute_resolution_id(value: object) -> str:
    return _require_id(value, DISPUTE_RESOLUTION_ID_PREFIX)


def require_dispute_edge_id(value: object) -> str:
    return _require_id(value, DISPUTE_EDGE_ID_PREFIX)


def require_dispute_publication_id(value: object) -> str:
    return _require_id(value, DISPUTE_PUBLICATION_ID_PREFIX)


def _derive(domain: str, material: tuple[str, ...]) -> str:
    payload = "\x1f".join((domain, *material))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[
        :DISPUTE_SNAPSHOT_ID_HEX_LEN
    ]


def _derive_row_id(domain: str, material: tuple[str, ...]) -> str:
    return f"{DISPUTE_ROW_ID_PREFIX}{_derive(domain, material)}"


def dispute_party_set_digest(party_ids: tuple[str, ...]) -> str:
    """Return the canonical digest of one sorted, de-duplicated party set."""
    return hashlib.sha256(
        "\x1f".join(("dispute-party-set", *sorted(set(party_ids)))).encode("utf-8")
    ).hexdigest()


def derive_dispute_case_ref(subject_token: str, party_ids: tuple[str, ...]) -> str:
    """Derive the portable thread digest shared by two owners."""
    token = _text(subject_token)
    parties = dispute_party_set_digest(_require_tokens(party_ids))
    return hashlib.sha256(
        "\x1f".join(("dispute-case", token, parties)).encode("utf-8")
    ).hexdigest()


def derive_dispute_claim_id(
    case_ref: str,
    claimant_id: str,
    role: str,
    claim_kind: str,
    subject_token: str,
    counters_claim_id: str | None = None,
) -> str:
    """Derive one content-addressed ``dispcl-`` claim id."""
    material = (
        _hex64(case_ref),
        _text(claimant_id),
        _require_enum(role, _CLAIM_ROLES),
        _require_enum(claim_kind, _CLAIM_KINDS),
        _text(subject_token),
        ""
        if counters_claim_id is None
        else require_dispute_claim_id(counters_claim_id),
    )
    return f"{DISPUTE_CLAIM_ID_PREFIX}{_derive('dispute-published-claim', material)}"


def derive_dispute_resolution_id(
    case_ref: str, proposer_id: str, terms_digest: str
) -> str:
    """Derive one content-addressed ``dispres-`` resolution id."""
    material = (_hex64(case_ref), _text(proposer_id), _hex64(terms_digest))
    return (
        f"{DISPUTE_RESOLUTION_ID_PREFIX}"
        f"{_derive('dispute-published-resolution', material)}"
    )


def derive_dispute_testimony_id(
    case_ref: str,
    claim_id: str,
    speaker_id: str,
    channel: str,
    root_token: str,
    tick: int,
) -> str:
    material = (
        _hex64(case_ref),
        require_dispute_claim_id(claim_id),
        _text(speaker_id),
        _require_enum(channel, _TESTIMONY_CHANNELS),
        _text(root_token),
        str(_tick(tick)),
    )
    return _derive_row_id("dispute-published-testimony", material)


def derive_dispute_evidence_id(
    case_ref: str,
    claim_id: str,
    channel: str,
    reference_kind: str,
    reference_token: str,
    tick: int,
) -> str:
    material = (
        _hex64(case_ref),
        require_dispute_claim_id(claim_id),
        _require_enum(channel, _EVIDENCE_CHANNELS),
        _require_enum(reference_kind, _EVIDENCE_REFERENCE_KINDS),
        _hex64(reference_token),
        str(_tick(tick)),
    )
    return _derive_row_id("dispute-published-evidence", material)


def derive_dispute_rule_reference_id(
    case_ref: str,
    claim_id: str,
    system_token: str,
    rule_token: str,
    version_number: int,
) -> str:
    material = (
        _hex64(case_ref),
        require_dispute_claim_id(claim_id),
        _text(system_token),
        _text(rule_token),
        str(_count(version_number)),
    )
    return _derive_row_id("dispute-published-rule-reference", material)


def derive_dispute_authority_reference_id(
    case_ref: str, authority_kind: str, reference_token: str
) -> str:
    material = (
        _hex64(case_ref),
        _require_enum(authority_kind, _AUTHORITY_KINDS),
        _text(reference_token),
    )
    return _derive_row_id("dispute-published-authority-reference", material)


def derive_dispute_mediation_reference_id(
    case_ref: str, mediation_case_token: str
) -> str:
    material = (_hex64(case_ref), _text(mediation_case_token))
    return _derive_row_id("dispute-published-mediation-reference", material)


def derive_dispute_response_id(
    resolution_ref: str, party_id: str, kind: str, tick: int, terms_digest: str
) -> str:
    material = (
        _hex64(resolution_ref),
        _text(party_id),
        _require_enum(kind, _RESPONSE_KINDS),
        str(_tick(tick)),
        _hex64(terms_digest),
    )
    return _derive_row_id("dispute-published-response", material)


def derive_dispute_edge_id(source: str, target: str, kind: str, tick: int) -> str:
    """Derive one stable forward-only ``disp-edge-`` identity."""
    material = (
        require_dispute_candidate_id(source),
        require_dispute_candidate_id(target),
        _require_enum(kind, _LINEAGE_KINDS),
        str(_tick(tick)),
    )
    return f"{DISPUTE_EDGE_ID_PREFIX}{_derive('dispute-edge', material)}"


@dataclass(frozen=True, slots=True)
class DisputeSnapshotRef:
    run_id: str
    input_revision: str
    generated_tick: int
    publication_id: str
    snapshot_digest: str
    policy_version: str = DISPUTE_SNAPSHOT_POLICY_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id))
        object.__setattr__(self, "input_revision", _text(self.input_revision))
        object.__setattr__(self, "generated_tick", _tick(self.generated_tick))
        object.__setattr__(
            self,
            "publication_id",
            require_dispute_publication_id(self.publication_id),
        )
        object.__setattr__(
            self,
            "snapshot_digest",
            require_dispute_snapshot_digest(self.snapshot_digest),
        )
        if self.policy_version != DISPUTE_SNAPSHOT_POLICY_VERSION:
            _fail()
        _reject_owner_ids(self.run_id)
        _reject_owner_ids(self.input_revision)


@dataclass(frozen=True, slots=True)
class DisputeCoverage:
    observed: int
    expected: int
    ratio: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        observed = _count(self.observed)
        expected = _count(self.expected)
        if observed > expected:
            _fail()
        object.__setattr__(self, "observed", observed)
        object.__setattr__(self, "expected", expected)
        computed = _ratio_value(observed, expected)
        if self.ratio is None:
            object.__setattr__(self, "ratio", computed)
        else:
            if computed is None or _unit(self.ratio) != computed:
                _fail()
            object.__setattr__(self, "ratio", computed)
        if type(self.note) is not str:
            _fail()
        _reject_owner_ids(self.note)


@dataclass(frozen=True, slots=True)
class DisputeCaseRecord:
    case_ref: str
    kind: str
    subject_kind: str
    subject_token: str
    status: str
    party_ids: tuple[str, ...]
    first_tick: int
    last_tick: int
    coverage: DisputeCoverage

    def __post_init__(self) -> None:
        case_ref = _hex64(self.case_ref)
        kind = _require_enum(self.kind, _DISPUTE_KINDS)
        subject_kind = _require_enum(self.subject_kind, _SUBJECT_KINDS)
        subject_token = _text(self.subject_token)
        parties = _require_tokens(self.party_ids)
        if not parties:
            _fail()
        for party in parties:
            _reject_owner_ids(party)
        if case_ref != derive_dispute_case_ref(subject_token, parties):
            _fail()
        object.__setattr__(self, "case_ref", case_ref)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "subject_kind", subject_kind)
        object.__setattr__(self, "subject_token", subject_token)
        object.__setattr__(self, "status", _require_enum(self.status, _CASE_STATUSES))
        object.__setattr__(self, "party_ids", parties)
        first = _tick(self.first_tick)
        last = _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if type(self.coverage) is not DisputeCoverage:
            _fail()
        _reject_owner_ids(subject_token)


@dataclass(frozen=True, slots=True)
class DisputeClaimRecord:
    claim_id: str
    case_ref: str
    claimant_id: str
    respondent_id: str
    role: str
    claim_kind: str
    polarity: str
    subject_token: str
    counters_claim_ref: str | None
    evidence_count: int
    first_tick: int
    last_tick: int
    candidate_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", require_dispute_claim_id(self.claim_id))
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(self, "claimant_id", _text(self.claimant_id))
        object.__setattr__(self, "respondent_id", _text(self.respondent_id))
        object.__setattr__(self, "role", _require_enum(self.role, _CLAIM_ROLES))
        object.__setattr__(
            self, "claim_kind", _require_enum(self.claim_kind, _CLAIM_KINDS)
        )
        object.__setattr__(self, "polarity", _require_enum(self.polarity, _POLARITIES))
        object.__setattr__(self, "subject_token", _text(self.subject_token))
        if self.counters_claim_ref is not None:
            object.__setattr__(
                self,
                "counters_claim_ref",
                _optional_text(self.counters_claim_ref),
            )
        object.__setattr__(self, "evidence_count", _count(self.evidence_count))
        first = _tick(self.first_tick)
        last = _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if self.candidate_id != "":
            object.__setattr__(
                self, "candidate_id", require_dispute_candidate_id(self.candidate_id)
            )
        for token in (
            self.claimant_id,
            self.respondent_id,
            self.subject_token,
        ):
            _reject_owner_ids(token)
        if self.counters_claim_ref is not None:
            _reject_owner_ids(self.counters_claim_ref)


@dataclass(frozen=True, slots=True)
class DisputeTestimonyRecord:
    testimony_id: str
    case_ref: str
    claim_id: str
    speaker_id: str
    channel: str
    root_token: str
    independently_evidenced: bool
    tick: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "testimony_id", _require_id(self.testimony_id, DISPUTE_ROW_ID_PREFIX)
        )
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(self, "claim_id", require_dispute_claim_id(self.claim_id))
        object.__setattr__(self, "speaker_id", _text(self.speaker_id))
        object.__setattr__(
            self, "channel", _require_enum(self.channel, _TESTIMONY_CHANNELS)
        )
        object.__setattr__(self, "root_token", _text(self.root_token))
        if type(self.independently_evidenced) is not bool:
            _fail()
        object.__setattr__(self, "tick", _tick(self.tick))
        for token in (self.speaker_id, self.root_token):
            _reject_owner_ids(token)


@dataclass(frozen=True, slots=True)
class DisputeEvidenceRecord:
    evidence_id: str
    case_ref: str
    claim_id: str
    channel: str
    reference_kind: str
    reference_token: str
    tick: int
    independently_evidenced: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "evidence_id", _require_id(self.evidence_id, DISPUTE_ROW_ID_PREFIX)
        )
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(self, "claim_id", require_dispute_claim_id(self.claim_id))
        object.__setattr__(
            self, "channel", _require_enum(self.channel, _EVIDENCE_CHANNELS)
        )
        object.__setattr__(
            self,
            "reference_kind",
            _require_enum(self.reference_kind, _EVIDENCE_REFERENCE_KINDS),
        )
        object.__setattr__(self, "reference_token", _hex64(self.reference_token))
        object.__setattr__(self, "tick", _tick(self.tick))
        if type(self.independently_evidenced) is not bool:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeRuleReferenceRecord:
    rule_reference_id: str
    case_ref: str
    claim_ref: str
    system_token: str
    rule_token: str
    version_number: int
    applicability: str
    interpretation: str
    status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rule_reference_id",
            _require_id(self.rule_reference_id, DISPUTE_ROW_ID_PREFIX),
        )
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(self, "claim_ref", require_dispute_claim_id(self.claim_ref))
        system_token = _text(self.system_token)
        rule_token = _text(self.rule_token)
        _reject_owner_ids(system_token)
        _reject_owner_ids(rule_token)
        _reject_context_ids(rule_token)
        object.__setattr__(self, "system_token", system_token)
        object.__setattr__(self, "rule_token", rule_token)
        version = _count(self.version_number)
        if version < 1:
            _fail()
        object.__setattr__(self, "version_number", version)
        object.__setattr__(
            self,
            "applicability",
            _require_enum(self.applicability, _RULE_APPLICABILITIES),
        )
        object.__setattr__(
            self,
            "interpretation",
            _require_enum(self.interpretation, _RULE_INTERPRETATIONS),
        )
        object.__setattr__(self, "status", _require_enum(self.status, _RULE_STATUSES))


@dataclass(frozen=True, slots=True)
class DisputeAuthorityReferenceRecord:
    authority_reference_id: str
    case_ref: str
    authority_kind: str
    reference_token: str
    strength: float
    uncertainty: float
    dissenting: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "authority_reference_id",
            _require_id(self.authority_reference_id, DISPUTE_ROW_ID_PREFIX),
        )
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(
            self,
            "authority_kind",
            _require_enum(self.authority_kind, _AUTHORITY_KINDS),
        )
        reference_token = _text(self.reference_token)
        _reject_owner_ids(reference_token)
        _reject_context_ids(reference_token)
        object.__setattr__(self, "reference_token", reference_token)
        object.__setattr__(self, "strength", _unit(self.strength))
        object.__setattr__(self, "uncertainty", _unit(self.uncertainty))
        if type(self.dissenting) is not bool:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeMediationReferenceRecord:
    mediation_reference_id: str
    case_ref: str
    mediation_case_token: str
    recommendation_token: str | None
    response_token: str | None
    outcome_token: str | None
    link_status: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mediation_reference_id",
            _require_id(self.mediation_reference_id, DISPUTE_ROW_ID_PREFIX),
        )
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(
            self, "mediation_case_token", _text(self.mediation_case_token)
        )
        for name in ("recommendation_token", "response_token", "outcome_token"):
            token = _optional_text(getattr(self, name))
            if token is not None:
                _reject_owner_ids(token)
                _reject_context_ids(token)
            object.__setattr__(self, name, token)
        object.__setattr__(
            self,
            "link_status",
            _require_enum(self.link_status, _MEDIATION_LINK_STATUSES),
        )


@dataclass(frozen=True, slots=True)
class DisputeResolutionRecord:
    resolution_id: str
    resolution_ref: str
    case_ref: str
    proposer_id: str
    source: str
    terms_digest: str
    status: str
    first_tick: int
    last_tick: int
    expires_tick: int | None
    accepted_party_count: int
    rejected_party_count: int
    candidate_id: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resolution_id",
            require_dispute_resolution_id(self.resolution_id),
        )
        object.__setattr__(self, "resolution_ref", _hex64(self.resolution_ref))
        object.__setattr__(self, "case_ref", _hex64(self.case_ref))
        object.__setattr__(self, "proposer_id", _text(self.proposer_id))
        object.__setattr__(
            self, "source", _require_enum(self.source, _RESOLUTION_SOURCES)
        )
        object.__setattr__(self, "terms_digest", _hex64(self.terms_digest))
        object.__setattr__(
            self, "status", _require_enum(self.status, _RESOLUTION_STATUSES)
        )
        first = _tick(self.first_tick)
        last = _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if self.expires_tick is not None:
            object.__setattr__(self, "expires_tick", _tick(self.expires_tick))
        object.__setattr__(
            self, "accepted_party_count", _count(self.accepted_party_count)
        )
        object.__setattr__(
            self, "rejected_party_count", _count(self.rejected_party_count)
        )
        if self.candidate_id != "":
            object.__setattr__(
                self, "candidate_id", require_dispute_candidate_id(self.candidate_id)
            )
        _reject_owner_ids(self.proposer_id)


@dataclass(frozen=True, slots=True)
class DisputeResolutionResponseRecord:
    response_id: str
    resolution_ref: str
    party_id: str
    kind: str
    tick: int
    terms_digest: str
    active: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "response_id", _require_id(self.response_id, DISPUTE_ROW_ID_PREFIX)
        )
        object.__setattr__(self, "resolution_ref", _hex64(self.resolution_ref))
        object.__setattr__(self, "party_id", _text(self.party_id))
        object.__setattr__(self, "kind", _require_enum(self.kind, _RESPONSE_KINDS))
        object.__setattr__(self, "tick", _tick(self.tick))
        object.__setattr__(self, "terms_digest", _hex64(self.terms_digest))
        if type(self.active) is not bool:
            _fail()
        _reject_owner_ids(self.party_id)


@dataclass(frozen=True, slots=True)
class DisputeCandidateRecord:
    candidate_id: str
    kind: str
    subject_token: str
    party_count: int
    owner_count: int
    case_count: int
    claim_count: int
    counterclaim_count: int
    testimony_count: int
    evidence_count: int
    resolution_count: int
    disagreement_count: int
    status: str
    first_tick: int
    last_tick: int
    coverage: DisputeCoverage

    def __post_init__(self) -> None:
        candidate_id = require_dispute_candidate_id(self.candidate_id)
        if candidate_id.startswith(_FOREIGN_CANDIDATE_PREFIXES):
            _fail()
        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "kind", _require_enum(self.kind, _DISPUTE_KINDS))
        subject_token = _text(self.subject_token)
        _reject_owner_ids(subject_token)
        object.__setattr__(self, "subject_token", subject_token)
        for name in (
            "party_count",
            "owner_count",
            "case_count",
            "claim_count",
            "counterclaim_count",
            "testimony_count",
            "evidence_count",
            "resolution_count",
            "disagreement_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.claim_count > MAX_DISPUTE_CLAIMS_PER_CANDIDATE:
            raise DisputeArtifactError("dispute_size_limit")
        if self.resolution_count > MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE:
            raise DisputeArtifactError("dispute_size_limit")
        object.__setattr__(
            self, "status", _require_enum(self.status, _CANDIDATE_STATUSES)
        )
        first = _tick(self.first_tick)
        last = _tick(self.last_tick)
        if last < first:
            _fail()
        object.__setattr__(self, "first_tick", first)
        object.__setattr__(self, "last_tick", last)
        if type(self.coverage) is not DisputeCoverage:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeObjectiveRow:
    tick: int
    observed_occurrence_count: int
    observed_transfer_count: int
    observed_harm_count: int
    observed_commitment_count: int
    observed_record_count: int
    observed_communication_count: int

    def __post_init__(self) -> None:
        for name in (
            "tick",
            "observed_occurrence_count",
            "observed_transfer_count",
            "observed_harm_count",
            "observed_commitment_count",
            "observed_record_count",
            "observed_communication_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class DisputeWindowRecord:
    start_tick: int
    end_tick: int
    owner_count: int
    candidate_count: int
    claim_count: int

    def __post_init__(self) -> None:
        start = _tick(self.start_tick)
        end = _tick(self.end_tick)
        if end < start:
            _fail()
        object.__setattr__(self, "start_tick", start)
        object.__setattr__(self, "end_tick", end)
        object.__setattr__(self, "owner_count", _count(self.owner_count))
        object.__setattr__(self, "candidate_count", _count(self.candidate_count))
        object.__setattr__(self, "claim_count", _count(self.claim_count))


@dataclass(frozen=True, slots=True)
class DisputeLineageEdgeRecord:
    edge_id: str
    source: str
    target: str
    kind: str
    tick: int

    def __post_init__(self) -> None:
        edge_id = require_dispute_edge_id(self.edge_id)
        source = require_dispute_candidate_id(self.source)
        target = require_dispute_candidate_id(self.target)
        kind = _require_enum(self.kind, _LINEAGE_KINDS)
        tick = _tick(self.tick)
        if edge_id != derive_dispute_edge_id(source, target, kind, tick):
            _fail()
        object.__setattr__(self, "edge_id", edge_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "tick", tick)


@dataclass(frozen=True, slots=True)
class DisputeCounts:
    candidate_count: int = 0
    case_count: int = 0
    claim_count: int = 0
    counterclaim_count: int = 0
    testimony_count: int = 0
    evidence_count: int = 0
    resolution_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    owner_count: int = 0
    response_count: int = 0
    edge_count: int = 0
    rule_reference_count: int = 0
    authority_reference_count: int = 0
    mediation_reference_count: int = 0
    objective_row_count: int = 0
    window_count: int = 0

    def __post_init__(self) -> None:
        for name in (
            "candidate_count",
            "case_count",
            "claim_count",
            "counterclaim_count",
            "testimony_count",
            "evidence_count",
            "resolution_count",
            "accepted_count",
            "rejected_count",
            "owner_count",
            "response_count",
            "edge_count",
            "rule_reference_count",
            "authority_reference_count",
            "mediation_reference_count",
            "objective_row_count",
            "window_count",
        ):
            object.__setattr__(self, name, _count(getattr(self, name)))
        if self.counterclaim_count > self.claim_count:
            _fail()
        if self.accepted_count + self.rejected_count > self.response_count:
            _fail()


@dataclass(frozen=True, slots=True)
class DisputeSnapshot:
    ref: DisputeSnapshotRef
    coverage: DisputeCoverage
    candidates: tuple[DisputeCandidateRecord, ...] = ()
    cases: tuple[DisputeCaseRecord, ...] = ()
    claims: tuple[DisputeClaimRecord, ...] = ()
    testimony: tuple[DisputeTestimonyRecord, ...] = ()
    evidence: tuple[DisputeEvidenceRecord, ...] = ()
    rule_references: tuple[DisputeRuleReferenceRecord, ...] = ()
    authority_references: tuple[DisputeAuthorityReferenceRecord, ...] = ()
    mediation_references: tuple[DisputeMediationReferenceRecord, ...] = ()
    resolutions: tuple[DisputeResolutionRecord, ...] = ()
    responses: tuple[DisputeResolutionResponseRecord, ...] = ()
    objective_rows: tuple[DisputeObjectiveRow, ...] = ()
    windows: tuple[DisputeWindowRecord, ...] = ()
    lineage: tuple[DisputeLineageEdgeRecord, ...] = ()
    counts: DisputeCounts = DisputeCounts()
    provenance_code: str = "empty"
    schema_version: str = DISPUTE_SNAPSHOT_SCHEMA

    def __post_init__(self) -> None:
        if type(self.ref) is not DisputeSnapshotRef:
            _fail()
        if self.schema_version != DISPUTE_SNAPSHOT_SCHEMA:
            _fail()
        if type(self.coverage) is not DisputeCoverage:
            _fail()
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(self.candidates, key=lambda item: item.candidate_id)),
        )
        object.__setattr__(
            self, "cases", tuple(sorted(self.cases, key=lambda item: item.case_ref))
        )
        object.__setattr__(
            self, "claims", tuple(sorted(self.claims, key=lambda item: item.claim_id))
        )
        object.__setattr__(
            self,
            "testimony",
            tuple(sorted(self.testimony, key=lambda item: item.testimony_id)),
        )
        object.__setattr__(
            self,
            "evidence",
            tuple(sorted(self.evidence, key=lambda item: item.evidence_id)),
        )
        object.__setattr__(
            self,
            "rule_references",
            tuple(
                sorted(self.rule_references, key=lambda item: item.rule_reference_id)
            ),
        )
        object.__setattr__(
            self,
            "authority_references",
            tuple(
                sorted(
                    self.authority_references,
                    key=lambda item: item.authority_reference_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "mediation_references",
            tuple(
                sorted(
                    self.mediation_references,
                    key=lambda item: item.mediation_reference_id,
                )
            ),
        )
        object.__setattr__(
            self,
            "resolutions",
            tuple(sorted(self.resolutions, key=lambda item: item.resolution_id)),
        )
        object.__setattr__(
            self,
            "responses",
            tuple(
                sorted(
                    self.responses,
                    key=lambda item: (item.resolution_ref, item.response_id),
                )
            ),
        )
        object.__setattr__(
            self,
            "objective_rows",
            tuple(sorted(self.objective_rows, key=lambda item: item.tick)),
        )
        object.__setattr__(
            self,
            "windows",
            tuple(sorted(self.windows, key=lambda item: item.start_tick)),
        )
        object.__setattr__(
            self,
            "lineage",
            tuple(sorted(self.lineage, key=lambda item: item.edge_id)),
        )
        if type(self.counts) is not DisputeCounts:
            _fail()
        object.__setattr__(
            self,
            "provenance_code",
            _require_enum(self.provenance_code, _PROVENANCE_CODES),
        )
        for name, cap in (
            ("candidates", MAX_DISPUTE_CANDIDATES),
            ("cases", MAX_DISPUTE_CASES),
            ("claims", MAX_DISPUTE_CLAIMS),
            ("testimony", MAX_DISPUTE_TESTIMONY),
            ("evidence", MAX_DISPUTE_EVIDENCE),
            ("resolutions", MAX_DISPUTE_RESOLUTIONS),
            ("responses", MAX_DISPUTE_RESPONSES),
            ("windows", MAX_DISPUTE_WINDOWS),
            ("objective_rows", MAX_DISPUTE_OBJECTIVE_ROWS),
        ):
            if len(getattr(self, name)) > cap:
                raise DisputeArtifactError("dispute_size_limit")
        _validate_tables(self)
        _reject_snapshot_owner_ids(self)


def _validate_tables(snapshot: DisputeSnapshot) -> None:
    candidate_ids = {item.candidate_id for item in snapshot.candidates}
    if len(candidate_ids) != len(snapshot.candidates):
        _fail()
    case_refs = {item.case_ref for item in snapshot.cases}
    if len(case_refs) != len(snapshot.cases):
        _fail()
    claim_ids = {item.claim_id for item in snapshot.claims}
    if len(claim_ids) != len(snapshot.claims):
        _fail()
    resolution_refs = {item.resolution_ref for item in snapshot.resolutions}
    if len(resolution_refs) != len(snapshot.resolutions):
        _fail()
    row_ids: list[str] = [
        *(item.candidate_id for item in snapshot.candidates),
        *(item.claim_id for item in snapshot.claims),
        *(item.resolution_id for item in snapshot.resolutions),
        *(item.testimony_id for item in snapshot.testimony),
        *(item.evidence_id for item in snapshot.evidence),
        *(item.rule_reference_id for item in snapshot.rule_references),
        *(item.authority_reference_id for item in snapshot.authority_references),
        *(item.mediation_reference_id for item in snapshot.mediation_references),
        *(item.response_id for item in snapshot.responses),
        *(item.edge_id for item in snapshot.lineage),
    ]
    if len(set(row_ids)) != len(row_ids):
        _fail()
    evidence_per_claim: dict[str, int] = {}
    for evidence in snapshot.evidence:
        if evidence.case_ref not in case_refs or evidence.claim_id not in claim_ids:
            _fail()
        evidence_per_claim[evidence.claim_id] = (
            evidence_per_claim.get(evidence.claim_id, 0) + 1
        )
    for claim in snapshot.claims:
        if claim.case_ref not in case_refs:
            _fail()
        if claim.candidate_id != "" and claim.candidate_id not in candidate_ids:
            _fail()
        if claim.counters_claim_ref is not None:
            if (
                claim.counters_claim_ref not in claim_ids
                or claim.counters_claim_ref == claim.claim_id
            ):
                _fail()
        if claim.evidence_count != evidence_per_claim.get(claim.claim_id, 0):
            _fail()
    for testimony in snapshot.testimony:
        if testimony.case_ref not in case_refs or testimony.claim_id not in claim_ids:
            _fail()
    for rule in snapshot.rule_references:
        if rule.case_ref not in case_refs or rule.claim_ref not in claim_ids:
            _fail()
    for authority in snapshot.authority_references:
        if authority.case_ref not in case_refs:
            _fail()
    for mediation in snapshot.mediation_references:
        if mediation.case_ref not in case_refs:
            _fail()
    responses_by_resolution: dict[str, list[DisputeResolutionResponseRecord]] = {}
    for response in snapshot.responses:
        if response.resolution_ref not in resolution_refs:
            _fail()
        responses_by_resolution.setdefault(response.resolution_ref, []).append(response)
    for resolution in snapshot.resolutions:
        if resolution.case_ref not in case_refs:
            _fail()
        if (
            resolution.candidate_id != ""
            and resolution.candidate_id not in candidate_ids
        ):
            _fail()
        responses = responses_by_resolution.get(resolution.resolution_ref, [])
        accepted = sum(1 for item in responses if item.active and item.kind == "accept")
        rejected = sum(1 for item in responses if item.active and item.kind == "reject")
        if (
            resolution.accepted_party_count != accepted
            or resolution.rejected_party_count != rejected
        ):
            _fail()
    objective_ticks = [row.tick for row in snapshot.objective_rows]
    if len(set(objective_ticks)) != len(objective_ticks):
        _fail()
    for edge in snapshot.lineage:
        if edge.source not in candidate_ids or edge.target not in candidate_ids:
            _fail()
    _ensure_acyclic(snapshot.lineage)
    expected = {
        "candidate_count": len(snapshot.candidates),
        "case_count": len(snapshot.cases),
        "claim_count": len(snapshot.claims),
        "counterclaim_count": sum(
            1 for item in snapshot.claims if item.role == "counterclaim"
        ),
        "testimony_count": len(snapshot.testimony),
        "evidence_count": len(snapshot.evidence),
        "resolution_count": len(snapshot.resolutions),
        "accepted_count": sum(
            1 for item in snapshot.responses if item.active and item.kind == "accept"
        ),
        "rejected_count": sum(
            1 for item in snapshot.responses if item.active and item.kind == "reject"
        ),
        "response_count": len(snapshot.responses),
        "edge_count": len(snapshot.lineage),
    }
    for name, value in expected.items():
        if getattr(snapshot.counts, name) != value:
            _fail()


def _ensure_acyclic(lineage: tuple[DisputeLineageEdgeRecord, ...]) -> None:
    edges: dict[str, set[str]] = {}
    for edge in lineage:
        edges.setdefault(edge.source, set()).add(edge.target)
    visiting: set[str] = set()
    settled: set[str] = set()

    def visit(node: str) -> None:
        if node in settled:
            return
        if node in visiting:
            _fail()
        visiting.add(node)
        for target in sorted(edges.get(node, ())):
            visit(target)
        visiting.discard(node)
        settled.add(node)

    for node in sorted(edges):
        visit(node)


def _reject_snapshot_owner_ids(snapshot: DisputeSnapshot) -> None:
    for item in fields(snapshot):
        _walk_owner_ids(getattr(snapshot, item.name))


def _walk_owner_ids(value: object) -> None:
    if type(value) is str:
        _reject_owner_ids(value)
        return
    if isinstance(value, tuple):
        for item in value:
            _walk_owner_ids(item)
        return
    if hasattr(value, "__dataclass_fields__"):
        record = cast(Any, value)
        for item in fields(record):
            _walk_owner_ids(getattr(record, item.name))


def empty_dispute_snapshot(
    ref: DisputeSnapshotRef, *, coverage: DisputeCoverage
) -> DisputeSnapshot:
    """Return one empty but valid canonical snapshot with a real digest."""

    if type(ref) is not DisputeSnapshotRef:
        raise TypeError("ref must be DisputeSnapshotRef")
    if type(coverage) is not DisputeCoverage:
        raise TypeError("coverage must be DisputeCoverage")
    snapshot = DisputeSnapshot(
        ref=ref,
        coverage=coverage,
        counts=DisputeCounts(),
        provenance_code="empty",
    )
    from simulation.dispute_codec import finalize_dispute_snapshot

    return finalize_dispute_snapshot(snapshot)


__all__ = [
    "DISPUTE_ARTIFACT_ERROR_CODES",
    "DISPUTE_CANDIDATE_ID_PREFIX",
    "DISPUTE_CLAIM_ID_PREFIX",
    "DISPUTE_EDGE_ID_PREFIX",
    "DISPUTE_FORBIDDEN_FIELD_NAMES",
    "DISPUTE_PORT_ERROR_CODES",
    "DISPUTE_PUBLICATION_ID_PREFIX",
    "DISPUTE_RESOLUTION_ID_PREFIX",
    "DISPUTE_ROW_ID_PREFIX",
    "DISPUTE_SNAPSHOT_ID_HEX_LEN",
    "DISPUTE_SNAPSHOT_POLICY_VERSION",
    "DISPUTE_SNAPSHOT_SCHEMA",
    "MAX_DISPUTE_CANDIDATES",
    "MAX_DISPUTE_CASES",
    "MAX_DISPUTE_CLAIMS",
    "MAX_DISPUTE_CLAIMS_PER_CANDIDATE",
    "MAX_DISPUTE_EVIDENCE",
    "MAX_DISPUTE_OBJECTIVE_ROWS",
    "MAX_DISPUTE_RESOLUTIONS",
    "MAX_DISPUTE_RESOLUTIONS_PER_CANDIDATE",
    "MAX_DISPUTE_RESPONSES",
    "MAX_DISPUTE_SNAPSHOT_BYTES",
    "MAX_DISPUTE_TESTIMONY",
    "MAX_DISPUTE_WINDOWS",
    "MAX_PAGE_ROWS",
    "MAX_RESPONSE_BYTES",
    "SUPPORTED_DISPUTE_SNAPSHOT_SCHEMAS",
    "DisputeArtifactError",
    "DisputeAuthorityReferenceRecord",
    "DisputeCandidateRecord",
    "DisputeCaseRecord",
    "DisputeClaimRecord",
    "DisputeCounts",
    "DisputeCoverage",
    "DisputeEvidenceRecord",
    "DisputeLineageEdgeRecord",
    "DisputeMediationReferenceRecord",
    "DisputeObjectiveRow",
    "DisputePortError",
    "DisputeResolutionRecord",
    "DisputeResolutionResponseRecord",
    "DisputeRuleReferenceRecord",
    "DisputeSnapshot",
    "DisputeSnapshotRef",
    "DisputeTestimonyRecord",
    "DisputeWindowRecord",
    "derive_dispute_authority_reference_id",
    "derive_dispute_case_ref",
    "derive_dispute_claim_id",
    "derive_dispute_edge_id",
    "derive_dispute_evidence_id",
    "derive_dispute_mediation_reference_id",
    "derive_dispute_resolution_id",
    "derive_dispute_response_id",
    "derive_dispute_rule_reference_id",
    "derive_dispute_testimony_id",
    "dispute_party_set_digest",
    "empty_dispute_snapshot",
    "require_dispute_candidate_id",
    "require_dispute_claim_id",
    "require_dispute_edge_id",
    "require_dispute_publication_id",
    "require_dispute_resolution_id",
    "require_dispute_snapshot_digest",
]
