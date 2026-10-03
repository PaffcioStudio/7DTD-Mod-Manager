import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Drawer szczegółów overhaula z LOKALNEGO manifestu (katalog Lokalne).
// Użycie:  LocalModDrawer { id: localDrawer }   /   localDrawer.openWith(item)
// Otwierany kliknięciem karty na Odkrywaj (provider "local") - pokazuje PEŁNY
// opis, którego karta ucina elizją, oraz pobieranie z manifestowego źródła.
Item {
    id: drawer

    property bool opened: false
    property var entry: ({})

    readonly property string title: entry.title || ""
    readonly property string url: entry.url || ""
    readonly property string gameVersion: entry.game_version || entry.versions || ""
    readonly property var stateKey: Downloads.modDownloads[url] || ""
    readonly property bool downloading: ["queued", "downloading", "paused"].indexOf(stateKey) >= 0

    function openWith(item) {
        entry = item || ({})
        opened = true
        drawer.forceActiveFocus()
    }

    function close() {
        opened = false
    }

    parent: Overlay.overlay
    anchors.fill: parent
    z: 400
    visible: scrim.opacity > 0.001
    enabled: opened

    Keys.onEscapePressed: close()

    // ---- scrim --------------------------------------------------------- #
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Theme.rgba(Theme.bg0, 0.55)
        opacity: drawer.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }
        MouseArea {
            anchors.fill: parent
            onClicked: drawer.close()
        }
    }

    // ---- card ----------------------------------------------------------- #
    Rectangle {
        id: panel
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.min(640, parent.width - 60)
        color: Theme.bg1
        border.width: 1
        border.color: Theme.border
        x: drawer.opened ? parent.width - width : parent.width
        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

        // panel konsumuje kliknięcia - nic nie przelatuje do scrima/UI pod spodem
        MouseArea {
            anchors.fill: parent
            onClicked: { /* klik w panel - ignorowany */ }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // header
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 18
                spacing: 12

                ColumnLayout {
                    spacing: 3
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: drawer.title
                        color: Theme.text
                        font.pixelSize: Typography.h2
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: {
                            const parts = []
                            if (drawer.entry.author) parts.push(I18n.resolveMessage(drawer.entry.author))
                            if (drawer.entry.version) parts.push("v" + drawer.entry.version)
                            parts.push(I18n.t("discover.local.overhaul"))
                            if (drawer.entry.versions) parts.push(drawer.entry.versions)
                            return parts.join(" · ")
                        }
                        color: Theme.textMuted
                        font.pixelSize: Typography.small
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                }

                IconButton {
                    icon: "external-link"
                    tooltip: I18n.t("discover.drawer.openSource")
                    visible: drawer.url !== ""
                    onClicked: Qt.openUrlExternally(drawer.url)
                }
                IconButton {
                    icon: "x"
                    tooltip: I18n.t("discover.drawer.close")
                    onClicked: drawer.close()
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

            // body
            AppScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentHeight: drawerBody.implicitHeight

                ColumnLayout {
                    id: drawerBody
                    width: Math.max(0, parent.width - 36)
                    x: 18
                    spacing: 18

                    // ---- miniatura -------------------------------------- #
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.topMargin: 18
                        implicitHeight: 240
                        radius: 10
                        color: Theme.bg2
                        border.width: 1
                        border.color: Theme.border
                        clip: true
                        visible: drawer.entry.thumbnail !== undefined && drawer.entry.thumbnail !== ""

                        Image {
                            anchors.fill: parent
                            anchors.margins: 1
                            source: drawer.entry.thumbnail || ""
                            asynchronous: true
                            fillMode: Image.PreserveAspectFit
                            sourceSize.width: 1200
                        }
                    }

                    // ---- opis (PEŁNY) ----------------------------------- #
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        Text {
                            text: I18n.t("discover.drawer.description")
                            color: Theme.textMuted
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.letterSpacing: Typography.trackingCaps
                            font.family: Theme.fontFamily
                        }

                        Text {
                            Layout.fillWidth: true
                            text: ((I18n.language === "en" && drawer.entry.summaryEn)
                                   ? drawer.entry.summaryEn : drawer.entry.summary)
                                  || I18n.t("discover.local.noDescription")
                            textFormat: Text.PlainText
                            color: Theme.textSecondary
                            font.pixelSize: Typography.small
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                    }

                    // ---- pobieranie -------------------------------------- #
                    PrimaryButton {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.bottomMargin: 24
                        text: drawer.downloading ? I18n.t("discover.download.queued") : I18n.t("discover.local.downloadOverhaul")
                        icon: drawer.downloading ? "clock" : "download"
                        disabled: drawer.downloading || drawer.url === ""
                        onClicked: Downloads.startUrlDownloadNamed(
                            drawer.url, drawer.title, drawer.gameVersion)
                    }

                    Item { Layout.fillHeight: true; Layout.minimumHeight: 20 }
                }
            }
        }
    }
}
