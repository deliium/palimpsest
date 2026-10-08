"""Private experiment law catalog. Imported only by world rules."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from world.experimentation import (
    ExperimentDeltaKind,
    ExperimentHarmBand,
    ExperimentOperator,
    ExperimentOutcomeClass,
    ExperimentProcessToken,
)
from world.models import Item, Resource
from world.production import ProductionCatalog, ToolMark
from world.values import ItemKind, ResourceKind

_LOG: Final[logging.Logger] = logging.getLogger("world._experiment_laws")

_EMIT: Final[frozenset[ExperimentDeltaKind]] = frozenset(
    {
        ExperimentDeltaKind.EMIT_CATALOG_PRODUCT,
        ExperimentDeltaKind.PARTIAL_EMIT,
    }
)


def _fail(reason_code: str) -> ValueError:
    _LOG.warning("experiment_law_catalog_rejected reason_code=%s", reason_code)
    return ValueError(reason_code)


def _operand_token(value: str) -> str:
    prefix, sep, rest = value.partition(":")
    if sep != ":" or not rest or prefix not in {"item", "resource", "tool"}:
        raise _fail("experiment_law_operand_unprefixed")
    if prefix == "item" and rest not in {kind.value for kind in ItemKind}:
        raise _fail("experiment_law_operand_invalid")
    if prefix == "resource" and rest not in {kind.value for kind in ResourceKind}:
        raise _fail("experiment_law_operand_invalid")
    if prefix == "tool" and rest != "strike":
        raise _fail("experiment_law_operand_invalid")
    return value


@dataclass(frozen=True, slots=True)
class ExperimentLaw:
    """One deterministic law row. No sampled outcome."""

    operator: ExperimentOperator
    operand_a_kind: str
    operand_b_kind: str
    process_token: ExperimentProcessToken
    outcome_class: ExperimentOutcomeClass
    delta: ExperimentDeltaKind
    product_id: str = ""
    harm_band: ExperimentHarmBand = ExperimentHarmBand.NONE
    public_technique_token: str = ""

    def __post_init__(self) -> None:
        if type(self.operator) is not ExperimentOperator:
            raise _fail("experiment_law_operator_invalid")
        if type(self.process_token) is not ExperimentProcessToken:
            raise _fail("experiment_law_process_invalid")
        if type(self.outcome_class) is not ExperimentOutcomeClass:
            raise _fail("experiment_law_outcome_invalid")
        if type(self.delta) is not ExperimentDeltaKind:
            raise _fail("experiment_law_delta_invalid")
        if type(self.harm_band) is not ExperimentHarmBand:
            raise _fail("experiment_law_harm_band_invalid")
        object.__setattr__(
            self, "operand_a_kind", _operand_token(self.operand_a_kind)
        )
        allow_none = self.operator is ExperimentOperator.VARY_PROCESS
        if allow_none and self.operand_b_kind == "none":
            object.__setattr__(self, "operand_b_kind", "none")
        else:
            object.__setattr__(
                self, "operand_b_kind", _operand_token(self.operand_b_kind)
            )
        if (
            self.operator is ExperimentOperator.VARY_PROCESS
            and self.process_token is ExperimentProcessToken.NONE
        ):
            raise _fail("experiment_law_process_invalid")
        if (
            self.operator is not ExperimentOperator.VARY_PROCESS
            and self.process_token is not ExperimentProcessToken.NONE
        ):
            raise _fail("experiment_law_process_invalid")
        if self.delta in _EMIT:
            if type(self.product_id) is not str or not self.product_id:
                raise _fail("experiment_law_product_invalid")
        elif self.product_id != "":
            raise _fail("experiment_law_product_invalid")
        if self.delta is ExperimentDeltaKind.APPLY_HARM_BAND:
            if self.harm_band is ExperimentHarmBand.NONE:
                raise _fail("experiment_law_harm_band_invalid")
        elif self.harm_band is not ExperimentHarmBand.NONE:
            raise _fail("experiment_law_harm_band_invalid")

    @property
    def match_key(self) -> tuple[str, str, str, str]:
        return (
            self.operator.value,
            self.operand_a_kind,
            self.operand_b_kind,
            self.process_token.value,
        )


@dataclass(frozen=True, slots=True)
class ExperimentLawResult:
    outcome_class: ExperimentOutcomeClass
    delta: ExperimentDeltaKind
    product_id: str
    harm_band: ExperimentHarmBand
    public_technique_token: str
    matched: bool


def _failure() -> ExperimentLawResult:
    return ExperimentLawResult(
        outcome_class=ExperimentOutcomeClass.FAILURE,
        delta=ExperimentDeltaKind.NONE,
        product_id="",
        harm_band=ExperimentHarmBand.NONE,
        public_technique_token="",
        matched=False,
    )


def live_operand_token(entity: object) -> str | None:
    """Prefix token for a live operand, or None when the type does not match."""
    if type(entity) is Item:
        return f"item:{entity.kind.value}"
    if type(entity) is Resource:
        return f"resource:{entity.kind.value}"
    if type(entity) is ToolMark:
        return f"tool:{entity.role.value}"
    return None


class ExperimentLawCatalog:
    """First-match law table. Unlisted pairs resolve to failure."""

    def __init__(
        self,
        laws: Sequence[ExperimentLaw],
        production_catalog: ProductionCatalog,
    ) -> None:
        if not laws:
            raise _fail("bounded_experimentation_laws_empty")
        known = {recipe.recipe_id.value for recipe in production_catalog.recipes}
        seen: set[tuple[str, str, str, str]] = set()
        rows: list[ExperimentLaw] = []
        for law in laws:
            if type(law) is not ExperimentLaw:
                raise _fail("experiment_law_invalid")
            if law.delta in _EMIT and law.product_id not in known:
                raise _fail("experiment_law_unknown_product")
            if law.match_key in seen:
                raise _fail("experiment_law_duplicate")
            seen.add(law.match_key)
            rows.append(law)
        self._laws = tuple(rows)
        _LOG.debug(
            "experiment_law_catalog_built law_count=%s",
            len(self._laws),
        )

    def evaluate(
        self,
        *,
        operator: ExperimentOperator,
        operand_a: object,
        operand_b: object | None,
        process_token: ExperimentProcessToken,
    ) -> ExperimentLawResult:
        token_a = live_operand_token(operand_a)
        if operand_b is None:
            token_b = (
                "none" if operator is ExperimentOperator.VARY_PROCESS else None
            )
        else:
            token_b = live_operand_token(operand_b)
        if token_a is None or token_b is None:
            _LOG.debug(
                "experiment_law_unlisted operator=%s outcome_class=%s",
                operator.value,
                ExperimentOutcomeClass.FAILURE.value,
            )
            return _failure()
        key = (operator.value, token_a, token_b, process_token.value)
        for law in self._laws:
            if law.match_key == key:
                _LOG.debug(
                    "experiment_law_matched operator=%s outcome_class=%s",
                    operator.value,
                    law.outcome_class.value,
                )
                return ExperimentLawResult(
                    outcome_class=law.outcome_class,
                    delta=law.delta,
                    product_id=law.product_id,
                    harm_band=law.harm_band,
                    public_technique_token=law.public_technique_token,
                    matched=True,
                )
        _LOG.debug(
            "experiment_law_unlisted operator=%s outcome_class=%s",
            operator.value,
            ExperimentOutcomeClass.FAILURE.value,
        )
        return _failure()
