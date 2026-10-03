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
    assert text.startswith("# 7DTD Mod Manager")
    assert "## 1.0." not in text
    assert "changelog" not in text.lower()
    assert "build.sh --install" in text
    assert "Pillow" in text


def test_screenshot_script_recreates_missing_output_directory():
    text = (ROOT / "tests" / "screenshot_en.py").read_text(encoding="utf-8")
    assert 'out_dir = ROOT / "docs" / "screenshots"' in text
    assert 'out_dir.mkdir(parents=True, exist_ok=True)' in text
