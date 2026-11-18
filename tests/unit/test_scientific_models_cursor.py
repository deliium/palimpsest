# mypy: ignore-errors

"""Dual-gate plumbing: settings, cursor binding, publication pinning, routes."""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import pytest
from pydantic import SecretStr, ValidationError

from api.errors import ApiError
from api.routes import scientific_models as route_module
from api.scientific_models_cursor import (
    SCIENTIFIC_MODELS_CURSOR_TTL_SECONDS,
    ScientificModelsCursorCodec,
    ScientificModelsCursorError,
)
from infrastructure.settings import Settings
from persistence.scientific_models_filesystem import ScientificModelsStoreError
from tests.unit.test_scientific_models_snapshot import _snapshot

pytestmark = pytest.mark.unit

_RUN = "run-scientific-models"


def _publication(token: str):
    return dataclasses.replace(
        _snapshot(predictions=5), publication_id=token, run_token=_RUN
    )


class _Reader:
    def __init__(self, snapshots) -> None:
        self._snapshots = {row.publication_id: row for row in snapshots}
        self.requested: list[str] = []

    def list_publications(self, run_token: str) -> tuple[str, ...]:
        return tuple(self._snapshots)

    def read_snapshot(self, run_token: str, publication_id: str):
        self.requested.append(publication_id)
        snapshot = self._snapshots.get(publication_id)
        if snapshot is None:
            raise ScientificModelsStoreError(
                "scientific_models_store_publication_missing"
            )
        return snapshot


def _request(reader, codec):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                scientific_models_reader=reader,
                scientific_models_cursor_codec=codec,
            )
        )
    )


def test_cursor_alias_is_domain_separated() -> None:
    codec = ScientificModelsCursorCodec.from_secret(b"k" * 32)
    token = codec.encode(
        purpose="scientific-models:predictions",
        run_id=_RUN,
        publication_id="a" * 32,
        snapshot_digest="d" * 64,
        query_fingerprint="f" * 20,
        after_key="2",
    )
    with pytest.raises(ScientificModelsCursorError):
        codec.decode(token, purpose="diplomacy:relations")
    assert SCIENTIFIC_MODELS_CURSOR_TTL_SECONDS == 900


def test_settings_require_a_paired_root_and_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("PALIMPSEST_SCIENTIFIC_MODELS_ROOT", raising=False)
    monkeypatch.delenv("PALIMPSEST_SCIENTIFIC_MODELS_CURSOR_KEY", raising=False)
    assert Settings().scientific_models_root is None
    with pytest.raises(ValidationError, match="set together"):
        Settings(scientific_models_root=tmp_path)
    with pytest.raises(ValidationError, match="set together"):
        Settings(scientific_models_cursor_key=SecretStr("k" * 32))
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(
            scientific_models_root=tmp_path,
            scientific_models_cursor_key=SecretStr("short"),
        )
    configured = Settings(
        scientific_models_root=tmp_path,
        scientific_models_cursor_key=SecretStr("k" * 32),
    )
    assert configured.scientific_models_root == tmp_path


def test_routes_are_eight_get_only_paths() -> None:
    routes = route_module.router.routes
    assert len(routes) == route_module.SCIENTIFIC_MODELS_ROUTE_COUNT == 8
    for route in routes:
        assert route.methods == {"GET"}
        assert "/scientific-models" in route.path


def test_paging_pins_the_cursor_publication(monkeypatch) -> None:
    monkeypatch.setattr(route_module, "_authorize", lambda request: None)
    reader = _Reader((_publication("a" * 32), _publication("b" * 32)))
    codec = ScientificModelsCursorCodec.from_secret(b"k" * 32)
    first = route_module._page(
        _request(reader, codec),
        _RUN,
        section="predictions",
        publication_id=None,
        cursor=None,
        limit=2,
    )
    assert first["publication_id"] == "b" * 32
    assert first["next_cursor"] is not None
    second = route_module._page(
        _request(reader, codec),
        _RUN,
        section="predictions",
        publication_id=None,
        cursor=first["next_cursor"],
        limit=2,
    )
    assert second["publication_id"] == "b" * 32
    assert reader.requested == ["b" * 32, "b" * 32]


def test_cursor_rejects_filter_or_selector_drift(monkeypatch) -> None:
    monkeypatch.setattr(route_module, "_authorize", lambda request: None)
    reader = _Reader((_publication("a" * 32), _publication("b" * 32)))
    codec = ScientificModelsCursorCodec.from_secret(b"k" * 32)
    first = route_module._page(
        _request(reader, codec),
        _RUN,
        section="predictions",
        publication_id="a" * 32,
        cursor=None,
        limit=2,
    )
    with pytest.raises(ApiError) as conflict:
        route_module._page(
            _request(reader, codec),
            _RUN,
            section="predictions",
            publication_id="b" * 32,
            cursor=first["next_cursor"],
            limit=2,
        )
    assert conflict.value.code == "scientific_models_cursor_invalid"
    with pytest.raises(ApiError):
        route_module._page(
            _request(reader, codec),
            _RUN,
            section="predictions",
            publication_id="a" * 32,
            cursor=first["next_cursor"],
            limit=3,
        )


def test_missing_publication_maps_to_not_found(monkeypatch) -> None:
    monkeypatch.setattr(route_module, "_authorize", lambda request: None)
    reader = _Reader((_publication("a" * 32),))
    codec = ScientificModelsCursorCodec.from_secret(b"k" * 32)
    with pytest.raises(ApiError) as missing:
        route_module._page(
            _request(reader, codec),
            _RUN,
            section="outcomes",
            publication_id="f" * 32,
            cursor=None,
            limit=10,
        )
    assert missing.value.code == "scientific_models_publication_not_found"
