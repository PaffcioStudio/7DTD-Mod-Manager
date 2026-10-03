import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import "pages"
import "theme"
import "i18n"

ApplicationWindow {
    id: window

    width: Math.max(Boot.width || Settings.windowWidth || 1400, minimumWidth)
    height: Math.max(Boot.height || Settings.windowHeight || 880, minimumHeight)
    minimumWidth: 1150
    minimumHeight: 700
    visible: true
    title: I18n.t("app.windowTitle")
    color: Theme.bg0

    // geometria okna (etap 14): zapamiętany rozmiar/maksymalizacja wraca po
    // restarcie; zapis z debounce - resize generuje dziesiątki zdarzeń.
    // Uruchomienia testowe (Boot nadaje wymiary okna) NIE nadpisują geometrii
    // zapamiętanej przez użytkownika.
    Timer {
        id: geometrySave
        interval: 600
        onTriggered: {
            if ((Boot.width || 0) > 0 || (Boot.height || 0) > 0)
                return
            Settings.windowMaximized = window.visibility === Window.Maximized
            if (window.visibility === Window.Windowed) {
                Settings.windowWidth = window.width
                Settings.windowHeight = window.height
            }
        }
    }
    onWidthChanged: geometrySave.restart()
    onHeightChanged: geometrySave.restart()
    onVisibilityChanged: geometrySave.restart()

    readonly property bool frameless: Settings.customWindowFrame
    flags: frameless ? (Qt.Window | Qt.FramelessWindowHint) : Qt.Window

    font.family: Theme.fontFamily
    font.pixelSize: Typography.body

    // ---- theme bindings -------------------------------------------------- #
    Binding { target: Colors; property: "mode"; value: Settings.themeMode }
    Binding { target: Theme; property: "accent"; value: Settings.accentColor }
    Binding { target: Theme; property: "animationsEnabled"; value: Settings.animationsEnabled }
    Binding { target: Dimensions; property: "scale"; value: Settings.uiScale }
    Binding { target: I18n; property: "language"; value: Settings.language }

    // ---- page titles ------------------------------------------------------ #
    readonly property var pageMeta: ({
        "dashboard": [I18n.t("dashboard.title"), I18n.t("dashboard.subtitle")],
        "mods": [I18n.t("mods.title"), I18n.format("mods.caption", {shown: Mods.totalMods, total: Mods.totalMods, enabled: Mods.enabledCount})],
        "profiles": [I18n.t("instances.title"), I18n.t("instances.subtitle")],
        "game_profiles": [I18n.t("gameProfiles.title"), GameProfiles.count > 0 ? I18n.format("gameProfiles.subtitle.count", {count: GameProfiles.count}) : I18n.t("gameProfiles.subtitle.none")],
        "modpacks": [I18n.t("backups.title"), Modpacks.count > 0 ? I18n.format("backups.items", {count: Modpacks.count}) : I18n.t("backups.caption")],
        "downloads": [I18n.t("downloads.title"), Downloads.activeCount > 0 ? I18n.format("downloads.caption", {active: Downloads.activeCount, completed: Downloads.completedCount}) : I18n.t("downloads.caption.none")],
        "discover": [I18n.t("discover.title"), I18n.t("discover.subtitle")],
        "updates": [I18n.t("updates.title"), Mods.updateCount > 0 ? I18n.format("updates.pageSubtitle.withUpdates", {count: Mods.updateCount}) : I18n.t("updates.pageSubtitle.current")],
        "conflicts": [I18n.t("conflicts.title"), Mods.conflictCount > 0 ? I18n.format("conflicts.subtitle.withConflicts", {count: Mods.conflictCount}) : I18n.t("conflicts.subtitle.none")],
        "settings": [I18n.t("settings.title"), I18n.t("settings.subtitle")]
    })

    // ---- main layout -------------------------------------------------------- #
    RowLayout {
        anchors.fill: parent
        spacing: 0

        AppSidebar {
            id: sidebar
            Layout.fillHeight: true
            implicitHeight: window.height
            activePage: pageStack.currentPage
            updatesCount: Mods.updateCount
            downloadsActive: Downloads.activeCount
            titleBarDragEnabled: window.frameless

            onNavigateRequested: (page) => pageStack.go(page)
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            AppHeader {
                id: header
                // above the pages stack: tooltips flipped below header controls
                // must stay visible over the page area
                z: 10
                Layout.fillWidth: true
                implicitHeight: Dimensions.headerH

                pageTitle: (window.pageMeta[pageStack.currentPage] || [I18n.t("dashboard.title"), ""])[0]
                pageSubtitle: (window.pageMeta[pageStack.currentPage] || ["", ""])[1]
                searchVisible: true
                searchText: GlobalSearch.query
                gameDetected: Game.isDetected
                gameTooltip: Game.isDetected
                    ? I18n.format("app.gameDetectedTooltip", {path: Game.executablePath})
                    : I18n.t("app.gameNotDetectedTooltip")
                showWindowButtons: window.frameless
                dragEnabled: window.frameless

                onSearchEdited: (text) => GlobalSearch.query = text
                onSearchAccepted: {
                    if (GlobalSearch.query.trim() !== "") {
                        pageStack.go("mods")
                        Mods.searchText = GlobalSearch.query
                    }
                }
                onSettingsRequested: Bus.goTo("settings")
                onGameStatusRequested: {
                    pageStack.go("settings")
                    Qt.callLater(() => settingsPage.openSection("game"))
                }
                onAccountRequested: steamAccountModal.open()
            }

            // ---- pages ---------------------------------------------------- #
            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: false

                PageStack {
                    id: pageStack
                    anchors.fill: parent

                    DashboardPage {}
                    ModsPage {}
                    ProfilesPage { id: profilesPage; objectName: "profilesPage" }
                    GameProfilesPage {}
                    BackupsPage {}
                    DownloadsPage {}
                    DiscoverPage { id: discoverPage }
                    UpdatesPage {}
                    ConflictsPage {}
                    SettingsPage { id: settingsPage }
                }

                Connections {
                    target: pageStack
                    function onPageChanged() {
                        globalSearchPopup.close()
                        header.closeSearch()
                    }
                }
            }
        }
    }

    // Global search dropdown: it behaves like a real anchored popup, so it
    // closes on outside click / Escape and never stays open after navigation.
    Popup {
        id: globalSearchPopup
        parent: Overlay.overlay
        modal: false
        focus: false
        padding: 0
        closePolicy: Popup.CloseOnPressOutside | Popup.CloseOnEscape
        // Controls.Basic Popup has its own default background. Keep it fully
        // transparent so the dark search card below is the only visible edge.
        background: Rectangle {
            color: "transparent"
            border.width: 0
        }
        z: 900

        x: header.mapToItem(Overlay.overlay, header.searchLeft, header.searchBottom).x
        y: header.mapToItem(Overlay.overlay, header.searchLeft, header.searchBottom).y + 8
        width: Math.min(520, Math.max(320, Overlay.overlay.width - x - 12))
        height: Math.min(530, globalSearchLoader.item ? globalSearchLoader.item.implicitHeight : 530)

        Loader {
            id: globalSearchLoader
            anchors.fill: parent
            active: globalSearchPopup.opened
            source: active ? Qt.resolvedUrl("components/GlobalSearchPopup.qml") : ""

            function syncItem() {
                if (!item)
                    return
                item.query = Qt.binding(function() { return GlobalSearch.query })
                item.active = Qt.binding(function() { return globalSearchPopup.opened })
                item.busy = Qt.binding(function() { return GlobalSearch.busy })
                item.error = Qt.binding(function() { return GlobalSearch.error })
                item.errorKey = Qt.binding(function() { return GlobalSearch.errorKey })
                item.errorValues = Qt.binding(function() { return GlobalSearch.errorValues })
                item.results = Qt.binding(function() { return GlobalSearch.results })
            }

            function openSearchResult(kind, itemId, title) {
                globalSearchPopup.close()
                header.closeSearch()
                GlobalSearch.clear()
                if (kind === "mod") {
                    Mods.searchText = title
                    pageStack.go("mods")
                    Bus.openMod(itemId)
                } else if (kind === "discover") {
                    pageStack.go("discover")
                    Qt.callLater(function() { discoverPage.openDetails(itemId) })
                } else if (kind === "instance") {
                    pageStack.go("profiles")
                    Qt.callLater(function() { profilesPage.openEditor(itemId) })
                }
            }

            onLoaded: {
                syncItem()
                item.resultClicked.connect(openSearchResult)
            }
        }

        onClosed: header.closeSearch()
    }

    Connections {
        target: header
        function onSearchFocusedChanged() {
            if (header.searchFocused && GlobalSearch.query.trim() !== "")
                globalSearchPopup.open()
            else if (!header.searchFocused)
                globalSearchPopup.close()
        }
    }

    Connections {
        target: GlobalSearch
        function onQueryChanged() {
            if (header.searchFocused && GlobalSearch.query.trim() !== "")
                globalSearchPopup.open()
            else
                globalSearchPopup.close()
        }
    }

    // ---- overlays -------------------------------------------------------- #
    SteamAccountModal {
        id: steamAccountModal
        anchorItem: header.accountAnchor
        menuParent: header
    }

    ModDetailsDrawer {
        id: modDrawer
    }

    // ---- modal decyzji dla zestawu modów (overhaul) ---------------------- #
    Modal {
        id: multiModModal
        cardWidth: 560
        title: I18n.t("main.multiMod.title")
        iconName: "package"

        property string itemRef: ""
        property string packTitle: ""
        property int modCount: 0

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                Layout.fillWidth: true
                text: I18n.format("main.multiMod.description", {title: multiModModal.packTitle, count: multiModModal.modCount})
                color: Theme.text
                font.pixelSize: Typography.body
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }

            Text {
                Layout.fillWidth: true
                text: I18n.t("main.multiMod.choice")
                color: Theme.textSecondary
                font.pixelSize: Typography.small
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
                lineHeight: 1.35
            }
        }

        footer: [
            SecondaryButton {
                text: I18n.t("main.multiMod.addMods")
                onClicked: {
                    Downloads.resolveMulti(multiModModal.itemRef, "mods")
                    multiModModal.close()
                }
            },
            PrimaryButton {
                text: I18n.t("main.multiMod.createInstance")
                icon: "plus"
                onClicked: {
                    Downloads.resolveMulti(multiModModal.itemRef, "instance")
                    multiModModal.close()
                }
            }
        ]
    }

    Connections {
        target: Downloads
        function onMultiModFound(itemRef, title, count) {
            multiModModal.itemRef = itemRef
            multiModModal.packTitle = title
            multiModModal.modCount = count
            multiModModal.open()
        }
    }

    Connections {
        target: GameVersions
        function onAccountConnected(username) {
            toasts.show(I18n.format("main.accountConnected", {username: username}), "success")
        }
    }

    ToastManager {
        id: toasts
        parent: Overlay.overlay
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: 22
        anchors.bottomMargin: 22
        z: 950
    }

    // resize edges for the frameless window
    Repeater {
        model: window.frameless && window.visibility !== Window.Maximized
             ? [{ edges: Qt.TopEdge, x: 0, y: 0, w: window.width, h: 5, cursor: Qt.SizeVerCursor },
                { edges: Qt.BottomEdge, x: 0, y: window.height - 5, w: window.width, h: 5, cursor: Qt.SizeVerCursor },
                { edges: Qt.LeftEdge, x: 0, y: 0, w: 5, h: window.height, cursor: Qt.SizeHorCursor },
                { edges: Qt.RightEdge, x: window.width - 5, y: 0, w: 5, h: window.height, cursor: Qt.SizeHorCursor },
                { edges: Qt.TopEdge | Qt.LeftEdge, x: 0, y: 0, w: 14, h: 14, cursor: Qt.SizeFDiagCursor },
                { edges: Qt.TopEdge | Qt.RightEdge, x: window.width - 14, y: 0, w: 14, h: 14, cursor: Qt.SizeBDiagCursor },
                { edges: Qt.BottomEdge | Qt.LeftEdge, x: 0, y: window.height - 14, w: 14, h: 14, cursor: Qt.SizeBDiagCursor },
                { edges: Qt.BottomEdge | Qt.RightEdge, x: window.width - 14, y: window.height - 14, w: 14, h: 14, cursor: Qt.SizeFDiagCursor }]
             : []

        MouseArea {
            required property var modelData
            x: modelData.x
            y: modelData.y
            width: modelData.w
            height: modelData.h
            cursorShape: modelData.cursor
            z: 9998
            acceptedButtons: Qt.LeftButton

            onPressed: (mouse) => {
                window.startSystemResize(modelData.edges)
            }
        }
    }

    // ---- global shortcuts -------------------------------------------------- #
    Shortcut {
        sequence: "Ctrl+F"
        onActivated: {
            Bus.goTo("mods")
            header.focusSearch()
        }
    }

    // skróty wg pozycji w sidebarze: Pulpit | Instancje | Profile | Odkrywaj |
    // Mody | Kopie | Aktualizacje | Pobieranie; Ustawienia na końcu.
    Shortcut { sequence: "Ctrl+1"; onActivated: Bus.goTo("dashboard") }
    Shortcut { sequence: "Ctrl+2"; onActivated: Bus.goTo("profiles") }
    Shortcut { sequence: "Ctrl+3"; onActivated: Bus.goTo("game_profiles") }
    Shortcut { sequence: "Ctrl+4"; onActivated: Bus.goTo("discover") }
    Shortcut { sequence: "Ctrl+5"; onActivated: Bus.goTo("mods") }
    Shortcut { sequence: "Ctrl+6"; onActivated: Bus.goTo("modpacks") }
    Shortcut { sequence: "Ctrl+7"; onActivated: Bus.goTo("updates") }
    Shortcut { sequence: "Ctrl+8"; onActivated: Bus.goTo("downloads") }
    Shortcut { sequence: "Ctrl+9"; onActivated: Bus.goTo("settings") }

    // ---- bus wiring ---------------------------------------------------------- #
    Connections {
        target: Bus

        function onNotify(message, level) {
            toasts.show(I18n.resolveMessage(message), level)
        }

        function onNotifyKey(key, values, level) {
            toasts.show(I18n.format(key, values), level)
        }

        function onNavigate(page) {
            pageStack.go(page)
        }

        function onOpenModRequested(modId) {
            modDrawer.openWith(modId)
        }
    }

    // ---- boot ---------------------------------------------------------------- #
    Component.onCompleted: {
        // geometria (etap 14): zapamiętany rozmiar/maksymalizacja; argumenty
        // Boot (screenshoty) mają pierwszeństwo
        if ((Boot.width || 0) <= 0 && Settings.windowMaximized)
            window.showMaximized()

        if (Boot.page !== "") {
            pageStack.go(Boot.page)
        }
        if (Boot.drawerMod !== "") {
            const dm = Boot.drawerMod
            // "instance:new" otwiera modal tworzenia instancji (testy UI),
            // "instance:<id>" otwiera modal edycji instancji,
            // "game-versions" otwiera menedżer wersji gry;
            // pozostałe wartości = drawer szczegółów moda
            if (dm === "game-versions")
                Qt.callLater(() => profilesPage.openGameVersions())
            else if (dm.indexOf("instance:") === 0) {
                const inst = dm.substring(9)
                if (inst === "new")
                    Qt.callLater(() => profilesPage.openNew())
                else
                    Qt.callLater(() => profilesPage.openEditor(inst))
            }
            else
                Qt.callLater(() => modDrawer.openWith(dm))
        }
        if (Boot.toastDemo) {
            toasts.show(I18n.format("toast.mods.enabled", {name: "Better Loot"}), "success")
            Qt.callLater(() => toasts.show(I18n.format("toast.mods.conflictDetected", {a: "Better Loot", b: "Loot Overhaul"}), "warning"))
        }
    }
}
