import QtQuick
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "game_profiles"
    maxWidth: 1080

    property string assignProfileId: ""
    property string assignProfileName: ""
    property var assignOptions: []

    function openAssignments(profileId, name) {
        assignProfileId = profileId
        assignProfileName = name
        assignOptions = GameProfiles.instanceOptions(profileId)
        assignmentModal.open()
    }

    function setAssignment(instanceId, enabled) {
        GameProfiles.setInstanceEnabled(assignProfileId, instanceId, enabled)
        assignOptions = GameProfiles.instanceOptions(assignProfileId)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingLg
        enabled: !Game.isRunning

        PageDescription {
            text: GameProfiles.count > 0
                  ? I18n.format("gameProfiles.subtitle.count", {count: GameProfiles.count})
                  : I18n.t("gameProfiles.subtitle.none")
            maxTextWidth: 760
        }

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            SecondaryButton {
                text: I18n.t("gameProfiles.refresh")
                icon: "refresh-cw"
                onClicked: GameProfiles.refresh()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 66
            radius: Dimensions.radiusMd
            color: Theme.bg2
            border.width: 1
            border.color: Theme.border

            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 12

                Icon {
                    name: "file-text"
                    size: 22
                    tint: Theme.accent
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: I18n.t("gameProfiles.centralTitle")
                        color: Theme.text
                        font.pixelSize: Typography.body
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }
                    Text {
                        text: I18n.format("gameProfiles.directory", {path: GameProfiles.directory})
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                }

                Text {
                    visible: Game.isRunning
                    text: I18n.t("gameProfiles.runningHint")
                    color: Theme.warning
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                }
            }
        }

        AppScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
                contentHeight: profileColumn.implicitHeight
            clip: true

            ColumnLayout {
                id: profileColumn
                width: parent.width
                spacing: 8

                Repeater {
                    model: GameProfiles.model

                    Rectangle {
                        required property string profileId
                        required property string filename
                        required property string name
                        required property bool globalEnabled
                        required property int assignedCount
                        required property int sourceCount

                        Layout.fillWidth: true
                        implicitHeight: 94
                        radius: Dimensions.radiusMd
                        color: hover.hovered ? Theme.bg3 : Theme.bg2
                        border.width: 1
                        border.color: hover.hovered ? Theme.borderHover : Theme.border

                        Behavior on color { ColorAnimation { duration: Theme.fast } }

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 12

                            Rectangle {
                                width: 38
                                height: 38
                                radius: 10
                                color: globalEnabled ? Theme.accentSoft : Theme.bg3
                                border.width: 1
                                border.color: globalEnabled
                                    ? Theme.rgba(Theme.accent, 0.35) : Theme.border
                                Layout.alignment: Qt.AlignVCenter

                                Icon {
                                    anchors.centerIn: parent
                                    name: "file-text"
                                    size: 18
                                    tint: globalEnabled ? Theme.accent : Theme.textSecondary
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    Text {
                                        text: name
                                        color: Theme.text
                                        font.pixelSize: Typography.body + 1
                                        font.weight: Font.DemiBold
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Rectangle {
                                        visible: globalEnabled
                                        width: globalText.implicitWidth + 16
                                        height: 20
                                        radius: 10
                                        color: Theme.accentSoft
                                        Text {
                                            id: globalText
                                            anchors.centerIn: parent
                                            text: I18n.t("gameProfiles.globalBadge")
                                            color: Theme.accent
                                            font.pixelSize: Typography.micro
                                            font.weight: Font.Bold
                                            font.family: Theme.fontFamily
                                        }
                                    }
                                }

                                Text {
                                    text: filename
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: sourceCount > 0
                                          ? I18n.format("gameProfiles.sourceAssignments", {sources: sourceCount, assigned: assignedCount})
                                          : I18n.format("gameProfiles.assigned", {assigned: assignedCount})
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                }
                            }

                            ColumnLayout {
                                spacing: 4
                                Layout.alignment: Qt.AlignVCenter

                                Text {
                                    text: I18n.t("gameProfiles.globalLabel")
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.micro
                                    font.family: Theme.fontFamily
                                    horizontalAlignment: Text.AlignHCenter
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                ToggleSwitch {
                                    checked: globalEnabled
                                    onToggled: (c) => GameProfiles.setGlobalEnabled(profileId, c)
                                    Layout.alignment: Qt.AlignHCenter
                                }
                            }

                            SecondaryButton {
                                text: assignedCount > 0 ? I18n.format("gameProfiles.assignCount", {count: assignedCount}) : I18n.t("gameProfiles.assign")
                                icon: "layers"
                                compact: true
                                onClicked: page.openAssignments(profileId, name)
                            }

                            IconButton {
                                icon: "trash"
                                tooltip: I18n.t("gameProfiles.deleteTooltip")
                                buttonSize: 34
                                iconSize: 15
                                danger: true
                                onClicked: {
                                    deleteModal.profileId = profileId
                                    deleteModal.profileName = name
                                    deleteModal.ask(
                                        I18n.t("gameProfiles.deleteTitle"),
                                        I18n.format("gameProfiles.deleteMessage", {name: name}),
                                        I18n.t("gameProfiles.deleteConfirm"), true)
                                }
                            }
                        }

                        HoverHandler { id: hover }
                    }
                }

                EmptyState {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 320
                    visible: GameProfiles.count === 0
                    icon: "file-text"
                    tint: Theme.textMuted
                    title: I18n.t("gameProfiles.empty.title")
                    subtitle: I18n.t("gameProfiles.empty.subtitle")
                }

                Item { Layout.preferredHeight: 16 }
            }
        }
    }

    Modal {
        id: assignmentModal
        cardWidth: 620
        title: I18n.t("gameProfiles.assignTitle")
        iconName: "layers"

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                Layout.fillWidth: true
                text: I18n.format("gameProfiles.assignProfile", {name: page.assignProfileName})
                color: Theme.text
                font.pixelSize: Typography.body + 1
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
            }
            Text {
                Layout.fillWidth: true
                text: I18n.t("gameProfiles.assignMessage")
                color: Theme.textSecondary
                font.pixelSize: Typography.small
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }

            AppScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(360, assignmentColumn.implicitHeight + 6)
                contentHeight: assignmentColumn.implicitHeight
                clip: true

                ColumnLayout {
                    id: assignmentColumn
                    width: parent.width
                    spacing: 6

                    Repeater {
                        model: page.assignOptions
                        delegate: Rectangle {
                            required property var modelData
                            Layout.fillWidth: true
                            height: 50
                            radius: 8
                            color: modelData.enabled ? Theme.bg3 : Theme.bg2
                            border.width: 1
                            border.color: modelData.enabled ? Theme.rgba(Theme.accent, 0.32) : Theme.border

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 12
                                anchors.rightMargin: 12
                                spacing: 10
                                Icon { name: "layers"; size: 16; tint: modelData.enabled ? Theme.accent : Theme.textMuted }
                                Text {
                                    text: modelData.name
                                    color: Theme.text
                                    font.pixelSize: Typography.small + 0.5
                                    font.family: Theme.fontFamily
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                                Text {
                                    visible: modelData.global === true
                                    text: I18n.t("gameProfiles.assignmentGlobal")
                                    color: Theme.accent
                                    font.pixelSize: Typography.micro
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }
                                Text {
                                    visible: modelData.supported !== true
                                    text: I18n.t("gameProfiles.requiresV3")
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.micro
                                    font.family: Theme.fontFamily
                                }
                                ToggleSwitch {
                                    checked: modelData.enabled
                                    enabled: modelData.supported === true
                                    onToggled: (c) => page.setAssignment(modelData.instanceId, c)
                                }
                            }
                        }
                    }

                    Text {
                        visible: page.assignOptions.length === 0
                        text: I18n.t("gameProfiles.noInstances")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        footer: [
            PrimaryButton {
                text: I18n.t("gameProfiles.done")
                icon: "check"
                onClicked: assignmentModal.close()
            }
        ]
    }

    ConfirmModal {
        id: deleteModal
        property string profileId: ""
        property string profileName: ""
        onConfirmed: GameProfiles.removeProfile(profileId)
    }
}
