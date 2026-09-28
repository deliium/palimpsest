"""Pinned observer Web export contract. Does not download or launch the editor."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / "clients" / "godot-observer" / "export" / "pins.env"
PRESET = ROOT / "clients" / "godot-observer" / "export_presets.cfg"
PROJECT = ROOT / "clients" / "godot-observer" / "project.godot"
EXPORT_SCRIPT = ROOT / "scripts" / "export-observer-web.sh"

LINUX_ZIP_SHA512 = (
    "9aa00f7a605200940bce3027a567b782f49bd8e940dd06ae9e987bd65aee1b14"
    "67edd56ed84fcdcbdd44354bf613bdbb4e5d2913e925850368e150c59ed54c65"
)
TEMPLATES_SHA512 = (
    "ca4d71c4d7b81dfc15d1a98baa07534aa95b03fdda78a0075b06672e1648d2e5"
    "f40980c9adc28d23e1b92e732ee7bf3461997aa804af74ec2fcd7a93ccb84079"
)
LINUX_URL = (
    "https://github.com/godotengine/godot/releases/download/"
    "4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip"
)
TEMPLATES_URL = (
    "https://github.com/godotengine/godot/releases/download/"
    "4.7.2-stable/Godot_v4.7.2-stable_export_templates.tpz"
)


def _pin_map() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in PINS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def test_export_pins_match_the_official_4_7_2_release() -> None:
    pins = _pin_map()
    assert pins["GODOT_VERSION"] == "4.7.2-stable"
    assert pins["GODOT_LINUX_URL"] == LINUX_URL
    assert pins["GODOT_LINUX_SHA512"] == LINUX_ZIP_SHA512
    assert pins["GODOT_TEMPLATES_URL"] == TEMPLATES_URL
    assert pins["GODOT_TEMPLATES_SHA512"] == TEMPLATES_SHA512
    for url in (pins["GODOT_LINUX_URL"], pins["GODOT_TEMPLATES_URL"]):
        assert "latest" not in url
        assert url.endswith((".zip", ".tpz"))


def test_committed_web_preset_disables_threads() -> None:
    preset = PRESET.read_text(encoding="utf-8")
    project = PROJECT.read_text(encoding="utf-8")
    assert 'name="Web"' in preset
    assert 'platform="Web"' in preset
    assert "variant/thread_support=false" in preset
    assert 'renderer/rendering_method="gl_compatibility"' in project
    assert 'config/features=PackedStringArray("4.7", "GL Compatibility")' in project
    assert list((ROOT / "clients" / "godot-observer").rglob("*.csproj")) == []
    assert "[dotnet]" not in project
    assert "[csharp]" not in project


def test_export_script_is_not_the_user_launcher() -> None:
    script = EXPORT_SCRIPT.read_text(encoding="utf-8")
    assert "observer_export_download_ok file=" in script
    assert "observer_export_version_ok version=" in script
    assert "observer_export_started preset=Web" in script
    assert "observer_export_finished file_count=" in script
    assert "observer_export_failed reason_code=" in script
    assert '--export-release "Web"' in script
    assert "4.7.2.stable" in script
    assert "latest_url_forbidden" in script
