"""Composition root for matrix experiment CLI (no HTTP / no api imports)."""

from research_runner.composition import resolve_code_revision, resolve_package_version

__all__ = [
    "resolve_code_revision",
    "resolve_package_version",
]
