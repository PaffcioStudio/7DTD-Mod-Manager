import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Three genuinely different presentations of the same instance and actions.
// Configuration (paths, startup flags and Proton) stays in the editor/tooltip.
Item {
    id: root

    signal launchRequested()
    signal activateRequested()
    signal logsRequested()
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
    property string protonPath: ""
    property bool favorite: false
    property int totalPlaySeconds: 0
    property real lastPlayedEpoch: 0
    property string viewMode: "grid"   // grid, list or spotlight

    readonly property bool isList: viewMode === "list"
    readonly property bool isSpotlight: viewMode === "spotlight"
    implicitHeight: isList ? 160 : (isSpotlight ? 260 : 226)

    function durationText(seconds) {
        const minutes = Math.floor(Math.max(0, seconds) / 60)
        const hours = Math.floor(minutes / 60)
        if (hours === 0) return I18n.format("instances.playtime.minutes", {count: minutes})
        if (minutes % 60 === 0) return I18n.format("instances.playtime.hours", {count: hours})
        return I18n.format("instances.playtime.hoursMinutes", {hours: hours, minutes: minutes % 60})
    }

    function lastPlayedText() {
        if (lastPlayedEpoch <= 0)
            return I18n.t("instances.playtime.never")
        const stamp = new Date(lastPlayedEpoch * 1000)
        if (isNaN(stamp.getTime())) return I18n.t("instances.playtime.never")
        const locale = Qt.locale(I18n.language === "pl" ? "pl_PL" : "en_US")
        return I18n.format("instances.playtime.last", {
            date: stamp.toLocaleDateString(locale, Locale.ShortFormat),
            time: stamp.toLocaleTimeString(locale, Locale.ShortFormat)
        })
    }

    Rectangle {
        anchors.fill: parent
        radius: Dimensions.radiusLg
        color: root.isSpotlight ? Theme.bg3 : Theme.bg2
        border.width: root.isActive ? 2 : 1
        border.color: root.isRunning ? Theme.success
                      : root.isActive ? Theme.rgba(root.colorTag, 0.65)
                      : hover.hovered ? Theme.borderHover : Theme.border
        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
    }

    Rectangle {
        width: root.isSpotlight ? 5 : 3
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 13
        radius: 3
        color: root.isRunning ? Theme.success : root.colorTag
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.leftMargin: root.isSpotlight ? 28 : 25
        anchors.rightMargin: 12
        anchors.topMargin: root.isList ? 10 : 14
        anchors.bottomMargin: root.isList ? 8 : 12
        spacing: root.isSpotlight ? 9 : 5

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Text {
                Layout.fillWidth: true
                text: I18n.resolveMessage(root.name)
                color: Theme.text
                font.pixelSize: root.isSpotlight ? Typography.h1 : Typography.h2
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }
            Text {
                visible: root.isRunning || root.isActive
                text: root.isRunning ? I18n.t("instances.profile.running") : I18n.t("instances.profile.active")
                color: root.isRunning ? Theme.success : root.colorTag
                font.pixelSize: Typography.micro
                font.weight: Font.DemiBold
                font.family: Theme.fontFamily
            }
            IconButton {
                icon: root.favorite ? "star-filled" : "star"
                tint: root.favorite ? Theme.warning : Theme.textSecondary
                hoverTint: root.favorite ? Theme.warning : Theme.text
                tooltip: root.favorite ? I18n.t("instances.profile.favorite.remove") : I18n.t("instances.profile.favorite.add")
                buttonSize: 28
                iconSize: 16
                onClicked: root.favoriteToggled()
            }
        }

        Text {
            visible: !root.isList && text !== ""
            Layout.fillWidth: true
            text: I18n.resolveMessage(root.description)
            color: Theme.textSecondary
            font.pixelSize: Typography.small
            font.family: Theme.fontFamily
            elide: Text.ElideRight
            maximumLineCount: root.isSpotlight ? 2 : 1
            wrapMode: root.isSpotlight ? Text.WordWrap : Text.NoWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10
            Text {
                text: I18n.format("instances.profile.modsCount", {enabled: root.enabledCount, total: root.modCount})
                color: Theme.textSecondary
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
            }
            Text {
                visible: root.gameBranch !== ""
                Layout.fillWidth: true
                text: I18n.format("instances.profile.gameVersion", {branch: root.gameBranch})
                color: Theme.info
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
                elide: Text.ElideRight
            }
            Item { Layout.fillWidth: true }
            IconButton {
                icon: "info"
                buttonSize: 26
                iconSize: 13
                tooltip: I18n.format("instances.profile.detailsHint", {
                    path: I18n.resolveMessage(root.dataDirDisplay),
                    flags: root.flagsText || "-",
                    proton: root.protonPath || I18n.t("protons.automatic")
                })
            }
        }

        // Playtime is the primary information on a card; the raw folder and
        // launch flags no longer consume two entire lines.
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: root.isSpotlight ? 67 : (root.isList ? 30 : 48)
            radius: 9
            color: Theme.rgba(root.colorTag, root.isSpotlight ? 0.10 : 0.045)
            border.width: root.isSpotlight ? 1 : 0
            border.color: Theme.rgba(root.colorTag, 0.2)

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 12
                Icon {
                    name: "clock"
                    size: root.isSpotlight ? 19 : 15
                    tint: root.colorTag
                }
                ColumnLayout {
                    Layout.preferredWidth: root.isSpotlight ? 140 : (root.isList ? 140 : 104)
                    spacing: 1
                    Text {
                        visible: !root.isList
                        text: I18n.t("instances.playtime.total")
                        color: Theme.textMuted
                        font.pixelSize: Typography.micro
                        font.family: Theme.fontFamily
                    }
                    Text {
                        text: root.durationText(root.totalPlaySeconds)
                        color: Theme.text
                        font.pixelSize: root.isSpotlight ? Typography.h2 : Typography.small
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }
                }
                Rectangle { width: 1; Layout.fillHeight: true; Layout.topMargin: 7; Layout.bottomMargin: 7; color: Theme.border }
                Text {
                    Layout.fillWidth: true
                    text: root.lastPlayedText()
                    color: Theme.textSecondary
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            id: actionRow
            Layout.fillWidth: true
            spacing: root.isList ? 5 : 7
            SecondaryButton {
                text: I18n.t("instances.profile.launch")
                icon: "play"
                compact: true
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
            Item { Layout.fillWidth: true }
            IconButton { icon: "file-text"; buttonSize: 29; iconSize: 14; tooltip: I18n.t("logs.title"); onClicked: root.logsRequested() }
            IconButton {
                icon: "hammer"; buttonSize: 29; iconSize: 14
                tooltip: Game.isRunning ? I18n.t("instances.profile.buildLocked") : I18n.t("instances.profile.build")
                enabled: !Game.isRunning
                onClicked: root.buildModsRequested()
            }
            IconButton { icon: "folder"; buttonSize: 29; iconSize: 14; visible: !root.isDefault; tooltip: I18n.t("instances.profile.openFolder"); onClicked: root.openFolderRequested() }
            IconButton {
                icon: "edit"; buttonSize: 29; iconSize: 14
                tooltip: Game.isRunning ? I18n.t("instances.profile.editLocked") : I18n.t("instances.profile.edit")
                enabled: !Game.isRunning
                onClicked: root.editRequested()
            }
            IconButton {
                icon: "copy"; buttonSize: 29; iconSize: 14
                tooltip: Game.isRunning ? I18n.t("instances.profile.duplicateLocked") : I18n.t("instances.profile.duplicate")
                enabled: !Game.isRunning
                onClicked: root.duplicateRequested()
            }
            IconButton {
                icon: "trash"; buttonSize: 29; iconSize: 14; danger: true
                tooltip: Game.isRunning ? I18n.t("instances.profile.removeLocked")
                         : root.isDefault ? I18n.t("instances.profile.removeDefault")
                         : root.favorite ? I18n.t("instances.profile.removeFavoriteFirst") : I18n.t("instances.profile.remove")
                enabled: !Game.isRunning && !root.isDefault && !root.favorite
                visible: !root.isDefault
                onClicked: root.removeRequested()
            }
        }
    }

    HoverHandler { id: hover }
}
