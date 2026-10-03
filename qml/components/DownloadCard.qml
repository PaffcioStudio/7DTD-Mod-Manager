import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Download entry card with progress, speed and controls.
Item {
    id: root

    signal pauseRequested()
    signal resumeRequested()
    signal cancelRequested()
    signal retryRequested()

    property string title: ""
    property string subtitle: ""
    property real progress: 0            // 0..1
    property string totalText: ""
    property string downloadedText: ""
    property string speedText: ""
    property string etaText: ""
    property int etaSeconds: 0
    property string statusKey: "downloading"
    property string statusText: ""
    readonly property string displayStatusText: I18n.t("status." + root.statusKey) !== ("status." + root.statusKey)
        ? I18n.t("status." + root.statusKey) : I18n.resolveMessage(root.statusText)
    property string kind: "download"   // "game" uses a gamepad icon in the status tile
    property bool pausable: true        // git clone cannot be suspended (cancel/retry only)

    readonly property color statusColor: Theme.statusColor(statusKey)
    readonly property bool busy: statusKey === "downloading" || statusKey === "queued"
    readonly property bool completed: statusKey === "completed"
    // rozmiar nieznany (totalText puste) + trwa pobieranie = tryb nieokreślony
    readonly property bool indeterminate: root.totalText === "" && root.busy

    implicitHeight: 96

    Rectangle {
        anchors.fill: parent
        radius: Dimensions.radiusMd + 2
        color: hover.hovered ? Theme.bg3 : Theme.bg2
        border.width: 1
        border.color: hover.hovered ? Theme.borderHover : Theme.border

        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: 16
        anchors.rightMargin: 14
        spacing: 14

        // status icon tile
        Item {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 44
            implicitHeight: 44

            Rectangle {
                anchors.fill: parent
                radius: 12
                color: Theme.rgba(root.statusColor, 0.12)
                border.width: 1
                border.color: Theme.rgba(root.statusColor, 0.3)
            }

            Icon {
                anchors.centerIn: parent
                name: root.completed ? "check"
                     : root.statusKey === "failed" ? "x"
                     : root.statusKey === "paused" ? "pause"
                     : root.kind === "game" ? "gamepad"
                     : "download"
                tint: root.statusColor
                size: 19
            }
        }

        // main column
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 7

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text {
                    text: root.title
                    color: Theme.text
                    font.pixelSize: Typography.h3
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    visible: !root.indeterminate
                    text: Math.round(root.progress * 100) + "%"
                    color: root.statusColor
                    font.pixelSize: Typography.small
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                }
            }

            SlimProgress {
                Layout.fillWidth: true
                value: root.progress
                barColor: root.statusColor
                barHeight: 6
                indeterminate: root.indeterminate
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: I18n.resolveMessage(root.subtitle)
                    color: Theme.textMuted
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Text {
                    text: root.downloadedText
                    color: Theme.textSecondary
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                }

                Text {
                    // Rezerwujemy stałą szerokość, dzięki czemu przejściowy
                    // brak próbki prędkości nie przestawia całego wiersza.
                    visible: root.busy
                    text: root.speedText === "" || root.speedText === "-" ? "-" : root.speedText
                    Layout.preferredWidth: 78
                    horizontalAlignment: Text.AlignRight
                    color: Theme.textSecondary
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                }

                Text {
                    visible: root.busy
                    text: root.etaSeconds > 0
                        ? (root.etaSeconds < 60
                            ? I18n.format("downloads.eta.seconds", {seconds: root.etaSeconds})
                            : I18n.format("downloads.eta.minutes", {minutes: Math.floor(root.etaSeconds / 60), seconds: root.etaSeconds % 60}))
                        : "-"
                    Layout.preferredWidth: 92
                    horizontalAlignment: Text.AlignRight
                    color: Theme.textMuted
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                }
            }
        }

        // controls
        Row {
            spacing: 4
            Layout.alignment: Qt.AlignVCenter

            IconButton {
                icon: "pause"
                tooltip: root.pausable ? I18n.t("downloads.control.pause") : I18n.t("downloads.control.pauseUnavailable")
                visible: root.pausable && root.statusKey === "downloading"
                onClicked: root.pauseRequested()
            }

            IconButton {
                icon: "play"
                tooltip: I18n.t("downloads.control.resume")
                visible: root.statusKey === "paused"
                onClicked: root.resumeRequested()
            }

            IconButton {
                icon: "rotate-ccw"
                tooltip: I18n.t("downloads.control.retry")
                visible: root.statusKey === "failed"
                onClicked: root.retryRequested()
            }

            IconButton {
                icon: "x-circle"
                tooltip: I18n.t("downloads.control.cancel")
                visible: root.statusKey === "downloading" || root.statusKey === "paused" || root.statusKey === "queued"
                onClicked: root.cancelRequested()
            }

            IconButton {
                icon: "check-circle"
                tooltip: I18n.t("downloads.control.completed")
                visible: root.completed
                tint: Theme.success
                hoverTint: Theme.success
            }
        }
    }

    HoverHandler { id: hover }
}
