"""Immutable, quota-bounded filesystem store for predictive snapshots."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from simulation.scientific_models_codec import (
    ScientificModelsError,
    decode_scientific_models_snapshot,
    scientific_models_snapshot_bytes,
    scientific_models_snapshot_digest,
)
from simulation.scientific_models_models import ScientificModelsSnapshot
from simulation.scientific_models_ports import ScientificModelsStoreReceipt

__all__ = [
    "FilesystemScientificModelsStore",
    "ScientificModelsStoreError",
    "ScientificModelsStoreOptions",
    "scientific_models_store_publisher",
    "scientific_models_store_reader",
]

SCIENTIFIC_MODELS_STORE_VERSION: Final[str] = "scientific-models-store-v1"
_SAFE_COMPONENT: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class ScientificModelsStoreError(ValueError):
    """Closed store failure code; never carries paths or payloads."""

    __slots__ = ("code",)

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> ScientificModelsStoreError:
    return ScientificModelsStoreError(code)


@dataclass(frozen=True, slots=True)
class ScientificModelsStoreOptions:
    enabled: bool = False
    max_publications: int = 16
    max_bytes: int = 8_388_608

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise ValueError("enabled: invalid_type")
        for name in ("max_publications", "max_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or type(value) is not int or value < 1:
                raise ValueError(f"{name}: invalid_positive_int")


def _component(value: object, name: str) -> str:
    if type(value) is not str or _SAFE_COMPONENT.fullmatch(value) is None:
        raise _fail(f"scientific_models_store_invalid_{name}")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")


class FilesystemScientificModelsStore:
    """Atomic publication store. Readers never create, repair or delete files."""

    def __init__(self, root: Path, *, options: ScientificModelsStoreOptions) -> None:
        if not isinstance(root, Path):
            raise TypeError("root must be Path")
        if type(options) is not ScientificModelsStoreOptions:
            raise TypeError("options must be ScientificModelsStoreOptions")
        self._root = root
        self._options = options

    def _run_dir(self, run_token: str) -> Path:
        return self._root / _component(run_token, "run")

    @contextlib.contextmanager
    def _lock(self, run_dir: Path) -> Iterator[None]:
        import fcntl

        lock_path = run_dir / ".lock"
        handle = open(lock_path, "a+b")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()

    @staticmethod
    def _manifest_path(run_dir: Path) -> Path:
        return run_dir / "state.json"

    def _read_manifest(self, run_dir: Path) -> dict[str, Any]:
        path = self._manifest_path(run_dir)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _fail("scientific_models_store_corrupt") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"version", "publications"}
            or payload["version"] != SCIENTIFIC_MODELS_STORE_VERSION
            or not isinstance(payload["publications"], list)
        ):
            raise _fail("scientific_models_store_corrupt")
        seen: set[str] = set()
        for row in payload["publications"]:
            if (
                not isinstance(row, dict)
                or set(row)
                != {
                    "publication_id",
                    "file",
                    "digest",
                    "byte_size",
                    "finalized_through_tick",
                }
                or _SAFE_COMPONENT.fullmatch(str(row["publication_id"])) is None
                or _SAFE_COMPONENT.fullmatch(str(row["file"])) is None
                or row["publication_id"] in seen
            ):
                raise _fail("scientific_models_store_corrupt")
            if (
                type(row["byte_size"]) is not int
                or row["byte_size"] < 0
                or type(row["finalized_through_tick"]) is not int
            ):
                raise _fail("scientific_models_store_corrupt")
            seen.add(row["publication_id"])
        return payload

    @staticmethod
    def _atomic_write(path: Path, material: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        with open(temporary, "wb") as handle:
            handle.write(material)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)

    def publish(
        self, snapshot: ScientificModelsSnapshot
    ) -> ScientificModelsStoreReceipt:
        if type(snapshot) is not ScientificModelsSnapshot:
            raise TypeError("snapshot must be ScientificModelsSnapshot")
        publication_id = _component(snapshot.publication_id, "publication")
        if not self._options.enabled:
            return ScientificModelsStoreReceipt(
                publication_id=publication_id,
                stored=False,
                byte_size=0,
                reason="disabled",
            )
        try:
            material = scientific_models_snapshot_bytes(snapshot)
        except ScientificModelsError as exc:
            return ScientificModelsStoreReceipt(
                publication_id=publication_id,
                stored=False,
                byte_size=0,
                reason=exc.code,
            )
        digest = scientific_models_snapshot_digest(snapshot)
        byte_size = len(material)
        run_dir = self._run_dir(snapshot.run_token)
        run_dir.mkdir(parents=True, exist_ok=True)
        with self._lock(run_dir):
            manifest_path = self._manifest_path(run_dir)
            manifest = (
                self._read_manifest(run_dir)
                if manifest_path.exists()
                else {"version": SCIENTIFIC_MODELS_STORE_VERSION, "publications": []}
            )
            rows = list(manifest["publications"])
            existing = next(
                (row for row in rows if row["publication_id"] == publication_id),
                None,
            )
            if existing is not None:
                if existing["digest"] != digest:
                    return ScientificModelsStoreReceipt(
                        publication_id=publication_id,
                        stored=False,
                        byte_size=0,
                        reason="corrupt",
                    )
                return ScientificModelsStoreReceipt(
                    publication_id=publication_id,
                    stored=True,
                    byte_size=int(existing["byte_size"]),
                    reason="published",
                )
            total = sum(int(row["byte_size"]) for row in rows)
            if (
                len(rows) + 1 > self._options.max_publications
                or total + byte_size > self._options.max_bytes
            ):
                return ScientificModelsStoreReceipt(
                    publication_id=publication_id,
                    stored=False,
                    byte_size=byte_size,
                    reason="quota_exceeded",
                )
            file_name = f"{publication_id}.json"
            child = run_dir / file_name
            self._atomic_write(child, material)
            rows.append(
                {
                    "publication_id": publication_id,
                    "file": file_name,
                    "digest": digest,
                    "byte_size": byte_size,
                    "finalized_through_tick": snapshot.finalized_through_tick,
                }
            )
            self._atomic_write(
                manifest_path,
                _canonical(
                    {
                        "version": SCIENTIFIC_MODELS_STORE_VERSION,
                        "publications": rows,
                    }
                ),
            )
        return ScientificModelsStoreReceipt(
            publication_id=publication_id,
            stored=True,
            byte_size=byte_size,
            reason="published",
        )

    def list_publications(self, run_token: str) -> tuple[str, ...]:
        run_dir = self._run_dir(run_token)
        if not run_dir.is_dir():
            raise _fail("scientific_models_store_run_missing")
        manifest = self._read_manifest(run_dir)
        return tuple(row["publication_id"] for row in manifest["publications"])

    def read_snapshot(
        self, run_token: str, publication_id: str
    ) -> ScientificModelsSnapshot:
        run_dir = self._run_dir(run_token)
        publication = _component(publication_id, "publication")
        if not run_dir.is_dir():
            raise _fail("scientific_models_store_run_missing")
        manifest = self._read_manifest(run_dir)
        row = next(
            (
                item
                for item in manifest["publications"]
                if item["publication_id"] == publication
            ),
            None,
        )
        if row is None:
            raise _fail("scientific_models_store_publication_missing")
        child = run_dir / str(row["file"])
        if not child.is_file() or child.is_symlink():
            raise _fail("scientific_models_store_corrupt")
        try:
            material = child.read_bytes()
        except OSError as exc:
            raise _fail("scientific_models_store_corrupt") from exc
        if len(material) != row["byte_size"]:
            raise _fail("scientific_models_store_corrupt")
        if hashlib.sha256(material).hexdigest() != row["digest"]:
            raise _fail("scientific_models_store_corrupt")
        try:
            payload = json.loads(material.decode("utf-8"))
            snapshot = decode_scientific_models_snapshot(payload)
        except (UnicodeDecodeError, json.JSONDecodeError, ScientificModelsError):
            raise _fail("scientific_models_store_corrupt") from None
        if snapshot.run_token != run_token or snapshot.publication_id != publication:
            raise _fail("scientific_models_store_corrupt")
        return snapshot


def scientific_models_store_reader(
    root: Path, *, options: ScientificModelsStoreOptions
) -> FilesystemScientificModelsStore:
    return FilesystemScientificModelsStore(root, options=options)


def scientific_models_store_publisher(
    root: Path, *, options: ScientificModelsStoreOptions
) -> FilesystemScientificModelsStore:
    return FilesystemScientificModelsStore(root, options=options)
