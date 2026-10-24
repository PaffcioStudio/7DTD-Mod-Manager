from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_script_supports_install_short_and_long_flags():
    text = (PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")
    assert "--install|-i" in text
    assert "INSTALL_DEB=true" in text
    assert 'if [ "$INSTALL_DEB" = true ]; then' in text
    assert "read -r -p" in text


def test_build_script_payload_is_an_allowlist_without_dev_scripts():
    text = (PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")
    # only runtime files are included, everything else is excluded by default
    for entry in ("/run.sh", "/LICENSE", "/README.md", "/src/***", "/qml/***", "/assets/***"):
        assert f"--include '{entry}'" in text
    assert "--exclude '*' \\" in text
    # the old "copy everything except ..." approach must not come back
    assert "--exclude '*.md' \\" not in text
    # dev/private scripts are never named as payload
    for private in ("git-setup.sh", "git-push.sh", "git-release.sh", "venv.sh", "test.sh"):
        assert f"--include '/{private}'" not in text


def test_build_script_keeps_prompt_when_no_install_flag():
    text = (PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")
    assert "Instalacja pominięta" in text
