"""Wire filesystem stores and version identity without importing api."""

from __future__ import annotations

import importlib.metadata
import logging
import os
from pathlib import Path
from typing import Final

from experiments.matrix_manifest import FilesystemMatrixManifestStore
from experiments.matrix_runner import MatrixBatchDependencies

_LOG: Final[logging.Logger] = logging.getLogger("research_runner.composition")

CODE_REVISION_ENV: Final[str] = "PALIMPSEST_CODE_REVISION"


def resolve_package_version() -> str:
    """Resolve installed package version via importlib.metadata (never api)."""
    try:
        version = importlib.metadata.version("palimpsest")
    except importlib.metadata.PackageNotFoundError:
        version = "0.0.0+local"
        _LOG.warning(
            "package_version_fallback",
            extra={"experiment": {"package_version": version}},
        )
    _LOG.debug(
        "package_version_resolved",
        extra={"experiment": {"package_version": version}},
    )
    return version


def resolve_code_revision(*, injected: str | None = None) -> str:
    """Optional code revision from inject or env; empty allowed; never invent."""
    if injected is not None:
        revision = injected
    else:
        revision = os.environ.get(CODE_REVISION_ENV, "")
    if type(revision) is not str:
        raise TypeError("code_revision must be str")
    _LOG.debug(
        "code_revision_resolved",
        extra={"experiment": {"code_revision_present": bool(revision)}},
    )
    return revision


def build_batch_dependencies(
    *,
    code_revision: str | None = None,
) -> MatrixBatchDependencies:
    return MatrixBatchDependencies(
        package_version=resolve_package_version(),
        code_revision=resolve_code_revision(injected=code_revision),
    )


def build_manifest_store(root: Path | str) -> FilesystemMatrixManifestStore:
    return FilesystemMatrixManifestStore(root)


__all__ = [
    "CODE_REVISION_ENV",
    "build_batch_dependencies",
    "build_manifest_store",
    "resolve_code_revision",
    "resolve_package_version",
]
