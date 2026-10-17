import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backend import app_updates as au  # noqa: E402

BODY = (
    "If you run into any problems, open an issue.\n\n"
    "## 1.0.45\n- Five\n\n## 1.0.44\n- Four\n\n## 1.0.43\n- Three\n\n## 1.0.42\n- Two\n"
)


def test_parse_version_accepts_plain_prefixed_and_text():
    assert au.parse_version("1.0.44") == (1, 0, 44)
    assert au.parse_version("v1.0.44") == (1, 0, 44)
    assert au.parse_version("Release 2.1") == (2, 1)
    assert au.parse_version("release") is None
    assert au.parse_version("") is None


def test_is_newer_compares_numerically_not_lexically():
    assert au.is_newer("1.0.44", "1.0.43")
    assert au.is_newer("1.0.100", "1.0.99")
    assert au.is_newer("1.1", "1.0.9")
    assert not au.is_newer("1.0.43", "1.0.43")
    assert not au.is_newer("1.0.43.0", "1.0.43")
    assert not au.is_newer("1.0.42", "1.0.43")
    assert not au.is_newer("garbage", "1.0.43")


def test_notes_since_keeps_only_versions_newer_than_installed():
    notes = au.notes_since(BODY, "1.0.43")
    assert "Five" in notes and "Four" in notes
    assert "Three" not in notes and "Two" not in notes
    assert "open an issue" not in notes


def test_notes_since_falls_back_to_latest_section_or_whole_body():
    only_latest = au.notes_since(BODY, "1.0.45")
    assert "Five" in only_latest and "Four" not in only_latest
    assert au.notes_since("Just text without headings", "1.0.1") == "Just text without headings"


def test_parse_release_uses_title_as_version_and_html_url():
    payload = {"name": "1.0.44", "body": BODY, "html_url": "https://github.com/x/y/releases/tag/release"}
    info = au.parse_release(payload, "1.0.43")
    assert info["version"] == "1.0.44"
    assert info["newer"] is True
    assert info["url"] == "https://github.com/x/y/releases/tag/release"
    assert au.parse_release(payload, "1.0.44")["newer"] is False


def test_parse_release_rejects_missing_version_and_unsafe_url():
    assert au.parse_release({"name": "release", "body": ""}) is None
    assert au.parse_release("nope") is None
    info = au.parse_release({"name": "9.9.9", "html_url": "javascript:alert(1)"}, "1.0.0")
    assert info["url"] == au.RELEASE_PAGE


def test_endpoint_points_at_fixed_release_tag():
    assert au.API_URL.endswith("/repos/PaffcioStudio/7DTD-Mod-Manager/releases/tags/release")


def test_app_update_check_is_enabled_by_default_and_wired_to_ui():
    settings = (ROOT / "src/services/settings_service.py").read_text(encoding="utf-8")
    assert '"autoCheckAppUpdates": True' in settings
    assert "def autoCheckAppUpdates" in settings
    page = (ROOT / "qml/pages/SettingsPage.qml").read_text(encoding="utf-8")
    assert "Settings.autoCheckAppUpdates" in page and "AppUpdates.checkNow()" in page
    main = (ROOT / "qml/Main.qml").read_text(encoding="utf-8")
    assert "onUpdateAvailable" in main and "AppUpdateModal" in main
    modal = (ROOT / "qml/components/AppUpdateModal.qml").read_text(encoding="utf-8")
    assert "App.openUrl(root.url)" in modal and "root.close()" in modal
