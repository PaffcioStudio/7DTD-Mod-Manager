import re
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_profiles_page_defines_every_modal_it_asks():
    source = (ROOT / "qml" / "pages" / "ProfilesPage.qml").read_text(encoding="utf-8")
    used = set(re.findall(r"\b(\w+Modal)\.ask\(", source))
    defined = set(re.findall(r"\bid:\s*(\w+)", source))
    assert "stopGameModal" in used
    assert used <= defined, f"niezdefiniowane modale: {used - defined}"


def test_stop_game_modal_stops_the_running_game():
    source = (ROOT / "qml" / "pages" / "ProfilesPage.qml").read_text(encoding="utf-8")
    block = source[source.index("id: stopGameModal"):]
    block = block[:block.index("}")]
    assert "Game.stopRunningGame()" in block
