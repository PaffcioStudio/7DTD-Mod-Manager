import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Mod list card. Pure visual component - drag & drop is handled by the
// delegate wrapper in ModsPage.
Item {
    id: card

    signal detailsClicked()
    signal toggleRequested(bool enabled)
    signal uninstallRequested()
    signal openFolderRequested()

    property string modId: ""
    property string name: ""
    property string version: ""
    property string gameVersion: ""   // wersja gry wg katalogu (slug; "" = nieznana)
    property string newVersion: ""
    property string author: ""
    property string description: ""
    property string category: "Gameplay"
    property bool modEnabled: false
    property bool hasUpdate: false
    property bool inConflict: false
    property string updatedAgo: ""
    property var tags: []
    property bool dragging: false
    property bool dragHandleVisible: false
    property string thumbUrl: ""

    readonly property color catColor: Theme.catColor(category)

    // status priority: conflict > update > enabled/disabled
    readonly property string statusKey: inConflict ? "conflict"
        : hasUpdate ? "update"
        : modEnabled ? "enabled" : "disabled"

    scale: dragging ? 1.02 : 1.0
    Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

    SoftShadow {
        source: bgRect
        elevation: card.dragging ? 3 : (hover.hovered ? 1.6 : 0.8)
        Behavior on elevation { NumberAnimation { duration: Theme.normal } }
    }

    Rectangle {
        id: bgRect
        anchors.fill: parent
        radius: Dimensions.radiusMd + 2

        color: card.dragging ? Theme.bg3 : (hover.hovered ? Theme.bg3 : Theme.bg2)
        border.width: 1
        border.color: card.inConflict ? Theme.rgba(Theme.warning, 0.38)
                     : card.dragging ? Theme.rgba(card.catColor, 0.5)
                     : (hover.hovered ? Theme.borderHover : Theme.border)

        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 14
        anchors.topMargin: 12
        anchors.bottomMargin: 12
        spacing: 14

        // drag grip
        Icon {
            name: "grip-vertical"
            size: 15
            tint: Theme.textFaint
            visible: card.dragHandleVisible
            Layout.alignment: Qt.AlignVCenter
        }

        // icon tile (miniatura z 7daystodiemods.com albo placeholder)
        Item {
            Layout.alignment: Qt.AlignVCenter
            implicitWidth: 56
            implicitHeight: 56

            Rectangle {
                anchors.fill: parent
                radius: 13
                color: Theme.rgba(card.catColor, 0.13)
                border.width: 1
                border.color: Theme.rgba(card.catColor, 0.3)
            }

            Image {
                visible: card.thumbUrl !== ""
                anchors.fill: parent
                anchors.margins: 1
                source: card.thumbUrl
                asynchronous: true
                fillMode: Image.PreserveAspectCrop
            }

            // rama maskująca kwadratowe narożniki miniatury
            Rectangle {
                visible: card.thumbUrl !== ""
                anchors.fill: parent
                radius: 13
                color: "transparent"
                border.width: 2
                border.color: Theme.bg2
            }

            Icon {
                visible: card.thumbUrl === ""
                anchors.centerIn: parent
                name: Theme.catIcon(card.category)
                tint: card.catColor
                size: 25
            }
        }

        // info column
        ColumnLayout {
            Layout.fillWidth: true
            Layout.alignment: Qt.AlignVCenter
            spacing: 3

            RowLayout {
                spacing: 9
                Layout.fillWidth: true

                Text {
                    text: card.name
                    color: card.modEnabled ? Theme.text : Theme.textMuted
                    font.pixelSize: Typography.h3 + 1
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                // version chip
                Rectangle {
                    visible: card.version !== ""
                    width: versionText.implicitWidth + 14
                    height: 19
                    radius: 6
                    color: Theme.bg3
                    border.width: 1
                    border.color: Theme.border

                    Text {
                        id: versionText
                        anchors.centerIn: parent
                        text: "v" + card.version
                        color: Theme.textSecondary
                        font.pixelSize: Typography.micro + 0.5
                        font.weight: Font.Medium
                        font.family: Theme.fontFamily
                    }
                }

                // update chip
                Rectangle {
                    visible: card.hasUpdate
                    width: updateRow.implicitWidth + 14
                    height: 19
                    radius: 6
                    color: Theme.accentSoft
                    border.width: 1
                    border.color: Theme.rgba(Theme.accent, 0.35)

                    Row {
                        id: updateRow
                        anchors.centerIn: parent
                        spacing: 4

                        Icon { name: "arrow-up"; size: 10; tint: Theme.accent; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: card.newVersion
                            color: Theme.accent
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // conflict chip
                Rectangle {
                    visible: card.inConflict
                    width: conflictRow.implicitWidth + 14
                    height: 19
                    radius: 6
                    color: Theme.warningSoft
                    border.width: 1
                    border.color: Theme.rgba(Theme.warning, 0.35)

                    Row {
                        id: conflictRow
                        anchors.centerIn: parent
                        spacing: 4

                        Icon { name: "shield-alert"; size: 10; tint: Theme.warning; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: I18n.t("mod.card.conflict")
                            color: Theme.warning
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }

            Text {
                Layout.fillWidth: true
                text: I18n.format("mod.card.meta", {
                    author: card.author,
                    updatedAgo: card.updatedAgo,
                    category: Theme.catLabel(card.category),
                    gameSuffix: card.gameVersion !== "" ? "  ·  " + I18n.format("mod.card.gameSuffix", {gameVersion: card.gameVersion.toUpperCase()}) : ""
                })
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
                elide: Text.ElideMiddle
            }

            Text {
                Layout.fillWidth: true
                visible: card.description !== ""
                text: card.description
                color: Theme.textSecondary
                font.pixelSize: Typography.small
                font.family: Theme.fontFamily
                elide: Text.ElideRight
                maximumLineCount: 1
            }

            Row {
                spacing: 6
                Layout.topMargin: 2
                visible: card.tags.length > 0

                Repeater {
                    model: Math.min(card.tags.length, 3)

                    Rectangle {
                        required property int index
                        width: tagText.implicitWidth + 12
                        height: 18
                        radius: 5
                        color: "transparent"
                        border.width: 1
                        border.color: Theme.border

                        Text {
                            id: tagText
                            anchors.centerIn: parent
                            text: card.tags[index]
                            color: Theme.textMuted
                            font.pixelSize: Typography.micro
                            font.family: Theme.fontFamily
                        }
                    }
                }
            }
        }

        // right column: status + actions
        ColumnLayout {
            Layout.alignment: Qt.AlignVCenter
            spacing: 10

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8

                StatusBadge { key: card.statusKey }

                IconButton {
                    icon: "more-horizontal"
                    tooltip: I18n.t("mod.card.more")
                    buttonSize: 28
                    iconSize: 15
                    onClicked: contextMenu.open()

                    Menu {
                        id: contextMenu
                        y: parent.height + 6
                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                        padding: 6

                        background: Rectangle {
                            implicitWidth: 210
                            implicitHeight: 36
                            radius: 11
                            color: Theme.bg2
                            border.color: Theme.borderHover
                        }

                        MenuItem {
                            text: I18n.t("mod.card.openFolder")
                            height: 34
                            onTriggered: card.openFolderRequested()
                            background: Rectangle { radius: 8; color: parent.highlighted ? Theme.bg3 : "transparent" }
                            contentItem: Row {
                                spacing: 9
                                leftPadding: 10
                                Icon { name: "folder"; size: 15; tint: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: I18n.t("mod.card.openFolder"); color: Theme.textSecondary; font.pixelSize: Typography.small + 0.5; font.family: Theme.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            }
                        }

                        MenuItem {
                            height: 34
                            onTriggered: {
                                if (card.hasUpdate) Bus.toast(I18n.format("mod.card.updateQueued", {name: card.name}), "info")
                                else Bus.toast(I18n.format("mod.card.current", {name: card.name}), "info")
                            }
                            background: Rectangle { radius: 8; color: parent.highlighted ? Theme.bg3 : "transparent" }
                            contentItem: Row {
                                spacing: 9
                                leftPadding: 10
                                Icon { name: "refresh-cw"; size: 15; tint: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: I18n.t("mod.card.checkUpdates"); color: Theme.textSecondary; font.pixelSize: Typography.small + 0.5; font.family: Theme.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            }
                        }

                        MenuItem {
                            height: 34
                            onTriggered: App.copyToClipboard(card.version)
                            background: Rectangle { radius: 8; color: parent.highlighted ? Theme.bg3 : "transparent" }
                            contentItem: Row {
                                spacing: 9
                                leftPadding: 10
                                Icon { name: "copy"; size: 15; tint: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: I18n.t("mod.card.copyVersion"); color: Theme.textSecondary; font.pixelSize: Typography.small + 0.5; font.family: Theme.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            }
                        }

                        MenuItem {
                            height: 34
                            onTriggered: App.searchModOnline(card.name)
                            background: Rectangle { radius: 8; color: parent.highlighted ? Theme.bg3 : "transparent" }
                            contentItem: Row {
                                spacing: 9
                                leftPadding: 10
                                Icon { name: "search"; size: 15; tint: Theme.textSecondary; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: I18n.t("mod.card.searchOnline"); color: Theme.textSecondary; font.pixelSize: Typography.small + 0.5; font.family: Theme.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            }
                        }

                        MenuSeparator {
                            width: parent.width - 12
                            height: 9
                            contentItem: Rectangle {
                                implicitWidth: parent.width - 12
                                implicitHeight: 1
                                color: Theme.border
                            }
                        }

                        MenuItem {
                            height: 34
                            enabled: !Game.isRunning
                            onTriggered: card.uninstallRequested()
                            background: Rectangle { radius: 8; color: parent.highlighted ? Theme.rgba(Theme.danger, 0.12) : "transparent" }
                            contentItem: Row {
                                spacing: 9
                                leftPadding: 10
                                Icon { name: "trash"; size: 15; tint: Theme.danger; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: I18n.t("mod.card.uninstall"); color: Theme.danger; font.pixelSize: Typography.small + 0.5; font.family: Theme.fontFamily; anchors.verticalCenter: parent.verticalCenter }
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.alignment: Qt.AlignRight
                spacing: 8

                SecondaryButton {
                    text: I18n.t("mod.card.details")
                    compact: true
                    onClicked: card.detailsClicked()
                }

                ToggleSwitch {
                    checked: card.modEnabled
                    enabled: !Game.isRunning
                    onToggled: (checked) => card.toggleRequested(checked)
                }
            }
        }
    }

    HoverHandler { id: hover }
}
