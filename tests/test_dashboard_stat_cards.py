from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _text():
    return (PROJECT_ROOT / "qml/components/StatCard.qml").read_text(encoding="utf-8")


def test_stat_card_has_room_for_number_and_label():
    text = _text()
    assert "implicitHeight: 144 * Dimensions.scale" in text
    assert "anchors.bottomMargin: 16" in text
    assert "Layout.preferredHeight: Math.ceil(Typography.statBig * 1.18)" in text
    assert "Layout.fillHeight: true" in text


def test_stat_card_number_and_label_are_not_pushed_into_card_edge():
    text = _text()
    assert "Item { Layout.fillHeight: true; Layout.minimumHeight: 1 }" in text
    assert "Layout.preferredHeight: Math.ceil(Typography.caption * 1.35)" in text
