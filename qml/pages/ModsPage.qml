import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: modsPage
    pageName: "mods"
    maxWidth: 1180

    property string pendingUninstallId: ""
    property string pendingUninstallName: ""

    // ------------------------------------------------------------------ #
    // dialogs
    // ------------------------------------------------------------------ #
    FolderPickerModal {
        id: importFolderPicker
        onFolderPicked: (path) => Mods.importFolder(path)
    }

    // ------------------------------------------------------------------ #
    // filter chips
    // ------------------------------------------------------------------ #
    property var filters: [
        { key: "all", label: I18n.t("mods.filter.all") },
        { key: "enabled", label: I18n.t("mods.filter.enabled") },
        { key: "disabled", label: I18n.t("mods.filter.disabled") },
        { key: "updates", label: I18n.t("mods.filter.updates") },
        { key: "conflicts", label: I18n.t("mods.filter.conflicts") }
    ]

    property var sortOptions: [
        { value: "custom", label: I18n.t("mods.sort.custom") },
        { value: "name", label: I18n.t("mods.sort.name") },
        { value: "installed", label: I18n.t("mods.sort.installed") },
        { value: "updated", label: I18n.t("mods.sort.updated") },
        { value: "author", label: I18n.t("mods.sort.author") },
        { value: "size", label: I18n.t("mods.sort.size") }
    ]

    function refreshI18nOptions() {
        modsPage.filters = [
            { key: "all", label: I18n.t("mods.filter.all") },
            { key: "enabled", label: I18n.t("mods.filter.enabled") },
            { key: "disabled", label: I18n.t("mods.filter.disabled") },
            { key: "updates", label: I18n.t("mods.filter.updates") },
            { key: "conflicts", label: I18n.t("mods.filter.conflicts") }
        ]
        modsPage.sortOptions = [
            { value: "custom", label: I18n.t("mods.sort.custom") },
            { value: "name", label: I18n.t("mods.sort.name") },
            { value: "installed", label: I18n.t("mods.sort.installed") },
            { value: "updated", label: I18n.t("mods.sort.updated") },
            { value: "author", label: I18n.t("mods.sort.author") },
            { value: "size", label: I18n.t("mods.sort.size") }
        ]
    }

    Component.onCompleted: refreshI18nOptions()

    Connections {
        target: I18n
        function onLanguageChanged() { modsPage.refreshI18nOptions() }
    }

    readonly property bool dndEnabled: Mods.sortMode === "custom"

    // ------------------------------------------------------------------ #
    // layout
    // ------------------------------------------------------------------ #
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        anchors.bottomMargin: 0
        spacing: Dimensions.spacingLg

        // actions row - page title/subtitle are already provided by AppHeader
        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Item { Layout.fillWidth: true }

            SecondaryButton {
                text: I18n.t("mods.refresh")
                icon: "refresh-cw"
                onClicked: Mods.rescanGameMods()
            }

            SecondaryButton {
                text: I18n.t("mods.importFolder")
                icon: "folder"
                onClicked: importFolderPicker.openAt(
                    Settings.modsDirectory !== "" ? Settings.modsDirectory : FileBrowser.homePath)
            }
        }

        // toolbar: filters + sort
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Row {
                spacing: 8

                Repeater {
                    model: modsPage.filters

                    FilterChip {
                        required property var modelData
                        label: modelData.label
                        count: Mods.filterCounts[modelData.key] !== undefined ? Mods.filterCounts[modelData.key] : 0
                        active: Mods.filterMode === modelData.key
                        onClicked: Mods.filterMode = modelData.key
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // in-page search (kept in sync with the global header search)
            // chowa się przy wąskim oknie: chipsy + sort potrzebują ~840px,
            // a dopiero od ~1060px strony zostaje jeszcze miejsce na szukajkę
            SearchBar {
                visible: modsPage.width > 1060
                preferredWidth: 230
                placeholder: I18n.t("mods.searchPlaceholder")
                searchText: Mods.searchText
                onSearchEdited: (text) => Mods.searchText = text
            }

            DropdownButton {
                options: modsPage.sortOptions
                value: Mods.sortMode
                onPicked: (value) => Mods.sortMode = value
            }

            IconButton {
                visible: Mods.sortMode !== "custom"
                icon: Mods.sortDescending ? "arrow-down" : "arrow-up"
                tooltip: Mods.sortDescending
                    ? I18n.t("mods.sort.desc")
                    : I18n.t("mods.sort.asc")
                onClicked: Mods.sortDescending = !Mods.sortDescending
            }
        }

        // hint bar for load order
        Item {
            Layout.fillWidth: true
            implicitHeight: 34
            visible: modsPage.dndEnabled

            Rectangle {
                anchors.fill: parent
                radius: 9
                color: Theme.bg2
                border.width: 1
                border.color: Theme.border
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 8

                Icon { name: Mods.thumbStatus !== "" ? "image" : "grip-vertical"; size: 14; tint: Mods.thumbStatus !== "" ? Theme.accent : Theme.textMuted }
                Text {
                    text: Mods.thumbStatus !== ""
                          ? I18n.format("mods.loadOrder.fetchingIcons", {status: Mods.thumbStatus})
                          : I18n.t("mods.loadOrder.hint")
                    color: Mods.thumbStatus !== "" ? Theme.accent : Theme.textMuted
                    font.pixelSize: Typography.caption + 0.5
                    font.family: Theme.fontFamily
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }
        }

        // ---- mod list -------------------------------------------------- #
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            ListView {
                id: modsView
                anchors.fill: parent
                anchors.bottomMargin: Dimensions.pagePad
                model: Mods.listModel
                spacing: 10
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickDeceleration: 5200
                maximumFlickVelocity: 1800

                ScrollBar.vertical: AppScrollBar {}

                WheelHandler {
                    target: null
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad

                    onWheel: (event) => {
                        const maxY = Math.max(0, modsView.contentHeight - modsView.height)
                        if (maxY <= 0) { event.accepted = false; return }
                        const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                        modsView.contentY = Math.max(0, Math.min(maxY, modsView.contentY - step))
                        event.accepted = true
                    }
                }

                // smooth reorder during drag & drop
                moveDisplaced: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: Theme.animationsEnabled ? 260 : 0
                        easing.type: Easing.OutQuad
                    }
                }

                add: Transition {
                    ParallelAnimation {
                        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.normal }
                        NumberAnimation { property: "scale"; from: 0.97; to: 1; duration: Theme.normal }
                    }
                }

                remove: Transition {
                    NumberAnimation { property: "opacity"; from: 1; to: 0; duration: 160 }
                }

                displaced: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: Theme.animationsEnabled ? 220 : 0
                        easing.type: Easing.OutQuad
                    }
                }

                populate: null

                delegate: Item {
                    id: delegateRoot

                    required property string modId
                    required property int index
                    required property string name
                        required property string version
                        required property string gameVersion
                    required property string newVersion
                    required property string author
                    required property string description
                    required property string category
                    required property bool modEnabled
                    required property bool hasUpdate
                    required property bool inConflict
                    required property string updatedAgo
                    required property var tags
                    required property string thumbUrl

                    width: modsView.width
                    height: 118

                    property int visualIndex: index
                    property bool dragging: dragArea.drag.active

                    onDraggingChanged: {
                        if (!dragging) {
                            returnAnimX.from = card.x
                            returnAnimY.from = card.y
                            returnAnim.start()
                        }
                    }

                    ParallelAnimation {
                        id: returnAnim
                        NumberAnimation {
                            id: returnAnimX
                            target: card
                            property: "x"
                            to: 0
                            duration: Theme.animationsEnabled ? 260 : 0
                            easing.type: Easing.OutQuad
                        }
                        NumberAnimation {
                            id: returnAnimY
                            target: card
                            property: "y"
                            to: 0
                            duration: Theme.animationsEnabled ? 260 : 0
                            easing.type: Easing.OutQuad
                        }
                    }

                    // drag source
                    Drag.active: dragArea.drag.active
                    Drag.source: delegateRoot
                    Drag.hotSpot.x: width / 2
                    Drag.hotSpot.y: height / 2

                    // background drag surface (below the card visuals;
                    // interactive card controls sit above and still work)
                    MouseArea {
                        id: dragArea
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton
                        hoverEnabled: false
                        drag.target: modsPage.dndEnabled ? card : null
                        drag.axis: Drag.XAndYAxis
                        drag.threshold: 8

                        onClicked: (mouse) => {
                            if (!dragArea.drag.active) Bus.openMod(delegateRoot.modId)
                        }
                    }

                    DropArea {
                        anchors { fill: parent; margins: 8 }
                        onEntered: (drag) => {
                            let from = drag.source.visualIndex
                            let to = delegateRoot.visualIndex
                            if (from !== to && from >= 0 && to >= 0) {
                                modsView.model.move(from, to)
                            }
                        }
                    }

                    ModCard {
                        id: card
                        x: 0
                        y: 0
                        width: delegateRoot.width
                        height: delegateRoot.height
                        modId: delegateRoot.modId
                        name: delegateRoot.name
                        version: delegateRoot.version
                        gameVersion: delegateRoot.gameVersion
                        newVersion: delegateRoot.newVersion
                        author: delegateRoot.author
                        description: delegateRoot.description
                        category: delegateRoot.category
                        modEnabled: delegateRoot.modEnabled
                        hasUpdate: delegateRoot.hasUpdate
                        inConflict: delegateRoot.inConflict
                        updatedAgo: delegateRoot.updatedAgo
                        tags: delegateRoot.tags
                        thumbUrl: delegateRoot.thumbUrl
                        dragging: delegateRoot.dragging
                        dragHandleVisible: modsPage.dndEnabled

                        onDetailsClicked: Bus.openMod(delegateRoot.modId)
                        onToggleRequested: (enabled) => Mods.toggleMod(delegateRoot.modId)
                        onOpenFolderRequested: Mods.openFolder(delegateRoot.modId)
                        onUninstallRequested: {
                            modsPage.pendingUninstallId = delegateRoot.modId
                            modsPage.pendingUninstallName = delegateRoot.name
                            uninstallConfirm.ask(
                                I18n.t("mods.uninstall.title"),
                                I18n.format("mods.uninstall.message", {name: delegateRoot.name}),
                                I18n.t("mods.uninstall.confirm"), true)
                        }
                    }

                    // lift the card into the page overlay while dragging
                    states: State {
                        name: "dragging"
                        when: delegateRoot.dragging

                        ParentChange {
                            target: card
                            parent: dndLayer
                        }
                    }
                }

                // empty state
                EmptyState {
                    anchors.centerIn: parent
                    width: parent.width
                    visible: modsView.count === 0
                    icon: "search"
                    tint: Theme.textMuted
                    title: I18n.t("mods.empty.title")
                    subtitle: Mods.searchText !== ""
                        ? I18n.format("mods.empty.search", {query: Mods.searchText})
                        : I18n.t("mods.empty.category")
                    actionText: I18n.t("mods.empty.clearFilters")
                    onActionTriggered: {
                        Mods.searchText = ""
                        Mods.filterMode = "all"
                    }
                }
            }
        }
    }

    // drag overlay layer (above the list, below modals/drawer)
    Item {
        id: dndLayer
        anchors.fill: parent
        z: 60
    }

    // ---- uninstall confirm --------------------------------------------- #
    ConfirmModal {
        id: uninstallConfirm
        onConfirmed: Mods.uninstallMod(modsPage.pendingUninstallId)
    }
}
