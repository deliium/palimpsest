"""Detached, tokenized competing-theory facts. Never cognition ledgers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = [
    "COMPETING_THEORIES_ANALYSIS_VERSION",
    "COMPETING_THEORIES_WINDOW_TICKS",
    "MAX_THEORY_WINDOWS",
    "CompetingTheoryAnalysis",
    "CompetingTheoryFacts",
    "TheoryCaseRow",
    "TheoryCitationFact",
    "TheoryCitationRow",
    "TheoryClaimFact",
    "TheoryClaimRow",
    "TheoryCommunityRow",
    "TheoryCoverageRow",
    "TheoryForecastFact",
    "TheoryReceiptFact",
    "TheoryStanceFact",
    "TheorySupportEdge",
    "TheoryTransmissionEdge",
    "harvest_facts_error",
    "require_theory_token",
]

COMPETING_THEORIES_ANALYSIS_VERSION: Final[str] = "competing-theories-analysis-v1"
COMPETING_THEORIES_WINDOW_TICKS: Final[int] = 32
MAX_THEORY_WINDOWS: Final[int] = 512


class CompetingTheoriesAnalysisError(ValueError):
    """Safe detached theory-analysis failure."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("competing_theories_analysis_invalid_code")
        self.code = code
        super().__init__(code)


def harvest_facts_error(code: str) -> CompetingTheoriesAnalysisError:
    return CompetingTheoriesAnalysisError(code)


def _count(name: str, value: object) -> int:
    if isinstance(value, bool) or type(value) is not int or value < 0:
        raise ValueError(f"{name}: invalid_count")
    return value


def require_theory_token(name: str, value: object) -> str:
    if type(value) is not str or not value or len(value) > 128:
        raise ValueError(f"{name}: invalid_token")
    if not all(char.isalnum() or char in ":._-" for char in value):
        raise ValueError(f"{name}: invalid_token")
    return value


@dataclass(frozen=True, slots=True)
class TheoryClaimFact:
    claim_token: str
    owner_token: str
    context_token: str
    account: str
    category: str
    created_tick: int

    def __post_init__(self) -> None:
        for name in ("claim_token", "owner_token", "context_token"):
            require_theory_token(name, getattr(self, name))
        if self.account not in {"continuity", "recurrence"}:
            raise ValueError("account: invalid")
        if not self.category:
            raise ValueError("category: invalid")
        _count("created_tick", self.created_tick)


@dataclass(frozen=True, slots=True)
class TheoryStanceFact:
    owner_token: str
    context_token: str
    claim_token: str
    tick: int
    revision: str

    def __post_init__(self) -> None:
        for name in ("owner_token", "context_token", "claim_token", "revision"):
            require_theory_token(name, getattr(self, name))
        _count("tick", self.tick)


@dataclass(frozen=True, slots=True)
class TheoryCitationFact:
    owner_token: str
    claim_token: str
    polarity: str
    kind: str
    root_token: str
    tick: int
    independent: bool

    def __post_init__(self) -> None:
        for name in ("owner_token", "claim_token", "root_token"):
            require_theory_token(name, getattr(self, name))
        if self.polarity not in {"supports", "contradicts", "context_only"}:
            raise ValueError("polarity: invalid")
        if self.kind not in {
            "own_observation",
            "own_scored_case",
            "delivered_claim",
            "declared_pointer",
        }:
            raise ValueError("kind: invalid")
        _count("tick", self.tick)
        if type(self.independent) is not bool:
            raise ValueError("independent: invalid")


@dataclass(frozen=True, slots=True)
class TheoryReceiptFact:
    speaker_token: str
    learner_token: str
    context_token: str
    claim_token: str
    act: str
    tick: int
    origin: bool
    kind: str
    occurrence: str

    def __post_init__(self) -> None:
        for name in (
            "speaker_token",
            "learner_token",
            "context_token",
            "claim_token",
            "occurrence",
        ):
            require_theory_token(name, getattr(self, name))
        if self.act not in {"share", "support", "withdraw", "teach"}:
            raise ValueError("act: invalid")
        if self.kind not in {"communicated", "taught"}:
            raise ValueError("kind: invalid")
        _count("tick", self.tick)
        if type(self.origin) is not bool:
            raise ValueError("origin: invalid")


@dataclass(frozen=True, slots=True)
class TheoryForecastFact:
    owner_token: str
    case_token: str
    context_token: str
    alphabet: tuple[str, ...]
    rows: tuple[tuple[str, str, int, int], ...]
    issued_tick: int
    target_tick: int
    state: str
    observed_category: str | None
    observed_tick: int | None
    vectors: tuple[tuple[str, tuple[int, ...]], ...] = ()
    hits: tuple[tuple[str, bool], ...] = ()

    def __post_init__(self) -> None:
        for name in ("owner_token", "case_token", "context_token"):
            require_theory_token(name, getattr(self, name))
        if not self.alphabet:
            raise ValueError("alphabet: invalid")
        _count("issued_tick", self.issued_tick)
        _count("target_tick", self.target_tick)
        if self.state not in {"pending", "scored", "not_comparable", "unavailable"}:
            raise ValueError("state: invalid")
        for claim_token, hit in self.hits:
            require_theory_token("claim_token", claim_token)
            if type(hit) is not bool:
                raise ValueError("hits: invalid")
        vector_tokens: set[str] = set()
        for claim_token, vector in self.vectors:
            require_theory_token("claim_token", claim_token)
            if claim_token in vector_tokens:
                raise ValueError("vectors: duplicate")
            vector_tokens.add(claim_token)
            if len(vector) != len(self.alphabet):
                raise ValueError("vectors: length")
            if any(
                isinstance(value, bool) or type(value) is not int
                for value in vector
            ):
                raise ValueError("vectors: invalid")
            if sum(vector) != 1000 or any(value < 0 for value in vector):
                raise ValueError("vectors: invalid")
        for claim_token, predicted, probabilities, brier in self.rows:
            require_theory_token("claim_token", claim_token)
            if predicted not in self.alphabet:
                raise ValueError("predicted: invalid")
            _count("probabilities", probabilities)
            _count("brier", brier)


@dataclass(frozen=True, slots=True)
class TheorySupportEdge:
    window_start: int
    window_end: int
    owner_token: str
    claim_token: str


@dataclass(frozen=True, slots=True)
class TheoryCommunityRow:
    window_start: int
    window_end: int
    claim_token: str
    community_token: str
    owner_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TheoryTransmissionEdge:
    window_start: int
    window_end: int
    speaker_token: str
    learner_token: str
    claim_token: str
    act: str


@dataclass(frozen=True, slots=True)
class TheoryCoverageRow:
    window_start: int
    window_end: int
    observed_owners: int
    expected_owners: int
    unavailable_owners: int
    omitted_windows: int


@dataclass(frozen=True, slots=True)
class CompetingTheoryFacts:
    """Frozen tokenized owner facts from one completed run."""

    run_token: str
    owner_tokens: tuple[str, ...]
    claims: tuple[TheoryClaimFact, ...]
    stances: tuple[TheoryStanceFact, ...]
    citations: tuple[TheoryCitationFact, ...]
    receipts: tuple[TheoryReceiptFact, ...]
    forecasts: tuple[TheoryForecastFact, ...]
    owner_last_ticks: tuple[tuple[str, int], ...]
    death_ticks: tuple[tuple[str, int], ...] = ()
    window_ticks: int = COMPETING_THEORIES_WINDOW_TICKS

    def __post_init__(self) -> None:
        require_theory_token("run_token", self.run_token)
        if not isinstance(self.owner_tokens, tuple):
            raise ValueError("owner_tokens: invalid_type")
        for token in self.owner_tokens:
            require_theory_token("owner_token", token)
        claim_tokens = {row.claim_token for row in self.claims}
        for stance in self.stances:
            if stance.claim_token not in claim_tokens:
                raise ValueError("stance: unknown_claim")
        for citation in self.citations:
            if citation.claim_token not in claim_tokens:
                raise ValueError("citation: unknown_claim")
        for receipt in self.receipts:
            if receipt.claim_token not in claim_tokens:
                raise ValueError("receipt: unknown_claim")
        for forecast in self.forecasts:
            for claim_token, _, _, _ in forecast.rows:
                if claim_token not in claim_tokens:
                    raise ValueError("forecast: unknown_claim")
        if self.window_ticks < 1:
            raise ValueError("window_ticks: invalid")


@dataclass(frozen=True, slots=True)
class TheoryClaimRow:
    """One retained owner explanation with its window placement."""

    claim_token: str
    owner_token: str
    context_token: str
    account: str
    category: str
    created_tick: int
    window_start: int
    window_end: int


@dataclass(frozen=True, slots=True)
class TheoryCaseRow:
    """One frozen same-case contest with per-claim forecasts and outcomes."""

    case_token: str
    owner_token: str
    window_start: int
    window_end: int
    state: str
    observed_category: str
    issued_tick: int
    target_tick: int
    rows: tuple[tuple[str, str, str, int], ...]


@dataclass(frozen=True, slots=True)
class TheoryCitationRow:
    """One attributed citation retained for a claim."""

    claim_token: str
    owner_token: str
    window_start: int
    window_end: int
    kind: str
    polarity: str
    root_token: str
    independent: bool
    tick: int


@dataclass(frozen=True, slots=True)
class CompetingTheoryAnalysis:
    structure_rows: tuple[tuple[int, int, int, int], ...]
    support_edges: tuple[TheorySupportEdge, ...]
    communities: tuple[TheoryCommunityRow, ...]
    citation_rows: tuple[tuple[int, int, str, str, int, int, int], ...]
    prediction_rows: tuple[tuple[int, int, int, int, int, int], ...]
    failure_rows: tuple[tuple[int, int, int], ...]
    transmission_edges: tuple[TheoryTransmissionEdge, ...]
    coverage: tuple[TheoryCoverageRow, ...]
    claim_rows: tuple[TheoryClaimRow, ...]
    case_rows: tuple[TheoryCaseRow, ...]
    citation_edges: tuple[TheoryCitationRow, ...]
    claim_count: int
    rival_pair_count: int
    support_edge_count: int
    community_count: int
    citation_count: int
    verified_root_count: int
    prediction_count: int
    scored_count: int
    failure_count: int
    unscored_count: int
    delivered_count: int
    teaching_count: int
    paired_count: int
    paired_brier_difference: int

    def rows_for(self, section: str) -> tuple[object, ...]:
        return {
            "theories": self.structure_rows,
            "support": self.support_edges,
            "communities": self.communities,
            "citations": self.citation_rows,
            "predictions": self.prediction_rows,
            "failures": self.failure_rows,
            "transmission": self.transmission_edges,
            "coverage": self.coverage,
        }[section]
