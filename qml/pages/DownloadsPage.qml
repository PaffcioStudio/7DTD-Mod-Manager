import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "downloads"
    maxWidth: 1080

    // ------------------------------------------------------------------ #
    // URL download (migration stage 5)
    // ------------------------------------------------------------------ #
    function startUrl() {
        const value = urlField.text.trim()
        if (value.length === 0)
            return
        Downloads.startUrlDownload(value)
        urlField.text = ""
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingXl

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            SecondaryButton {
                text: I18n.t("downloads.clearCompleted")
                icon: "x"
                visible: Downloads.completedCount > 0
                onClicked: Downloads.clearCompleted()
            }
        }

        // ---- URL download (migration stage 5) -------------------------- #
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            AppTextField {
                id: urlField
                Layout.fillWidth: true
                placeholder: I18n.t("downloads.url.placeholder")
                onAccepted: page.startUrl()
            }

            PrimaryButton {
                text: I18n.t("downloads.url.action")
                icon: "download"
                onClicked: page.startUrl()
            }
        }

        // ---- active downloads ----------------------------------------- #
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: Downloads.activeCount > 0

            Text {
                text: I18n.t("downloads.active")
                color: Theme.textMuted
                font.pixelSize: Typography.micro + 0.5
                font.weight: Font.DemiBold
                font.letterSpacing: Typography.trackingCaps
                font.family: Theme.fontFamily
                Layout.leftMargin: 4
            }

            Repeater {
                model: Downloads.model

                Item {
                    id: downloadDelegate
                    required property string downloadId
                    required property string title
                    required property string subtitle
                    required property real progress
                    required property string totalText
                    required property string downloadedText
                    required property string speedText
                    required property string etaText
                    required property int etaSeconds
                    property string statusKey: "downloading"
                    property string statusText: ""
                    required property string kind
                    required property bool pausable

                    visible: downloadDelegate.statusKey !== "completed"
                    Layout.fillWidth: true
                    implicitHeight: 96

                    DownloadCard {
                        anchors.fill: parent
                        visible: downloadDelegate.visible
                        title: downloadDelegate.title
                        subtitle: downloadDelegate.subtitle
                        progress: downloadDelegate.progress
                        totalText: downloadDelegate.totalText
                        downloadedText: downloadDelegate.downloadedText
                        speedText: downloadDelegate.speedText
                        etaText: downloadDelegate.etaText
                        etaSeconds: downloadDelegate.etaSeconds
                        statusKey: downloadDelegate.statusKey
                        statusText: downloadDelegate.statusText
                        kind: downloadDelegate.kind
                        pausable: downloadDelegate.pausable

                        onPauseRequested: Downloads.pauseAt(downloadDelegate.downloadId)
                        onResumeRequested: Downloads.resumeAt(downloadDelegate.downloadId)
                        onCancelRequested: Downloads.cancelAt(downloadDelegate.downloadId)
                        onRetryRequested: Downloads.retryAt(downloadDelegate.downloadId)
                    }
                }
            }
        }

        // ---- completed ---------------------------------------------------- #
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10
            visible: Downloads.completedCount > 0

            Text {
                text: I18n.t("downloads.completed")
                color: Theme.textMuted
                font.pixelSize: Typography.micro + 0.5
                font.weight: Font.DemiBold
                font.letterSpacing: Typography.trackingCaps
                font.family: Theme.fontFamily
                Layout.leftMargin: 4
            }

            Repeater {
                model: Downloads.model

                Item {
                    id: completedDelegate
                    required property string downloadId
                    required property string title
                    required property string subtitle
                    required property real progress
                    required property string totalText
                    required property string downloadedText
                    required property string speedText
                    required property string etaText
                    required property int etaSeconds
                    required property string statusKey
                    required property string statusText
                    required property string kind

                    visible: completedDelegate.statusKey === "completed"
                    Layout.fillWidth: true
                    implicitHeight: 96

                    DownloadCard {
                        anchors.fill: parent
                        visible: completedDelegate.visible
                        title: completedDelegate.title
                        subtitle: I18n.t("downloads.completed.subtitle")
                        progress: 1.0
                        totalText: completedDelegate.totalText
                        downloadedText: completedDelegate.totalText
                        speedText: "-"
                        etaText: ""
                        statusKey: "completed"
                        statusText: I18n.t("downloads.completed.status")
                        kind: completedDelegate.kind
                    }
                }
            }
        }

        // ---- empty state ---------------------------------------------------- #
        Item {
            id: emptyWrap
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 340
            clip: true
            visible: Downloads.activeCount === 0 && Downloads.completedCount === 0


            EmptyState {
                id: emptyState
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 48
                width: parent.width
                icon: "download"
                tint: Theme.textMuted
                title: I18n.t("downloads.empty.title")
                subtitle: I18n.t("downloads.empty.subtitle")
                actionText: I18n.t("downloads.empty.action")
                onActionTriggered: Bus.goTo("updates")
            }
        }

        Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }
    }
}
