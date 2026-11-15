"""Deterministic purpose-bound paging for social-mobility rows."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Final

__all__ = [
    "SOCIAL_MOBILITY_PAGE_DEFAULT",
    "SOCIAL_MOBILITY_PAGE_MAX",
    "SOCIAL_MOBILITY_PURPOSE_DOMAINS",
    "page_social_mobility",
]

SOCIAL_MOBILITY_PAGE_DEFAULT: Final[int] = 100
SOCIAL_MOBILITY_PAGE_MAX: Final[int] = 500

_LOG: Final[logging.Logger] = logging.getLogger("simulation.social_mobility_paging")

SOCIAL_MOBILITY_PURPOSE_DOMAINS: Final[dict[str, frozenset[str]]] = {
    "summary": frozenset(),
    "domains": frozenset(
        {
            "resources",
            "skills",
            "social_influence",
            "organization_roles",
            "educational_access",
            "productive_assets",
        }
    ),
    "economy": frozenset({"resources", "productive_assets"}),
    "human_capital": frozenset({"skills", "educational_access"}),
    "standing": frozenset({"social_influence", "organization_roles"}),
    "generations": frozenset(),
    "coverage": frozenset(),
}


def _domain_key(row: Any) -> str:
    return f"{row.window_index:03d}|{row.domain}"


def _generation_key(row: Any) -> str:
    return f"{row.window_index:03d}|g{row.generation_index:03d}"


def _lag_key(row: Any) -> str:
    return f"{row.window_index:03d}|l{row.generation_lag:03d}"


def _coverage_key(row: Any) -> str:
    return f"{row.window_index:03d}|coverage"


def page_social_mobility(
    *,
    domains: Sequence[Any] = (),
    generations: Sequence[Any] = (),
    lags: Sequence[Any] = (),
    coverage: Sequence[Any] = (),
    purpose: str,
    limit: int = SOCIAL_MOBILITY_PAGE_DEFAULT,
    after_key: str = "",
    window_index: int | None = None,
) -> tuple[tuple[object, ...], str]:
    """Filter, sort, and cut one deterministic page; return the next key."""

    if purpose not in SOCIAL_MOBILITY_PURPOSE_DOMAINS:
        raise ValueError("social_mobility_page_invalid")
    if (
        isinstance(limit, bool)
        or type(limit) is not int
        or not 1 <= limit <= SOCIAL_MOBILITY_PAGE_MAX
    ):
        raise ValueError("social_mobility_page_invalid")
    if window_index is not None and (
        isinstance(window_index, bool)
        or type(window_index) is not int
        or not 0 <= window_index <= 511
    ):
        raise ValueError("social_mobility_page_invalid")

    keyed: list[tuple[str, object]] = []
    if purpose in {"domains", "economy", "human_capital", "standing"}:
        allowed = SOCIAL_MOBILITY_PURPOSE_DOMAINS[purpose]
        keyed = [
            (_domain_key(row), row)
            for row in domains
            if getattr(row, "domain", None) in allowed
            and (window_index is None or row.window_index == window_index)
        ]
    elif purpose == "generations":
        keyed = [
            (_generation_key(row), row)
            for row in generations
            if window_index is None or row.window_index == window_index
        ] + [
            (_lag_key(row), row)
            for row in lags
            if window_index is None or row.window_index == window_index
        ]
    elif purpose == "coverage":
        keyed = [
            (_coverage_key(row), row)
            for row in coverage
            if window_index is None or row.window_index == window_index
        ]
    else:
        return (), ""

    keyed.sort(key=lambda item: item[0])
    keys = [key for key, _ in keyed]
    if after_key:
        if after_key not in keys:
            raise ValueError("social_mobility_page_invalid")
        keyed = [item for item in keyed if item[0] > after_key]
        keys = [key for key, _ in keyed]
    page = tuple(row for _, row in keyed[:limit])
    next_key = "" if len(keyed) <= limit else keys[limit - 1]
    _LOG.debug(
        "social_mobility_page purpose=%s window=%s rows=%d next=%s",
        purpose,
        "-" if window_index is None else window_index,
        len(page),
        bool(next_key),
    )
    return page, next_key
