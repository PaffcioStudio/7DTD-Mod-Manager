import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Update entry card for the Updates page.
Item {
    id: root

    signal updateRequested()

    property string name: ""
    property string version: ""
    property string newVersion: ""
    property string updatedAgo: ""
    property string sizeText: ""
    property var downloadState: null     // null | {progress, statusKey}

    readonly property bool inFlight: downloadState !== null && downloadState.statusKey !== "completed"
    readonly property bool isDownloading: downloadState !== null && downloadState.statusKey === "downloading"
    readonly property bool isDone: downloadState !== null && downloadState.statusKey === "completed"

    implicitHeight: 86

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
        spacing: 14

        // icon tile
        Item {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 44
            implicitHeight: 44

            Rectangle {
                anchors.fill: parent
                radius: 12
                color: Theme.accentSoft
                border.width: 1
                border.color: Theme.rgba(Theme.accent, 0.3)
            }

            Icon {
                id: updateIcon
                anchors.centerIn: parent
                name: "refresh-cw"
                tint: Theme.accent
                size: 19
            }

            RotationAnimation {
                target: updateIcon
                running: root.isDownloading && Theme.animationsEnabled
                loops: Animation.Infinite
                from: 0
                to: 360
                duration: 1400
            }
        }

        // info
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 5

            RowLayout {
                spacing: 9
                Layout.fillWidth: true

                Text {
                    text: root.name
                    color: Theme.text
                    font.pixelSize: Typography.h3 + 1
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // version transition
                Rectangle {
                    width: versionRow.implicitWidth + 16
                    height: 22
                    radius: 7
                    color: Theme.bg3
                    border.width: 1
                    border.color: Theme.border

                    Row {
                        id: versionRow
                        anchors.centerIn: parent
                        spacing: 6

                        Text {
                            text: root.version
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Icon { name: "arrow-right"; size: 11; tint: Theme.accent; anchors.verticalCenter: parent.verticalCenter }

                        Text {
                            text: root.newVersion
                            color: Theme.accent
                            font.pixelSize: Typography.caption
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }

            Text {
                text: root.inFlight
                     ? (root.isDownloading ? I18n.format("updates.card.downloading", {progress: Math.round(root.downloadState.progress)}) : I18n.t("updates.card.queued"))
                     : I18n.format("updates.card.released", {updatedAgo: root.updatedAgo, sizeText: root.sizeText})
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            SlimProgress {
                Layout.fillWidth: true
                visible: root.inFlight
                value: root.downloadState ? root.downloadState.progress / 100 : 0
                barHeight: 4
            }
        }

        // action
        Item {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: updateButton.implicitWidth
            implicitHeight: updateButton.implicitHeight

            SecondaryButton {
                id: updateButton
                text: root.isDone ? I18n.t("updates.card.done") : I18n.t("updates.card.update")
                icon: root.isDone ? "check" : "download"
                compact: false
                disabled: root.inFlight || root.isDone
                onClicked: root.updateRequested()
            }
        }
    }

    HoverHandler { id: hover }
}
