import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Własny przeglądarka katalogów dla importu modów. Zamiast natywnego
// FolderDialog pokazujemy spójny z aplikacją picker z dyskami, ukrytymi
// plikami, Ctrl+I do ścieżki oraz Ctrl+H do plików ukrytych.
Modal {
    id: root

    title: I18n.t("folderPicker.title")
    iconName: "folder"
    cardWidth: 1080

    property string selectedFolder: ""
    property string startPath: ""

    signal folderPicked(string path)

    function openAt(path) {
        selectedFolder = ""
        const candidate = String(path || "").trim()
        FileBrowser.navigate(candidate !== "" ? candidate : FileBrowser.currentPath)
        root.open()
    }

    onOpenedChanged: {
        if (opened) {
            FileBrowser.ensureInitialized()
            pathInput.text = FileBrowser.currentPath
            pathInput.inputItem.forceActiveFocus()
            pathInput.inputItem.selectAll()
            pathInput.inputItem.deselect()
        }
    }

    Connections {
        target: FileBrowser
        function onCurrentPathChanged() {
            pathInput.text = FileBrowser.currentPath
            root.selectedFolder = ""
        }
    }

    // Keyboard shortcuts intentionally live inside the modal, so they only
    // affect the picker while it is open.
    Shortcut {
        sequence: "Ctrl+H"
        enabled: root.opened
        onActivated: FileBrowser.showHidden = !FileBrowser.showHidden
    }

    Shortcut {
        sequence: "Ctrl+I"
        enabled: root.opened
        onActivated: {
            pathInput.inputItem.forceActiveFocus()
            pathInput.inputItem.selectAll()
        }
    }

    Shortcut {
        sequence: "Alt+Up"
        enabled: root.opened
        onActivated: FileBrowser.goUp()
    }

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: 548

        RowLayout {
            anchors.fill: parent
            spacing: 12

            // -----------------------------------------------------------
            // Places / drives
            // -----------------------------------------------------------
            Rectangle {
                Layout.fillHeight: true
                Layout.preferredWidth: 236
                radius: 12
                color: Theme.bg1
                border.width: 1
                border.color: Theme.border

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    Text {
                        text: I18n.t("folderPicker.places")
                        color: Theme.text
                        font.pixelSize: Typography.small + 1
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                        Layout.leftMargin: 6
                        Layout.topMargin: 4
                    }

                    Repeater {
                        model: [
                            { name: I18n.t("folderPicker.home"), icon: "home", path: FileBrowser.homePath },
                            { name: I18n.t("folderPicker.root"), icon: "hard-drive", path: "/" },
                            { name: I18n.t("folderPicker.modsFolder"), icon: "package", path: Settings.modsDirectory },
                            { name: I18n.t("folderPicker.downloads"), icon: "download", path: Settings.downloadDirectory }
                        ]

                        Item {
                            id: placeRow
                            required property var modelData
                            implicitHeight: 42
                            Layout.fillWidth: true

                            readonly property bool active: FileBrowser.currentPath === String(modelData.path)

                            Rectangle {
                                anchors.fill: parent
                                radius: 9
                                color: placeRow.active ? Theme.accentSoft
                                     : placeHover.hovered ? Theme.bg3 : "transparent"
                                border.width: placeRow.active ? 1 : 0
                                border.color: Theme.rgba(Theme.accent, 0.28)
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 8
                                spacing: 10

                                Icon {
                                    name: modelData.icon
                                    size: 16
                                    tint: placeRow.active ? Theme.accent : Theme.textMuted
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0

                                    Text {
                                        text: modelData.name_key ? I18n.t(modelData.name_key) : (modelData.name || "")
                                        color: placeRow.active ? Theme.text : Theme.textSecondary
                                        font.pixelSize: Typography.small
                                        font.weight: placeRow.active ? Font.Medium : Font.Normal
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    Text {
                                        text: Theme.shortPath(String(modelData.path))
                                        color: Theme.textFaint
                                        font.pixelSize: 10
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }
                            }

                            HoverHandler { id: placeHover }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!FileBrowser.navigate(String(placeRow.modelData.path)))
                                        Bus.toast(I18n.resolveMessage(FileBrowser.error), "warning")
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.border
                        Layout.topMargin: 4
                        Layout.bottomMargin: 4
                    }

                    Text {
                        text: I18n.t("folderPicker.drives")
                        color: Theme.text
                        font.pixelSize: Typography.small + 1
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                        Layout.leftMargin: 6
                    }

                    ListView {
                        id: drivesView
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        model: FileBrowser.drives
                        spacing: 4
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        maximumFlickVelocity: 1600
                        flickDeceleration: 5200

                        delegate: Item {
                            id: driveRow
                            required property var modelData
                            width: drivesView.width
                            height: 46

                            Rectangle {
                                anchors.fill: parent
                                radius: 9
                                color: FileBrowser.currentPath === modelData.path ? Theme.accentSoft
                                     : driveHover.hovered ? Theme.bg3 : "transparent"
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 8
                                spacing: 9

                                Icon {
                                    name: "hard-drive"
                                    size: 16
                                    tint: FileBrowser.currentPath === modelData.path ? Theme.accent : Theme.textMuted
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        text: modelData.name_key !== "" ? I18n.t(modelData.name_key) : modelData.name
                                        color: Theme.textSecondary
                                        font.pixelSize: Typography.small
                                        font.weight: Font.Medium
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: modelData.path + (modelData.free !== "" ? "  ·  " + I18n.format("folderPicker.freeSpace", {free: modelData.free}) : "")
                                        color: Theme.textFaint
                                        font.pixelSize: 10
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideMiddle
                                        Layout.fillWidth: true
                                    }
                                }
                            }

                            HoverHandler { id: driveHover }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: FileBrowser.navigate(modelData.path)
                            }
                        }

                        ScrollBar.vertical: AppScrollBar {}

                        WheelHandler {
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: (event) => {
                                const maxY = Math.max(0, drivesView.contentHeight - drivesView.height)
                                if (maxY <= 0) { event.accepted = false; return }
                                drivesView.cancelFlick()
                                const delta = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                                drivesView.contentY = Math.max(0, Math.min(maxY, drivesView.contentY - delta))
                                event.accepted = true
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        radius: 9
                        color: Theme.bg2
                        border.width: 1
                        border.color: Theme.border
                        implicitHeight: 52

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 9
                            Icon { name: "info"; size: 14; tint: Theme.textMuted }
                            Text {
                                Layout.fillWidth: true
                                text: I18n.t("folderPicker.shortcuts")
                                color: Theme.textMuted
                                font.pixelSize: 10
                                font.family: Theme.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            // -----------------------------------------------------------
            // Main browser
            // -----------------------------------------------------------
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    AppTextField {
                        id: pathInput
                        Layout.fillWidth: true
                        placeholder: "/home/…"
                        onAccepted: {
                            if (!FileBrowser.navigate(text)) {
                                Bus.toast(I18n.resolveMessage(FileBrowser.error), "warning")
                                text = FileBrowser.currentPath
                            }
                        }
                    }

                    IconButton {
                        icon: "arrow-up"
                        buttonSize: 38
                        tooltip: I18n.t("folderPicker.up")
                        disabled: !FileBrowser.canGoUp
                        onClicked: FileBrowser.goUp()
                    }

                    IconButton {
                        icon: "refresh-cw"
                        buttonSize: 38
                        tooltip: I18n.t("folderPicker.refresh")
                        onClicked: FileBrowser.refresh()
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: FileBrowser.currentPath
                            color: Theme.text
                            font.pixelSize: Typography.body
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }
                        Text {
                            text: I18n.t("folderPicker.clickHint")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                        }
                    }

                    RowLayout {
                        spacing: 8
                        Layout.alignment: Qt.AlignRight
                        Text {
                            text: I18n.t("folderPicker.hidden")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                        }
                        ToggleSwitch {
                            checked: FileBrowser.showHidden
                            onToggled: (checked) => FileBrowser.showHidden = checked
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 12
                    color: Theme.bg1
                    border.width: 1
                    border.color: Theme.border
                    Layout.fillHeight: true
                    clip: true

                    ListView {
                        id: entriesView
                        anchors.fill: parent
                        anchors.margins: 8
                        model: FileBrowser.entriesModel
                        spacing: 4
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        maximumFlickVelocity: 1700
                        flickDeceleration: 5200

                        ScrollBar.vertical: AppScrollBar {}

                        WheelHandler {
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: (event) => {
                                const maxY = Math.max(0, entriesView.contentHeight - entriesView.height)
                                if (maxY <= 0) { event.accepted = false; return }
                                entriesView.cancelFlick()
                                const delta = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                                entriesView.contentY = Math.max(0, Math.min(maxY, entriesView.contentY - delta))
                                event.accepted = true
                            }
                        }

                        delegate: Item {
                            id: entryRow
                            required property string entryName
                            required property string entryPath
                            required property bool isDirectory
                            required property bool isHidden
                            required property string sizeText
                            required property string typeLabel
                            width: entriesView.width - 4
                            height: 48

                            readonly property bool selected: root.selectedFolder === entryPath

                            Rectangle {
                                anchors.fill: parent
                                radius: 9
                                color: entryRow.selected ? Theme.accentSoft
                                     : entryHover.hovered ? Theme.bg3 : "transparent"
                                border.width: entryRow.selected ? 1 : 0
                                border.color: Theme.rgba(Theme.accent, 0.30)
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 12
                                spacing: 11

                                Rectangle {
                                    width: 30
                                    height: 30
                                    radius: 8
                                    color: entryRow.isDirectory ? Theme.infoSoft : Theme.bg3
                                    border.width: 1
                                    border.color: entryRow.isDirectory ? Theme.rgba(Theme.info, 0.22) : Theme.border
                                    Layout.alignment: Qt.AlignVCenter

                                    Icon {
                                        anchors.centerIn: parent
                                        name: entryRow.isDirectory ? "folder" : "file-text"
                                        size: 15
                                        tint: entryRow.isDirectory ? Theme.info : Theme.textMuted
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1
                                    Text {
                                        text: entryRow.entryName
                                        color: Theme.text
                                        font.pixelSize: Typography.small
                                        font.weight: entryRow.selected ? Font.DemiBold : Font.Medium
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: entryRow.isDirectory ? I18n.t("folderPicker.folder") : (entryRow.sizeText !== "" ? entryRow.sizeText : I18n.t("folderPicker.file"))
                                        color: entryRow.isHidden ? Theme.warning : Theme.textFaint
                                        font.pixelSize: 10
                                        font.family: Theme.fontFamily
                                    }
                                }

                                Text {
                                    text: entryRow.isHidden ? I18n.t("folderPicker.hiddenBadge") : ""
                                    visible: entryRow.isHidden
                                    color: Theme.warning
                                    font.pixelSize: 9
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }

                                Icon {
                                    visible: entryRow.isDirectory
                                    name: "chevron-right"
                                    size: 15
                                    tint: Theme.textFaint
                                }
                            }

                            HoverHandler { id: entryHover }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: entryRow.isDirectory ? Qt.PointingHandCursor : Qt.ArrowCursor
                                acceptedButtons: Qt.LeftButton
                                onClicked: {
                                    root.selectedFolder = entryRow.isDirectory ? entryRow.entryPath : ""
                                }
                                onDoubleClicked: {
                                    if (entryRow.isDirectory) {
                                        if (FileBrowser.navigate(entryRow.entryPath))
                                            root.selectedFolder = ""
                                    }
                                }
                            }
                        }

                        EmptyState {
                            anchors.centerIn: parent
                            width: Math.min(parent.width - 80, 480)
                            visible: entriesView.count === 0
                            icon: FileBrowser.error !== "" ? "alert-triangle" : "folder"
                            tint: FileBrowser.error !== "" ? Theme.warning : Theme.textMuted
                            title: FileBrowser.error !== "" ? I18n.t("folderPicker.readError") : I18n.t("folderPicker.empty")
                            subtitle: FileBrowser.error !== "" ? I18n.resolveMessage(FileBrowser.error) : I18n.t("folderPicker.showHidden")
                            actionText: I18n.t("folderPicker.refresh")
                            onActionTriggered: FileBrowser.refresh()
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: 10
                    color: root.selectedFolder !== "" ? Theme.accentSoft : Theme.bg2
                    border.width: 1
                    border.color: root.selectedFolder !== "" ? Theme.rgba(Theme.accent, 0.28) : Theme.border
                    implicitHeight: 46

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 10

                        Icon {
                            name: root.selectedFolder !== "" ? "check-circle" : "folder"
                            size: 16
                            tint: root.selectedFolder !== "" ? Theme.accent : Theme.textMuted
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 1
                            Text {
                                text: root.selectedFolder !== "" ? I18n.t("folderPicker.selectedFolder") : I18n.t("folderPicker.currentFolder")
                                color: Theme.textSecondary
                                font.pixelSize: Typography.caption
                                font.weight: Font.Medium
                                font.family: Theme.fontFamily
                            }
                            Text {
                                text: root.selectedFolder !== "" ? root.selectedFolder : FileBrowser.currentPath
                                color: Theme.textMuted
                                font.pixelSize: 10
                                font.family: Theme.fontFamily
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }
    }

    footer: [
        SecondaryButton {
            text: I18n.t("folderPicker.cancel")
            onClicked: root.close()
        },
        PrimaryButton {
            text: I18n.t("folderPicker.scanImport")
            icon: "search"
            large: true
            disabled: FileBrowser.currentPath === "" && root.selectedFolder === ""
            onClicked: {
                const path = root.selectedFolder !== "" ? root.selectedFolder : FileBrowser.currentPath
                root.folderPicked(path)
                root.close()
            }
        }
    ]
}
