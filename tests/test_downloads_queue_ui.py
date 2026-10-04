from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS_PAGE = (ROOT / "qml/pages/DownloadsPage.qml").read_text(encoding="utf-8")
DOWNLOAD_CARD = (ROOT / "qml/components/DownloadCard.qml").read_text(encoding="utf-8")

def test_download_delegate_uses_model_status_roles():
    assert 'required property string statusKey' in DOWNLOADS_PAGE
    assert 'required property string statusText' in DOWNLOADS_PAGE
    assert 'property string statusKey: "downloading"' not in DOWNLOADS_PAGE

def test_completed_card_can_remove_single_history_entry():
    assert 'signal completedRequested()' in DOWNLOAD_CARD
    assert 'onClicked: root.completedRequested()' in DOWNLOAD_CARD
    assert 'onCompletedRequested: Downloads.removeCompletedAt(downloadDelegate.downloadId)' in DOWNLOADS_PAGE
    assert 'onCompletedRequested: Downloads.removeCompletedAt(completedDelegate.downloadId)' in DOWNLOADS_PAGE

def test_download_stats_have_separate_adaptive_columns():
    assert 'Layout.preferredWidth: 443' in DOWNLOAD_CARD
    assert 'Layout.minimumWidth: 330' in DOWNLOAD_CARD
    assert 'Layout.preferredWidth: 140' in DOWNLOAD_CARD
    assert 'Layout.preferredWidth: 100' in DOWNLOAD_CARD
    assert 'Layout.preferredWidth: 167' in DOWNLOAD_CARD
    assert 'Layout.minimumWidth: 0' in DOWNLOAD_CARD
    assert 'text: root.downloadedText' in DOWNLOAD_CARD
    assert 'text: root.speedText === "" || root.speedText === "-" ? "-" : root.speedText' in DOWNLOAD_CARD
    assert 'I18n.format("downloads.eta.minutes"' in DOWNLOAD_CARD


def test_long_statistics_are_elided_inside_their_own_columns():
    # Long localized values must be clipped/elided instead of overlapping
    # neighboring statistics such as speed or ETA.
    assert DOWNLOAD_CARD.count('elide: Text.ElideRight') >= 4
    assert DOWNLOAD_CARD.count('clip: true') >= 4
