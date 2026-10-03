import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Instance card for the Profiles page (migration stage 6).
Item {
    id: root

    signal launchRequested()
    signal activateRequested()
    signal editRequested()
    signal duplicateRequested()
    signal removeRequested()
    signal buildModsRequested()
    signal openFolderRequested()
    signal favoriteToggled()

    property string profileId: ""
    property string name: ""
    property string description: ""
    property string dataDirDisplay: ""
    property bool isDefault: false
    property string flagsText: ""
    property bool isRunning: false
    property int modCount: 0
    property int enabledCount: 0
    property string createdText: ""
    property bool isActive: false
    property color colorTag: Theme.accent
    property string gameBranch: ""
    property bool favorite: false

    implicitHeight: 214

    // active glow border
    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: Dimensions.radiusLg + 1
        color: "transparent"
        border.width: root.isActive ? 2 : 0
        border.color: Theme.rgba(root.colorTag, 0.55)
        visible: root.isActive
    }

    Rectangle {
        id: bg
        anchors.fill: parent
        radius: Dimensions.radiusLg
        color: root.isActive ? Theme.bg3 : Theme.bg2
        border.width: 1
        border.color: root.isRunning ? Theme.rgba(Theme.success, 0.55)
                     : root.isActive ? Theme.rgba(root.colorTag, 0.35)
                     : (hover.hovered ? Theme.borderHover : Theme.border)

        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    // color ribbon
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 14
        width: 3
        radius: 2
        color: root.isRunning ? Theme.success : root.colorTag
        opacity: 0.85
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: 32
        anchors.rightMargin: 18
        anchors.topMargin: 18
        anchors.bottomMargin: 14
        spacing: 5

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: I18n.resolveMessage(root.name)
                color: Theme.text
                font.pixelSize: Typography.h2
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
                elide: Text.ElideRight
                Layout.fillWidth: true
            }

            IconButton {
                icon: root.favorite ? "star-filled" : "star"
                tint: root.favorite ? Theme.warning : Theme.textMuted
                hoverTint: root.favorite ? Theme.warning : Theme.text
                iconSize: 16
                buttonSize: 30
                tooltip: root.favorite ? I18n.t("instances.profile.favorite.remove") : I18n.t("instances.profile.favorite.add")
                onClicked: root.favoriteToggled()
            }

            // RUNNING pill
            Rectangle {
                visible: root.isRunning
                width: runningRow.implicitWidth + 18
                height: 22
                radius: 11
                color: Theme.rgba(Theme.success, 0.16)
                border.width: 1
                border.color: Theme.rgba(Theme.success, 0.45)

                Row {
                    id: runningRow
                    anchors.centerIn: parent
                    spacing: 5

                    Rectangle { width: 6; height: 6; radius: 3; color: Theme.success; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: I18n.t("instances.profile.running")
                        color: Theme.success
                        font.pixelSize: Typography.micro
                        font.weight: Font.Bold
                        font.letterSpacing: Typography.trackingWide
                        font.family: Theme.fontFamily
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }

            // ACTIVE pill
            Rectangle {
                visible: root.isActive
                width: activeRow.implicitWidth + 18
                height: 22
                radius: 11
                color: Theme.rgba(root.colorTag, 0.16)
                border.width: 1
                border.color: Theme.rgba(root.colorTag, 0.45)

                Row {
                    id: activeRow
                    anchors.centerIn: parent
                    spacing: 5

                    Rectangle { width: 6; height: 6; radius: 3; color: root.colorTag; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        text: I18n.t("instances.profile.active")
                        color: root.colorTag
                        font.pixelSize: Typography.micro
                        font.weight: Font.Bold
                        font.letterSpacing: Typography.trackingWide
                        font.family: Theme.fontFamily
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            text: I18n.resolveMessage(root.description)
            color: Theme.textMuted
            font.pixelSize: Typography.small
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
            elide: Text.ElideRight
            maximumLineCount: 2
        }

        // data dir row
        RowLayout {
            Layout.fillWidth: true
            spacing: 6

            Icon {
                name: "folder"
                size: 12
                tint: Theme.textSecondary
                Layout.alignment: Qt.AlignVCenter
            }

            Text {
                text: I18n.resolveMessage(root.dataDirDisplay)
                color: Theme.textSecondary
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
                elide: Text.ElideMiddle
                Layout.fillWidth: true
            }
        }

        // flags row
        Text {
            visible: root.flagsText !== ""
            Layout.fillWidth: true
            text: root.flagsText
            color: Theme.textMuted
            font.pixelSize: Typography.caption
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        // przypisana wersja gry (pobrana przez DepotDownloader)
        Text {
            visible: root.gameBranch !== ""
            Layout.fillWidth: true
            text: I18n.format("instances.profile.gameVersion", {branch: root.gameBranch})
            color: Theme.info
            font.pixelSize: Typography.caption
            font.weight: Font.Medium
            font.family: Theme.fontFamily
            elide: Text.ElideRight
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: I18n.format("instances.profile.modsCount", {enabled: root.enabledCount, total: root.modCount})
                color: Theme.textSecondary
                font.pixelSize: Typography.small
                font.weight: Font.Medium
                font.family: Theme.fontFamily
            }

            Item { Layout.fillWidth: true }

            Text {
                text: I18n.resolveMessage(root.createdText)
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
            }
        }

        // action row (revealed on hover, or when active/running)
        Row {
            id: actions
            spacing: 8
            opacity: hover.hovered || root.isActive || root.isRunning ? 1 : 0.35
            Layout.fillWidth: true

            Behavior on opacity { NumberAnimation { duration: Theme.fast } }

            SecondaryButton {
                text: I18n.t("instances.profile.launch")
                icon: "play"
                compact: true
                // jedna instancja naraz: gdy gra działa, uruchamianie jest zablokowane
                enabled: !Game.isRunning && !Profiles.launchInProgress
                onClicked: root.launchRequested()
            }

            SecondaryButton {
                text: root.isActive ? I18n.t("instances.profile.activeButton") : I18n.t("instances.profile.activate")
                icon: root.isActive ? "check-circle" : "check"
                compact: true
                disabled: root.isActive || Game.isRunning || Profiles.launchInProgress
                onClicked: root.activateRequested()
            }

            Item { width: 4 }

            IconButton {
                icon: "hammer"
                tooltip: Game.isRunning
                         ? I18n.t("instances.profile.buildLocked")
                         : I18n.t("instances.profile.build")
                enabled: !Game.isRunning
                buttonSize: 30
                iconSize: 14
                onClicked: root.buildModsRequested()
            }

            IconButton {
                icon: "folder"
                tooltip: I18n.t("instances.profile.openFolder")
                buttonSize: 30
                iconSize: 14
                visible: !root.isDefault
                onClicked: root.openFolderRequested()
            }

            IconButton {
                icon: "edit"
                tooltip: Game.isRunning ? I18n.t("instances.profile.editLocked") : I18n.t("instances.profile.edit")
                enabled: !Game.isRunning
                buttonSize: 30
                iconSize: 14
                onClicked: root.editRequested()
            }

            IconButton {
                icon: "copy"
                tooltip: Game.isRunning ? I18n.t("instances.profile.duplicateLocked") : I18n.t("instances.profile.duplicate")
                enabled: !Game.isRunning
                buttonSize: 30
                iconSize: 14
                onClicked: root.duplicateRequested()
            }

            IconButton {
                icon: "trash"
                tooltip: Game.isRunning ? I18n.t("instances.profile.removeLocked")
                        : root.isDefault ? I18n.t("instances.profile.removeDefault")
                        : root.favorite ? I18n.t("instances.profile.removeFavoriteFirst") : I18n.t("instances.profile.remove")
                enabled: !Game.isRunning && !root.isDefault && !root.favorite
                buttonSize: 30
                iconSize: 14
                danger: true
                visible: !root.isDefault
                onClicked: root.removeRequested()
            }
        }
    }

    HoverHandler { id: hover }
}
