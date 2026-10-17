import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from backend.web_mod_details import _gallery_urls  # noqa: E402


def _qml(name: str) -> str:
    return (ROOT / "qml" / "components" / name).read_text(encoding="utf-8")


def test_gallery_dedupes_and_keeps_order():
    meta = {"gallery": ["https://a/1.png", "https://a/2.png", "https://a/1.png", "", None]}
    assert _gallery_urls(meta) == ["https://a/1.png", "https://a/2.png"]


def test_gallery_is_capped_and_http_only():
    meta = {"gallery": [f"https://a/{i}.png" for i in range(40)] + ["file:///etc/passwd", "data:x"]}
    urls = _gallery_urls(meta)
    assert len(urls) == 20
    assert all(u.startswith("https://") for u in urls)


def test_gallery_falls_back_to_thumbnail_then_description_images():
    assert _gallery_urls({"gallery": [], "thumbnail": "https://a/t.png"}) == ["https://a/t.png"]
    assert _gallery_urls({"thumbnail": None, "description_images": ["https://a/d.png"]}) == ["https://a/d.png"]
    assert _gallery_urls({}) == []


def test_drawer_shows_gallery_above_files_and_opens_fullscreen_viewer():
    text = _qml("WebModDrawer.qml")
    assert text.index("ScreenshotGallery {") < text.index("discover.drawer.filesTitle")
    assert "ImageViewer {" in text
    assert "onFullscreenRequested" in text
    assert "viewer.opened" in text  # Esc zamyka najpierw podgląd, potem drawer


def test_gallery_has_arrows_on_both_sides_and_click_to_fullscreen():
    text = _qml("ScreenshotGallery.qml")
    assert "anchors.left: parent.left" in text and "anchors.right: parent.right" in text
    assert "direction: -1" in text and "direction: 1" in text
    assert "fullscreenRequested(gallery.currentIndex)" in text


def test_viewer_supports_keyboard_and_closes_on_backdrop():
    text = _qml("ImageViewer.qml")
    assert "Keys.onLeftPressed" in text and "Keys.onRightPressed" in text
    assert "Keys.onEscapePressed" in text
    assert "onClicked: viewer.close()" in text
