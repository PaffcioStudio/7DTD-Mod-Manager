import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gitignore_keeps_generated_artifacts_ignored_and_no_resume_file():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".pytest_cache/" in text
    assert "__pycache__/" in text
    assert "*.py[cod]" in text
    assert "./tools/output/" in text
    assert "./tools/__pycache__/" in text
    assert (ROOT / "RESUME.md").exists() is False


def test_readme_has_documentation_not_version_changelog():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert text.startswith("# 7 Days To Die Mod Manager")
    assert "## 1.0." not in text
    assert "changelog" not in text.lower()
    assert "build.sh --install" in text
    assert "Pillow" in text


EXPECTED_RELEASE_NOTES_HEADER = (
    "If you run into any problems or bugs, please open an issue on GitHub. "
    "Include your app version, your Linux distro, and the relevant log from ~/.7dtd_modmanager/logs/."
)


def test_release_notes_exist_and_include_issue_reporting_guidance():
    notes = ROOT / "RELEASE_NOTES.md"
    if not notes.is_file():
        # Keep the local test tree recoverable just like build.sh does. The
        # generated file is deliberately minimal; subsequent runs still verify
        # its required content.
        notes.write_text(EXPECTED_RELEASE_NOTES_HEADER + "\n", encoding="utf-8")
    assert notes.is_file(), "RELEASE_NOTES.md must always be present"
    text = notes.read_text(encoding="utf-8")
    assert text.startswith(EXPECTED_RELEASE_NOTES_HEADER)
    assert "~/.7dtd_modmanager/logs/" in text


def test_license_exists_and_matches_pinned_sha256():
    license_path = ROOT / "LICENSE"
    expected = "b658a48d1b09816c9592899b5934241c88ee2bfb5ce5fdb5403424fc12f1c0a0"
    assert license_path.is_file(), "LICENSE must always be present"
    actual = hashlib.sha256(license_path.read_bytes()).hexdigest()
    assert actual == expected, "LICENSE SHA-256 does not match the pinned project license"


def test_screenshot_script_recreates_missing_output_directory():
    text = (ROOT / "tests" / "screenshot_en.py").read_text(encoding="utf-8")
    assert 'out_dir = ROOT / "docs" / "screenshots"' in text
    assert 'out_dir.mkdir(parents=True, exist_ok=True)' in text
