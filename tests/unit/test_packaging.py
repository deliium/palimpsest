"""Packaging, lock, and installed-wheel discovery checks."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _tool_palimpsest() -> dict[str, object]:
    pyproject = _pyproject()
    tool = pyproject["tool"]
    assert isinstance(tool, dict)
    palimpsest = tool["palimpsest"]
    assert isinstance(palimpsest, dict)
    return palimpsest


def _configured_packages() -> list[str]:
    packages = _tool_palimpsest()["packages"]
    assert isinstance(packages, list)
    return [str(name) for name in packages]


def test_reference_python_version_is_pinned() -> None:
    pyproject = _pyproject()
    pinned = _tool_palimpsest()["python_version"]
    version_file = (ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert version_file == pinned == "3.12.14"
    requires_python = pyproject["project"]
    assert isinstance(requires_python, dict)
    assert requires_python["requires-python"] == ">=3.12"


def test_application_log_level_setting_is_exclusive() -> None:
    assert _tool_palimpsest()["log_level_env"] == "PALIMPSEST_LOG_LEVEL"


def test_lockfile_exists_for_frozen_installs() -> None:
    lockfile = ROOT / "uv.lock"
    assert lockfile.is_file(), "uv.lock must be committed for locked installs"


def test_wheel_contains_only_project_packages_and_imports_outside_repo(
    tmp_path: Path,
) -> None:
    expected = set(_configured_packages())
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(dist_dir)],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, found {wheels}"

    with zipfile.ZipFile(wheels[0]) as archive:
        top_level = {
            Path(name).parts[0]
            for name in archive.namelist()
            if name and not name.startswith("palimpsest-")
        }
    extra = top_level - expected
    missing = expected - top_level
    assert not missing, f"wheel is missing project packages: {sorted(missing)}"
    assert not extra, (
        f"wheel contains colliding or unexpected packages: {sorted(extra)}"
    )

    venv_dir = tmp_path / "venv"
    subprocess.run(
        ["uv", "venv", "--python", "3.12.14", str(venv_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    python = venv_dir / "bin" / "python"
    subprocess.run(
        ["uv", "pip", "install", str(wheels[0]), "--python", str(python)],
        check=True,
        capture_output=True,
        text=True,
    )

    outside = tmp_path / "outside"
    outside.mkdir()
    import_script = (
        "import simulation; "
        "from simulation import ("
        "encode_domain, decode_domain, DomainSerializationError); "
        "assert callable(encode_domain); assert callable(decode_domain); "
        "assert DomainSerializationError is not None; "
        + "; ".join(f"import {name}" for name in sorted(expected))
    )
    completed = subprocess.run(
        [str(python), "-c", import_script],
        check=True,
        cwd=outside,
        capture_output=True,
        text=True,
        env={
            **dict(_without_repo_pythonpath()),
            "PATH": str(venv_dir / "bin"),
            "VIRTUAL_ENV": str(venv_dir),
        },
    )
    assert completed.returncode == 0


def _without_repo_pythonpath() -> dict[str, str]:
    env = dict(os.environ)
    pythonpath = env.get("PYTHONPATH", "")
    if not pythonpath:
        env.pop("PYTHONPATH", None)
        return env
    filtered = [
        entry
        for entry in pythonpath.split(":")
        if entry
        and Path(entry).resolve() != ROOT / "src"
        and Path(entry).resolve() != ROOT
    ]
    if filtered:
        env["PYTHONPATH"] = ":".join(filtered)
    else:
        env.pop("PYTHONPATH", None)
    return env


def test_editable_environment_uses_locked_python() -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; print(sys.version)"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith("3.12.14")
