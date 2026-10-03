from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_build_script_supports_install_short_and_long_flags():
    text = (PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")
    assert "--install|-i" in text
    assert "INSTALL_DEB=true" in text
    assert 'if [ "$INSTALL_DEB" = true ]; then' in text
    assert "read -r -p" in text


def test_build_script_keeps_prompt_when_no_install_flag():
    text = (PROJECT_ROOT / "build.sh").read_text(encoding="utf-8")
    assert "Instalacja pominięta" in text
