import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "components"
import "pages"
import "theme"
import "i18n"

ApplicationWindow {
    id: window

    function openOnlineSearch(text) {
        const phrase = String(text || "").trim()
        if (!phrase)
            return
        globalSearchPopup.close()
        header.closeSearch()
        GlobalSearch.clear()
        // Set the intended provider and query before navigating, to avoid
        // initial Discover loading overwriting the requested search.
        discoverPage.searchFromHeader(phrase)
        pageStack.go("discover")
    }

    Connections {
        target: Downloads
        function onMissingGameVersion(token, branch) {
            missingGameDialog.token = token
            missingGameDialog.ask(I18n.t("download.gameVersion.confirmTitle"),
                I18n.format("download.gameVersion.confirmMessage", {branch: branch}),
                I18n.t("download.gameVersion.confirmAction"), false)
        }
    }
    ConfirmModal {
        id: missingGameDialog
        cardWidth: 620
        alternativeLabel: I18n.t("download.gameVersion.downloadAnyway")
        onAlternativeConfirmed: Downloads.downloadDespiteMissingGame(token)
        closeHandler: function() { close(); Downloads.resolveMissingGame(token, false) }
        property string token: ""
        onConfirmed: Downloads.resolveMissingGame(token, true)
        onRejected: Downloads.resolveMissingGame(token, false)
    }

    Connections {
        target: Downloads
        function onIncompatibleModFile(token, title, version) {
            incompatibleFileDialog.enqueue(token, title, version)
        }
    }
    ConfirmModal {
        id: incompatibleFileDialog
        property string token: ""
        property var requests: []
        function enqueue(requestToken, modTitle, version) {
            requests.push({token: requestToken, name: modTitle, version: version})
            showNext()
        }
        function showNext() {
            if (token !== "" || requests.length === 0)
                return
            const request = requests.shift()
            token = request.token
            ask(I18n.t("download.compatibility.title"),
                I18n.format("download.compatibility.warning", request),
                I18n.t("download.gameVersion.downloadAnyway"), false)
        }
        function finish(accepted) {
            const requestToken = token
            token = ""
            Downloads.resolveIncompatibleFile(requestToken, accepted)
            Qt.callLater(showNext)
        }
        onConfirmed: finish(true)
        onRejected: finish(false)
        closeHandler: function() { close(); finish(false) }
    }

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

    // ---- page catalog ---------------------------------------------------- #
    // Page descriptions appear below their titles in AppHeader, not repeated
    // in each page. Long text is elided, with the full text on hover.
    readonly property var pageMeta: ({
        "dashboard": [I18n.t("dashboard.title"), I18n.t("dashboard.subtitle")],
        "mods": [I18n.t("mods.title"), I18n.format("mods.caption", {shown: Mods.visibleMods, total: Mods.totalMods, enabled: Mods.enabledCount})],
        "profiles": [I18n.t("instances.title"), I18n.t("instances.subtitle")],
        "protons": [I18n.t("nav.protons"), I18n.t("protons.help")],
        "steam_releases": [I18n.t("steamReleases.title"), I18n.t("steamReleases.subtitle")],
        "game_profiles": [I18n.t("gameProfiles.title"), GameProfiles.count > 0 ? I18n.format("gameProfiles.subtitle.count", {count: GameProfiles.count}) : I18n.t("gameProfiles.subtitle.none")],
        "modpacks": [I18n.t("backups.title"), Modpacks.count > 0 ? I18n.format("backups.items", {count: Modpacks.count}) : I18n.t("backups.caption")],
        "downloads": [I18n.t("downloads.title"), Downloads.activeCount > 0 ? I18n.format("downloads.caption", {active: Downloads.activeCount, completed: Downloads.completedCount}) : I18n.t("downloads.caption.none")],
        "discover": [I18n.t("discover.title"), I18n.t("discover.subtitle")],
        "updates": [I18n.t("updates.title"), Mods.updateCount > 0 ? I18n.format("updates.pageSubtitle.withUpdates", {count: Mods.updateCount}) : I18n.t("updates.pageSubtitle.current")],
        "conflicts": [I18n.t("conflicts.title"), Mods.conflictCount > 0 ? I18n.format("conflicts.subtitle.withConflicts", {count: Mods.conflictCount}) : I18n.t("conflicts.subtitle.none")],
        "settings": [I18n.t("settings.title"), I18n.t("settings.subtitle")]
    })

    // Page titles remain directly available for places that need a short label.
    readonly property var pageTitles: ({
        "dashboard": I18n.t("dashboard.title"),
        "mods": I18n.t("mods.title"),
        "profiles": I18n.t("instances.title"),
        "protons": I18n.t("nav.protons"),
        "steam_releases": I18n.t("steamReleases.title"),
        "game_profiles": I18n.t("gameProfiles.title"),
        "modpacks": I18n.t("backups.title"),
        "downloads": I18n.t("downloads.title"),
        "discover": I18n.t("discover.title"),
        "updates": I18n.t("updates.title"),
        "conflicts": I18n.t("conflicts.title"),
        "settings": I18n.t("settings.title")
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

                pageTitle: window.pageTitles[pageStack.currentPage] || I18n.t("dashboard.title")
                // Subtitles live directly under the page title, beside global search.
                // AppHeader elides lengthy copy and reveals it in a tooltip.
                pageSubtitle: window.pageMeta[pageStack.currentPage]
                              ? window.pageMeta[pageStack.currentPage][1] : ""
                searchVisible: true
                searchText: GlobalSearch.query
                gameDetected: Game.isDetected
                gameTooltip: Game.isDetected
                    ? I18n.format("app.gameDetectedTooltip", {path: Game.executablePath})
                    : I18n.t("app.gameNotDetectedTooltip")
                showWindowButtons: window.frameless
                dragEnabled: window.frameless

                onSearchEdited: (text) => GlobalSearch.query = text
                // Enter searches the website, while the popup keeps local and
                // online matches visible together as the user types.
                onSearchAccepted: window.openOnlineSearch(GlobalSearch.query)
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
                    SteamReleasesPage { id: steamReleasesPage
                        objectName: "steamReleasesPage"
                        onLogoutRequested: steamAccountModal.requestLogout()
                        onSandboxRequested: (branch) => {
                            pageStack.go("profiles")
                            profilesPage.openSandboxForBranch(branch)
                        }
                    }
                    ProtonsPage { objectName: "protonsPage" }
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
                item.onlineChecked = Qt.binding(function() { return GlobalSearch.onlineChecked })
                item.onlineOffline = Qt.binding(function() { return GlobalSearch.onlineOffline })
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
                    // Always open an online hit with the web provider, even
                    // when the Discover page was set to local overhauls.
                    discoverPage.provider = "web"
                    discoverPage.version = ""
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
                item.showOnlineRequested.connect(window.openOnlineSearch)
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

    // Search should lose keyboard focus as soon as the user clicks anywhere
    // outside the field.  A window-level TapHandler observes the tap without
    // becoming a blocking MouseArea, so buttons and page controls continue to
    // receive the click normally.
    TapHandler {
        acceptedButtons: Qt.LeftButton
        // The search TextInput is a child that normally grabs the pointer.
        // Allow this observer to also see taps handled by sibling/child
        // controls so an outside click can always dismiss keyboard focus.
        grabPermissions: PointerHandler.CanTakeOverFromAnything
        onTapped: (point) => {
            if (!header.searchFocused)
                return
            const topLeft = header.mapToItem(
                window.contentItem, header.searchLeft, 0)
            const p = point.position
            const inside = p.x >= topLeft.x
                         && p.x <= topLeft.x + header.searchWidth
                         && p.y >= topLeft.y
                         && p.y <= topLeft.y + header.height
            if (!inside)
                header.closeSearch()
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

    // Wybór dotyczy konkretnego pliku, także dodatków do overhaula.
    Modal {
        id: multiModModal
        cardWidth: 620
        title: I18n.t("main.multiMod.title")
        iconName: "package"
        property string itemRef: ""
        property string packTitle: ""
        property string fileLabel: ""
        property string fileType: ""
        readonly property string fileTypeLabel: {
            const names = {main: "main", optional: "optional", old: "old", other_version: "old", external: "external"}
            return names[fileType] ? I18n.t("discover.drawer.fileType." + names[fileType]) : fileType || I18n.t("common.unknown")
        }
        property int modCount: 0
        property var requests: []
        function enqueue(item, name, label, type, count) {
            requests.push({item: item, name: name, label: label, type: type, count: count})
            showNext()
        }
        function showNext() {
            if (itemRef !== "")
                return
            while (requests.length > 0) {
                const request = requests.shift()
                if (!Downloads.hasInstallDecision(request.item))
                    continue
                itemRef = request.item
                packTitle = request.name
                fileLabel = request.label
                fileType = request.type
                modCount = request.count
                open()
                return
            }
        }
        function finish(choice) {
            if (itemRef === "")
                return
            const item = itemRef
            itemRef = ""
            close()
            Downloads.resolveMulti(item, choice)
            Qt.callLater(showNext)
        }
        closeHandler: function() { finish("cancel") }
        Timer {
            interval: 200
            repeat: true
            running: multiModModal.opened
            onTriggered: if (!Downloads.hasInstallDecision(multiModModal.itemRef)) multiModModal.finish("cancel")
        }
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
            visible: multiModModal.fileLabel !== ""
            text: I18n.format("main.multiMod.file", {file: multiModModal.fileLabel, type: multiModModal.fileTypeLabel})
            color: Theme.textSecondary
            font.pixelSize: Typography.small
            font.family: Theme.fontFamily
            wrapMode: Text.WrapAnywhere
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
        footer: [
            PrimaryButton {
                text: I18n.t("main.multiMod.addMods")
                onClicked: multiModModal.finish("mods")
            },
            SecondaryButton {
                text: I18n.t("main.multiMod.createInstance")
                onClicked: multiModModal.finish("instance")
            },
            SecondaryButton {
                text: I18n.t("common.confirm.cancel")
                onClicked: multiModModal.finish("cancel")
            }
        ]
    }

    // ---- nowe wydanie programu (GitHub Releases) ------------------------- #
    AppUpdateModal {
        id: appUpdateModal
    }

    Connections {
        target: AppUpdates
        function onUpdateAvailable(version, notes, url) {
            appUpdateModal.show(version, notes, url)
        }
        function onUpToDate(version) {
            toasts.show(I18n.format("toast.appUpdate.upToDate", {version: version}), "success")
        }
        function onCheckFailed(error) {
            toasts.show(I18n.format("toast.appUpdate.failed", {error: error}), "warning")
        }
    }

    Connections {
        target: Downloads
        function onInstallTargetRequired(itemRef, title, fileLabel, fileType, count) {
            multiModModal.enqueue(itemRef, title, fileLabel, fileType, count)
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

    // Existing Ctrl+1..9 bindings stay unchanged for backwards compatibility;
    // navigation to a grouped page automatically expands its sidebar section.
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
            // "steam-releases" otwiera dedykowany obszar zarządzania wydaniami Steam.
            // "game-versions" pozostaje aliasem zgodności dla starszych screenshotów/argumentów.
            // pozostałe wartości = drawer szczegółów moda
            if (dm === "steam-releases" || dm === "game-versions")
                Qt.callLater(() => pageStack.go("steam_releases"))
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
