"""One deterministic detached accounting ledger analysis harvest."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from analysis.accounting_ledgers_contract import (
    ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION,
    AccountingAnalysisError,
    AccountingCoverage,
)
from analysis.accounting_ledgers_detection import (
    detect_accounting_counterparties,
    detect_accounting_entries,
    detect_accounting_flows,
    detect_record_conditions,
)
from analysis.accounting_ledgers_events import (
    accounting_evidence_rows_from_events,
)
from analysis.accounting_ledgers_expectations import (
    AccountingOwnerRowInput,
    join_accounting_owners,
)
from analysis.accounting_ledgers_policy import (
    AccountingLedgersAnalysisPolicy,
    default_accounting_ledgers_analysis_policy,
)
from analysis.accounting_ledgers_rows import (
    AccountingAlignmentRow,
    AccountingCounterpartyRow,
    AccountingFlowRow,
    AccountingRecordConditionRow,
    AccountingRecordEvidenceRow,
    AnalyticalAccountingEntryRow,
)

__all__ = [
    "ACCOUNTING_LEDGERS_COVERAGE_KEYS",
    "AccountingLedgersAnalysis",
    "accounting_ledgers_analysis_digest",
    "empty_accounting_ledgers_analysis",
    "harvest_accounting_ledgers_analysis",
]

_LOG: Final[logging.Logger] = logging.getLogger(
    "analysis.accounting_ledgers.analysis"
)

ACCOUNTING_LEDGERS_COVERAGE_KEYS: Final[tuple[str, ...]] = (
    "entries",
    "records",
    "conditions",
    "flows",
    "counterparties",
    "alignments",
)


def _tuple(name: str, values: object) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, set, frozenset)) or not isinstance(
        values, (list, tuple)
    ):
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    return tuple(values)


@dataclass(frozen=True, slots=True)
class AccountingLedgersAnalysis:
    """Bounded detached accounting rows with explicit per-family coverage."""

    run_id: str
    entries: tuple[AnalyticalAccountingEntryRow, ...] = ()
    records: tuple[AccountingRecordEvidenceRow, ...] = ()
    conditions: tuple[AccountingRecordConditionRow, ...] = ()
    flows: tuple[AccountingFlowRow, ...] = ()
    counterparties: tuple[AccountingCounterpartyRow, ...] = ()
    alignments: tuple[AccountingAlignmentRow, ...] = ()
    owners: tuple[AccountingOwnerRowInput, ...] = ()
    coverage: Mapping[str, AccountingCoverage] = MappingProxyType({})
    truncated: bool = False
    notices: tuple[str, ...] = ()
    policy_version: str = ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION
    digest: str = ""

    def __post_init__(self) -> None:
        if type(self.run_id) is not str or not self.run_id:
            raise AccountingAnalysisError("accounting_analysis_missing_input")
        if self.policy_version != ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION:
            raise AccountingAnalysisError("accounting_analysis_invalid_policy")
        for name in (
            "entries",
            "records",
            "conditions",
            "flows",
            "counterparties",
            "alignments",
            "owners",
            "notices",
        ):
            object.__setattr__(self, name, _tuple(name, getattr(self, name)))
        coverage = dict(self.coverage)
        if set(coverage) != set(ACCOUNTING_LEDGERS_COVERAGE_KEYS):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        for value in coverage.values():
            if type(value) is not AccountingCoverage:
                raise AccountingAnalysisError("accounting_analysis_invalid_row")
        object.__setattr__(self, "coverage", MappingProxyType(coverage))
        if type(self.truncated) is not bool:
            raise AccountingAnalysisError("accounting_analysis_invalid_row")
        if self.digest and (
            type(self.digest) is not str or len(self.digest) != 64
        ):
            raise AccountingAnalysisError("accounting_analysis_invalid_row")

    @property
    def source_layers(self) -> tuple[str, ...]:
        return ("analytical_entry",)


def _coverage_map(
    *, entries: Sequence[object], records: Sequence[object],
    conditions: Sequence[object], flows: Sequence[object],
    counterparties: Sequence[object], alignments: Sequence[object],
    notices: Sequence[str],
) -> Mapping[str, AccountingCoverage]:
    values: dict[str, AccountingCoverage] = {}
    for key, rows in (
        ("entries", entries),
        ("records", records),
        ("conditions", conditions),
        ("flows", flows),
        ("counterparties", counterparties),
        ("alignments", alignments),
    ):
        if not rows:
            values[key] = AccountingCoverage.MISSING
        elif notices:
            values[key] = AccountingCoverage.PARTIAL
        else:
            values[key] = AccountingCoverage.COMPLETE
    return MappingProxyType(values)


def empty_accounting_ledgers_analysis(run_id: str) -> AccountingLedgersAnalysis:
    """Return an absent-channel analysis with all six families missing."""

    coverage = MappingProxyType(
        {key: AccountingCoverage.MISSING for key in ACCOUNTING_LEDGERS_COVERAGE_KEYS}
    )
    analysis = AccountingLedgersAnalysis(run_id=run_id, coverage=coverage)
    return AccountingLedgersAnalysis(
        run_id=analysis.run_id,
        coverage=analysis.coverage,
        digest=accounting_ledgers_analysis_digest(analysis),
    )


def harvest_accounting_ledgers_analysis(
    *,
    run_id: str,
    events: Sequence[object],
    owner_rows: Sequence[AccountingOwnerRowInput] = (),
    policy: AccountingLedgersAnalysisPolicy | None = None,
) -> AccountingLedgersAnalysis:
    """Build one deterministic analysis from committed events and owner rows."""

    active = (
        default_accounting_ledgers_analysis_policy()
        if policy is None
        else policy
    )
    if type(active) is not AccountingLedgersAnalysisPolicy:
        raise AccountingAnalysisError("accounting_analysis_invalid_policy")
    evidence = accounting_evidence_rows_from_events(
        events, run_id=run_id, policy=active
    )
    if not evidence.records and not evidence.transfers and not evidence.claims:
        return empty_accounting_ledgers_analysis(run_id)
    entries = detect_accounting_entries(evidence, active)
    conditions = detect_record_conditions(entries, active)
    flows = detect_accounting_flows(
        entries, evidence.transfers, evidence.contributions, active
    )
    counterparties = detect_accounting_counterparties(evidence.claims, active)
    join = join_accounting_owners(
        owner_rows=tuple(owner_rows),
        record_rows=evidence.records,
        transfer_rows=evidence.transfers,
        policy=active,
    )
    notices = tuple(
        sorted(set(evidence.notices) | set(join.notices))
    )[:8]
    coverage = _coverage_map(
        entries=entries,
        records=evidence.records,
        conditions=conditions,
        flows=flows,
        counterparties=counterparties,
        alignments=join.alignments,
        notices=notices,
    )
    truncated = any(
        value is AccountingCoverage.PARTIAL for value in coverage.values()
    )
    for key, value in coverage.items():
        if value is AccountingCoverage.PARTIAL:
            _LOG.warning("accounting_ledgers_analysis_truncated family=%s", key)
    analysis = AccountingLedgersAnalysis(
        run_id=run_id,
        entries=entries,
        records=evidence.records,
        conditions=conditions,
        flows=flows,
        counterparties=counterparties,
        alignments=join.alignments,
        owners=join.owner_rows,
        coverage=coverage,
        truncated=truncated,
        notices=notices,
    )
    analysis = AccountingLedgersAnalysis(
        **{
            **{
                name: getattr(analysis, name)
                for name in analysis.__dataclass_fields__
                if name != "digest"
            },
            "digest": accounting_ledgers_analysis_digest(analysis),
        }
    )
    _LOG.info("accounting_ledgers_analysis_built families=6")
    return analysis


def accounting_ledgers_analysis_digest(
    analysis: AccountingLedgersAnalysis,
) -> str:
    """Stable digest over canonical analysis rows."""

    if type(analysis) is not AccountingLedgersAnalysis:
        raise AccountingAnalysisError("accounting_analysis_invalid_row")
    lines = [ACCOUNTING_LEDGERS_ANALYSIS_POLICY_VERSION, analysis.run_id]
    for entry in analysis.entries:
        lines.append(
            "|".join(
                (
                    entry.entry_token,
                    entry.record_token,
                    entry.entry_kind.value,
                    entry.direction.value,
                    entry.item_kind,
                    str(entry.quantity),
                    entry.assessment.value,
                    str(entry.confidence_milli),
                    str(entry.first_tick),
                    str(entry.last_tick),
                    str(entry.window_index),
                )
            )
        )
    for record in analysis.records:
        lines.append(
            "|".join(
                (
                    record.record_token,
                    record.record_genre,
                    record.observed_integrity.value,
                    str(record.content_revision),
                    record.author_token,
                    str(record.tick),
                    str(record.event_ordinal),
                    str(record.copy_generation),
                    str(int(record.tombstoned)),
                )
            )
        )
    for condition in analysis.conditions:
        lines.append(
            "|".join(
                (
                    condition.condition,
                    str(condition.record_count),
                    str(condition.share_milli),
                    str(condition.window_index),
                    condition.availability,
                )
            )
        )
    for flow in analysis.flows:
        lines.append(
            "|".join(
                (
                    flow.entry_kind.value,
                    flow.direction.value,
                    str(flow.event_count),
                    str(flow.quantity_sum),
                    str(flow.owner_count),
                    str(flow.counterparty_count),
                    str(flow.window_index),
                )
            )
        )
    for counterparty in analysis.counterparties:
        lines.append(
            "|".join(
                (
                    counterparty.counterparty_token,
                    str(counterparty.entry_count),
                    ",".join(counterparty.kinds),
                    str(counterparty.first_tick),
                    str(counterparty.last_tick),
                )
            )
        )
    for alignment in analysis.alignments:
        lines.append(
            "|".join(
                (
                    alignment.entry_token,
                    alignment.alignment.value,
                    str(alignment.gap_milli),
                    alignment.record_token,
                )
            )
        )
    lines.extend(analysis.notices)
    for key in ACCOUNTING_LEDGERS_COVERAGE_KEYS:
        lines.append(f"{key}:{analysis.coverage[key].value}")
    lines.append(str(int(analysis.truncated)))
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
