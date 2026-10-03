from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_split_tool_exists_and_is_executable():
    tool = ROOT / "tools" / "split.py"
    assert tool.is_file()
    assert tool.stat().st_mode & 0o111


def test_requirements_contains_pillow():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    assert any(line.strip().lower() == "pillow" for line in requirements)


def test_gitignore_contains_split_tool_artifacts():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "./tools/output/" in gitignore
    assert "./tools/__pycache__/" in gitignore
