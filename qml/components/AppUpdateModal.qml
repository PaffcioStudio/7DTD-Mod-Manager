import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Informacja o nowym wydaniu programu (GitHub Releases).
// Użycie:  AppUpdateModal { id: m }  /  m.show(version, notes, url)
// "Pobierz" otwiera stronę wydania w przeglądarce, "Anuluj" nic nie robi.
Modal {
    id: root

    cardWidth: 560
    title: I18n.t("appUpdate.title")
    iconName: "download"

    property string version: ""
    property string notes: ""
    property string url: ""

    function show(newVersion, releaseNotes, releaseUrl) {
        version = newVersion
        notes = releaseNotes
        url = releaseUrl
        open()
    }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: 12

        Text {
            Layout.fillWidth: true
            text: I18n.format("appUpdate.message", {version: root.version, current: App.version})
            color: Theme.text
            font.pixelSize: Typography.body
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }

        Text {
            visible: root.notes !== ""
            text: I18n.t("appUpdate.notes")
            color: Theme.textMuted
            font.pixelSize: Typography.micro + 0.5
            font.weight: Font.DemiBold
            font.letterSpacing: Typography.trackingCaps
            font.family: Theme.fontFamily
        }

        // notatki wydania - przewijane, żeby długi changelog nie rozpychał okna
        Rectangle {
            visible: root.notes !== ""
            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(300, notesBody.implicitHeight + 24)
            radius: 10
            color: Theme.bg0
            border.width: 1
            border.color: Theme.border
            clip: true

            AppScrollView {
                anchors.fill: parent
                anchors.margins: 1
                contentHeight: notesBody.implicitHeight + 24

                Text {
                    id: notesBody
                    x: 12
                    y: 12
                    width: Math.max(0, parent.width - 24 - 14)
                    text: root.notes
                    textFormat: Text.MarkdownText
                    color: Theme.textSecondary
                    font.pixelSize: Typography.small
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                    onLinkActivated: (link) => App.openUrl(link)
                }
            }
        }
    }

    footer: [
        SecondaryButton {
            text: I18n.t("common.confirm.cancel")
            onClicked: root.close()
        },
        PrimaryButton {
            text: I18n.t("appUpdate.download")
            icon: "external-link"
            onClicked: {
                App.openUrl(root.url)
                root.close()
            }
        }
    ]
}
