import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "profiles"
    maxWidth: 1080

    // ------------------------------------------------------------------ #
    // instance editing (migration stage 6)
    // ------------------------------------------------------------------ #
    // sugestia katalogu podąża za nazwą TYLKO dla nowej instancji i dopóki
    // użytkownik ręcznie nie zmienił pola katalogu
    property bool dirTouched: false
    property bool settingDir: false

    // responsywna siatka: 1 kolumna przy waskim oknie, 2 przy szerokim
    property string filterMode: "all"
    property string sortMode: "created"
    property bool reverseSort: true
    property string viewMode: "grid"  // grid, list or spotlight
    readonly property int gridColumns: viewMode === "list" || viewMode === "spotlight"
                                       ? 1 : (width > 1000 ? 2 : 1)
    onFilterModeChanged: syncBrowser()
    onSortModeChanged: syncBrowser()
    onReverseSortChanged: syncBrowser()
    Component.onCompleted: syncBrowser()

    function syncBrowser() {
        Profiles.setBrowserOptions(filterMode, sortMode, reverseSort)
    }

    function durationText(seconds) {
        const minutes = Math.floor(Math.max(0, seconds) / 60)
        const hours = Math.floor(minutes / 60)
        if (!hours) return I18n.format("instances.playtime.minutes", {count: minutes})
        if (minutes % 60 === 0) return I18n.format("instances.playtime.hours", {count: hours})
        return I18n.format("instances.playtime.hoursMinutes", {hours: hours, minutes: minutes % 60})
    }

    // blokada zawartości strony na czas JAKIEGOKOLWEGO modala + 600 ms po
    // zamknięciu (doklik/fade-out nie trafia w karty pod spodem) - D24.
    // Deklaratywnie: odblokowana na starcie (bez modali), lock na otwarcie,
    // 600 ms grace po zamknięciu.
    readonly property bool anyModalOpen: editorModal.opened || deleteInstanceModal.opened || logsModal.opened || sandboxModal.opened || sandboxInstancePicker.opened
    readonly property bool contentLocked: anyModalOpen || unlockTimer.running
    onAnyModalOpenChanged: if (!anyModalOpen) unlockTimer.restart()
    Timer {
        id: unlockTimer
        interval: 600
    }

    function widthForColumns() {
        const spacing = Dimensions.spacingLg
        const usable = profileFlow.width - spacing * (gridColumns - 1)
        return usable / gridColumns
    }

    function syncDirSuggestion() {
        if (dirTouched || settingDir || editorModal.instanceId !== "")
            return
        settingDir = true
        editorDataDir.text = Profiles.suggestDataDir(editorName.text.trim())
        settingDir = false
    }

    // mody per instancja (krok 7.5): lista w dialogu edycji
    property var editorMods: []

    function loadEditorMods() {
        if (editorModal.instanceId !== "")
            editorMods = Profiles.instanceModStates(editorModal.instanceId)
    }

    Timer {
        id: editorReloadTimer
        interval: 700
        onTriggered: page.loadEditorMods()
    }

    function setEditorMod(modId, enabled) {
        // aktywacja + natychmiastowa przebudowa folderu Mods instancji
        Profiles.setInstanceModEnabled(editorModal.instanceId, modId, enabled)
        Profiles.buildModsFor(editorModal.instanceId)
        editorReloadTimer.restart()
    }

    function openSandboxForBranch(branch) {
        const matches = Profiles.sandboxInstancesForBranch(branch)
        if (matches.length === 0) {
            Bus.toast(I18n.t("instances.sandbox.noInstanceForBranch"), "info")
        } else if (matches.length === 1) {
            sandboxModal.openFor(matches[0].id)
        } else {
            sandboxInstancePicker.options = matches.map(m => ({value: m.id, label: m.label}))
            sandboxInstancePicker.selectedId = matches[0].id
            sandboxInstancePicker.open()
        }
    }

    function openEditor(instanceId) {
        editorModFilter = "all"
        editorModsSearch.text = ""
        const d = Profiles.profileDetails(instanceId)
        editorModal.instanceId = instanceId
        editorModal.isDefault = d.isDefault === true
        dirTouched = true
        settingDir = true
        editorName.text = d.name || ""
        editorDesc.text = d.description || ""
        editorDataDir.text = d.dataDir || ""
        editorBranch.value = d.gameBranch || ""
        Protons.refreshInstalled()
        editorProton.value = d.protonPath || ""
        editorExecutable.value = d.executable || ""
        GameVersions.refreshAvailable()
        noeosCheck.checked = d.noeos === true
        noeacCheck.checked = d.noeac === true
        skipNewsCheck.checked = d.skipNewsScreen === true
        skipIntroCheck.checked = d.skipIntro === true
        settingDir = false
        loadEditorMods()
        editorModal.open()
    }

    function openNew() {
        editorModFilter = "all"
        editorModsSearch.text = ""
        editorMods = []
        editorModal.instanceId = ""
        editorModal.isDefault = false
        dirTouched = false
        settingDir = true
        editorName.text = ""
        editorDesc.text = ""
        editorDataDir.text = Profiles.suggestDataDir("")
        editorBranch.value = ""
        Protons.refreshInstalled()
        editorProton.value = ""
        editorExecutable.value = ""
        GameVersions.refreshAvailable()
        noeosCheck.checked = true
        noeacCheck.checked = false
        skipNewsCheck.checked = true
        skipIntroCheck.checked = true
        settingDir = false
        editorModal.open()
    }

    function saveEditor() {
        // idempotencja: podwójne zamknięcie (Esc/X + closeRequested) nie
        // może zapisać dwa razy
        if (!editorModal.opened)
            return
        if (editorModal.instanceId !== "") {
            Profiles.updateInstance(editorModal.instanceId, editorName.text.trim(),
                                    editorDataDir.text.trim(), editorDesc.text.trim(),
                                    noeosCheck.checked, noeacCheck.checked,
                                    skipNewsCheck.checked, skipIntroCheck.checked,
                                    editorBranch.value, editorProton.value, editorExecutable.value)
            editorModal.close()
            return
        }
        // tworzenie: modal zostaje otwarty przy bledzie walidacji (toast
        // z przyczyna pokazuje sie obok), zeby user nie stracil wpisywanych danych
        if (Profiles.createInstance(editorName.text.trim(), editorDataDir.text.trim(),
                                    editorDesc.text.trim(), noeosCheck.checked,
                                    noeacCheck.checked, skipNewsCheck.checked,
                                    skipIntroCheck.checked, editorBranch.value, editorProton.value)) {
            editorModal.close()
        }
    }

    // ------------------------------------------------------------------ #
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingXl


        // modale są poza tym layoutem - blokada nie dotyka ich samych
        enabled: !contentLocked

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            RowLayout {
                spacing: 10

                Icon { name: "clock"; size: 19; tint: Theme.accent }
                ColumnLayout {
                    spacing: 2
                    Text {
                        text: I18n.t("instances.playtime.libraryTotal")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                    }
                    RowLayout {
                        spacing: 18
                        Text {
                            text: page.durationText(Profiles.totalPlaySeconds)
                            color: Theme.text
                            font.pixelSize: Typography.h2
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                        }
                        Text {
                            text: I18n.format("instances.playtime.playedCount", {played: Profiles.playedInstancesCount, total: Profiles.count})
                            color: Theme.textSecondary
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            Layout.alignment: Qt.AlignBottom
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true }

            PrimaryButton {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                text: Game.isRunning ? I18n.t("instances.stopGame.confirm") : I18n.t("instances.newInstance")
                icon: Game.isRunning ? "x-circle" : "plus"
                danger: Game.isRunning
                onClicked: {
                    if (Game.isRunning)
                        stopGameModal.ask(I18n.t("instances.stopGame.title"),
                            I18n.t("instances.stopGame.message"),
                            I18n.t("instances.stopGame.confirm"), true)
                    else
                        page.openNew()
                }
            }
        }

        // Sort/filter row is next to the new-instance controls, not hidden
        // in Settings. The ordering does not modify instances.json.
        RowLayout {
            Layout.fillWidth: true
            spacing: 9
            DropdownButton {
                Layout.preferredWidth: 195
                compact: true
                value: page.filterMode
                options: [
                    {value: "all", label: I18n.t("instances.filter.all"), icon: "layers"},
                    {value: "favorites", label: I18n.t("instances.filter.favorites"), icon: "star"},
                    {value: "played", label: I18n.t("instances.filter.played"), icon: "clock"},
                    {value: "unplayed", label: I18n.t("instances.filter.unplayed"), icon: "minus"},
                    {value: "recent", label: I18n.t("instances.filter.recent"), icon: "activity"},
                    {value: "running", label: I18n.t("instances.filter.running"), icon: "play"}
                ]
                onPicked: (v) => page.filterMode = v
            }
            DropdownButton {
                Layout.preferredWidth: 184
                compact: true
                value: page.sortMode
                options: [
                    {value: "created", label: I18n.t("instances.sort.created"), icon: "calendar"},
                    {value: "last", label: I18n.t("instances.sort.last"), icon: "clock"},
                    {value: "playtime", label: I18n.t("instances.sort.playtime"), icon: "activity"},
                    {value: "name", label: I18n.t("instances.sort.name"), icon: "tag"},
                    {value: "mods", label: I18n.t("instances.sort.mods"), icon: "package"}
                ]
                onPicked: (v) => page.sortMode = v
            }
            IconButton {
                icon: page.reverseSort ? "arrow-down" : "arrow-up"
                tooltip: page.reverseSort ? I18n.t("instances.sort.descending") : I18n.t("instances.sort.ascending")
                tint: Theme.text
                onClicked: page.reverseSort = !page.reverseSort
            }
            Item { Layout.fillWidth: true }
            Repeater {
                model: [
                    {value: "grid", icon: "grid", key: "instances.view.grid"},
                    {value: "list", icon: "list", key: "instances.view.list"},
                    {value: "spotlight", icon: "layout", key: "instances.view.spotlight"}
                ]
                Rectangle {
                    required property var modelData
                    width: 37
                    height: 36
                    radius: 9
                    color: page.viewMode === modelData.value ? Theme.accentSoft : Theme.bg2
                    border.width: 1
                    border.color: page.viewMode === modelData.value ? Theme.accent : Theme.border
                    IconButton {
                        anchors.centerIn: parent
                        icon: modelData.icon
                        iconSize: 17
                        buttonSize: 32
                        tint: page.viewMode === modelData.value ? Theme.accent : Theme.textSecondary
                        tooltip: I18n.t(modelData.key)
                        onClicked: page.viewMode = modelData.value
                    }
                }
            }
        }

        // ---- instance grid ---------------------------------------------- #
        AppScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
                contentHeight: profileFlow.height

            Flow {
                id: profileFlow
                width: Math.min(parent.width, page.contentWidth)
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: Dimensions.spacingLg

                Repeater {
                    model: Profiles.browserModel

                    Item {
                        id: profileDelegate
                        required property string profileId
                        required property string name
                        required property string description
                        required property string dataDir
                        required property bool isDefault
                        required property string flagsText
                        required property bool isRunning
                        required property int modCount
                        required property int enabledCount
                        required property string createdText
                        required property bool isActive
                        required property string colorTag
                        required property string gameBranch
                        required property string protonPath
                        required property bool favorite
                        required property int totalPlaySeconds
                        required property real lastPlayedEpoch

                        width: widthForColumns()
                        height: page.viewMode === "list" ? 160 : (page.viewMode === "spotlight" ? 260 : 226)

                        ProfileCard {
                            anchors.fill: parent
                            profileId: profileDelegate.profileId
                            name: profileDelegate.name
                            description: profileDelegate.description
                            dataDirDisplay: profileDelegate.dataDir
                            isDefault: profileDelegate.isDefault
                            flagsText: profileDelegate.flagsText
                            isRunning: profileDelegate.isRunning
                            modCount: profileDelegate.modCount
                            enabledCount: profileDelegate.enabledCount
                            createdText: profileDelegate.createdText
                            isActive: profileDelegate.isActive
                            colorTag: profileDelegate.colorTag
                            gameBranch: profileDelegate.gameBranch
                            protonPath: profileDelegate.protonPath
                            favorite: profileDelegate.favorite
                            totalPlaySeconds: profileDelegate.totalPlaySeconds
                            lastPlayedEpoch: profileDelegate.lastPlayedEpoch
                            viewMode: page.viewMode

                            onFavoriteToggled: Profiles.toggleFavorite(profileDelegate.profileId)
                            onSandboxRequested: sandboxModal.openFor(profileDelegate.profileId)
                            onLaunchRequested: Profiles.launchInstance(profileDelegate.profileId)
                            onActivateRequested: Profiles.activate(profileDelegate.profileId)
                            onBuildModsRequested: Profiles.buildModsFor(profileDelegate.profileId)
                            onLogsRequested: logsModal.showFor(profileDelegate.profileId)
                            onEditRequested: page.openEditor(profileDelegate.profileId)
                            onOpenFolderRequested: Profiles.openDataFolder(profileDelegate.profileId)
                            onDuplicateRequested: Profiles.duplicate(profileDelegate.profileId)
                            onRemoveRequested: {
                                deleteInstanceModal.instanceToDelete = profileDelegate.profileId
                                deleteInstanceModal.instanceNameToDelete = profileDelegate.name
                                deleteInstanceModal.ask(
                                    I18n.t("instances.delete.title"),
                                    I18n.format("instances.delete.message", {name: profileDelegate.name}),
                                    I18n.t("instances.delete.confirm"), true)
                            }
                        }
                    }
                }

                // new instance card
                Item {
                    width: widthForColumns()
                    implicitHeight: 236

                    Rectangle {
                        anchors.fill: parent
                        radius: Dimensions.radiusLg
                        color: hoverCard.hovered ? Theme.bg2 : "transparent"
                        border.width: 2
                        border.color: hoverCard.hovered ? Theme.rgba(Theme.accent, 0.55) : Theme.border

                        Behavior on border.color { ColorAnimation { duration: Theme.fast } }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 8

                        Icon {
                            name: "plus"
                            size: 26
                            tint: hoverCard.hovered ? Theme.accent : Theme.textSecondary
                            Layout.alignment: Qt.AlignHCenter
                        }

                        Text {
                            text: I18n.t("instances.createNew")
                            color: Theme.textSecondary
                            font.pixelSize: Typography.small + 0.5
                            font.weight: Font.Medium
                            font.family: Theme.fontFamily
                            Layout.alignment: Qt.AlignHCenter
                        }
                    }

                    HoverHandler { id: hoverCard }
                    TapHandler { gesturePolicy: TapHandler.ReleaseWithinBounds; onTapped: page.openNew() }
                }
            }
        }
    }

    // ---- folder picker for the editor ------------------------------------ #
    FolderPickerModal {
        id: editorDirDialog
        pickerTitle: I18n.t("instances.folderPicker.title")
        confirmText: I18n.t("folderPicker.chooseFolder")
        onFolderPicked: function(path) { editorDataDir.text = path }
    }

    // ---- create / edit modal ---------------------------------------------- #
    // Jeden wspólny edytor dla "Nowa instancja" i "Edytuj instancję".
    // Przy tworzeniu prawa kolumna (menedżer modów) jest ukryta - mody
    // wybiera się dopiero po utworzeniu instancji - więc karta jest węższa.
    Modal {
        id: editorModal
        cardWidth: editorModal.isNew ? 620 : 1120
        title: editorModal.instanceId !== "" ? I18n.t("instances.editor.editTitle") : I18n.t("instances.editor.newTitle")
        iconName: editorModal.instanceId !== "" ? "edit" : "plus"
        closeHandler: function() {
            if (editorModal.instanceId !== "")
                page.saveEditor()
            else
                editorModal.close()
        }

        property string instanceId: ""
        property bool isDefault: false

        readonly property bool isNew: instanceId === ""
        readonly property int modTotal: editorMods.length
        readonly property int modManaged: editorMods.filter(m => m.managed).length
        readonly property int modEnabled: editorMods.filter(m => m.managed && m.enabled).length
        readonly property int modDisabled: editorMods.filter(m => m.managed && !m.enabled).length
        readonly property int modManual: editorMods.filter(m => !m.managed).length

        // panel wysokości jest stałe, dzięki czemu układ nie skacze przy
        // zmianie filtra lub liczby modów
        readonly property real editorHeight: 600

        function filteredMods() {
            const needle = editorModsSearch.text.trim().toLowerCase()
            let items = editorMods
            if (editorModFilter === "enabled")
                items = items.filter(m => m.managed && m.enabled)
            else if (editorModFilter === "disabled")
                items = items.filter(m => m.managed && !m.enabled)
            else if (editorModFilter === "manual")
                items = items.filter(m => !m.managed)

            if (needle !== "")
                items = items.filter(m => (m.name || "").toLowerCase().indexOf(needle) >= 0)

            // Zarządzane mody na górze, potem ręczne. W obrębie grupy
            // zachowujemy czytelność przez nazwę.
            return items.slice().sort((a, b) => {
                if (a.managed !== b.managed)
                    return a.managed ? -1 : 1
                if (a.enabled !== b.enabled)
                    return a.enabled ? -1 : 1
                return (a.name || "").localeCompare(b.name || "", "pl")
            })
        }

        function setLocalMod(modId, enabled) {
            const next = editorMods.slice()
            for (let i = 0; i < next.length; i++) {
                if (next[i].modId === modId && next[i].managed) {
                    const copy = Object.assign({}, next[i])
                    copy.enabled = enabled
                    next[i] = copy
                    break
                }
            }
            editorMods = next
        }

        function bulkSet(enabled) {
            if (isNew || editorModal.instanceId === "" || modManaged === 0)
                return

            Profiles.setInstanceModsEnabled(editorModal.instanceId, enabled)
            const next = editorMods.map(m => {
                if (!m.managed)
                    return m
                const copy = Object.assign({}, m)
                copy.enabled = enabled
                return copy
            })
            editorMods = next
            Profiles.buildModsFor(editorModal.instanceId)
            editorReloadTimer.restart()
        }

        function refreshMods() {
            page.loadEditorMods()
        }

        function openModInfo(mod) {
            Bus.toast(I18n.format("instances.mod.toast", {
                          name: mod.name,
                          state: I18n.t(!mod.managed ? "instances.mod.toast.manual" : (mod.enabled ? "instances.mod.toast.enabled" : "instances.mod.toast.disabled"))
                      }), "info")
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: editorModal.editorHeight
            spacing: 18

            // ================================================================
            // LEWA: dane instancji + ustawienia uruchamiania
            // ================================================================
            AppScrollView {
                Layout.fillWidth: true
                Layout.preferredWidth: 530
                Layout.fillHeight: true
                contentHeight: editorLeft.implicitHeight
                clip: true

                ColumnLayout {
                    id: editorLeft
                    width: parent.width
                    spacing: 12

                // compact status header
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 58
                    radius: Dimensions.radiusMd
                    color: Theme.rgba(editorModal.isNew ? Theme.accent : Theme.info, 0.08)
                    border.width: 1
                    border.color: Theme.rgba(editorModal.isNew ? Theme.accent : Theme.info, 0.24)

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        spacing: 10

                        Rectangle {
                            width: 34
                            height: 34
                            radius: 10
                            color: Theme.rgba(editorModal.isNew ? Theme.accent : Theme.info, 0.15)
                            border.width: 1
                            border.color: Theme.rgba(editorModal.isNew ? Theme.accent : Theme.info, 0.28)

                            Icon {
                                anchors.centerIn: parent
                                name: editorModal.isNew ? "plus" : "layers"
                                size: 17
                                tint: editorModal.isNew ? Theme.accent : Theme.info
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                Layout.fillWidth: true
                                text: editorModal.isNew ? I18n.t("instances.editor.newStatus") : I18n.t("instances.editor.status")
                                color: Theme.text
                                font.pixelSize: Typography.body
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                            }
                            Text {
                                Layout.fillWidth: true
                                text: editorModal.isNew
                                      ? I18n.t("instances.editor.newDescription")
                                      : (editorModal.isDefault
                                         ? I18n.t("instances.editor.defaultDescription")
                                         : I18n.t("instances.editor.existingDescription"))
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                            }
                        }

                        StatusBadge {
                            key: editorModal.isNew ? "info" : (editorModal.isDefault ? "warning" : "enabled")
                            label: editorModal.isNew ? I18n.t("instances.editor.draft") : (editorModal.isDefault ? I18n.t("instances.editor.default") : I18n.t("instances.editor.instance"))
                        }
                    }
                }

                // ---------------- dane podstawowe --------------------------
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 390
                    radius: Dimensions.radiusMd
                    color: Theme.bg2
                    border.width: 1
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Icon { name: "file-text"; size: 15; tint: Theme.accent }
                            Text {
                                text: I18n.t("instances.info.title")
                                color: Theme.text
                                font.pixelSize: Typography.h3
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: I18n.t("instances.info.nameDescription")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 5
                                Text { text: I18n.t("instances.info.name"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                                AppTextField {
                                    id: editorName
                                    Layout.fillWidth: true
                                    placeholder: I18n.t("instances.info.namePlaceholder")
                                    onTextChanged: page.syncDirSuggestion()
                                }
                            }

                            ColumnLayout {
                                Layout.preferredWidth: 104
                                Layout.fillWidth: false
                                spacing: 5
                                Text { text: I18n.t("instances.info.mods"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: Dimensions.controlH
                                    radius: 9
                                    color: Theme.bg3
                                    border.width: 1
                                    border.color: Theme.border

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 8
                                        Text {
                                            text: editorModal.isNew ? "-" : (editorModal.modEnabled + " / " + editorModal.modManaged)
                                            color: Theme.text
                                            font.pixelSize: Typography.body
                                            font.weight: Font.Medium
                                            font.family: Theme.fontFamily
                                            Layout.fillWidth: true
                                        }
                                        Icon {
                                            name: "package"
                                            size: 15
                                            tint: Theme.textSecondary
                                        }
                                    }
                                }
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            Text { text: I18n.t("instances.info.description"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                            AppTextField {
                                id: editorDesc
                                Layout.fillWidth: true
                                placeholder: I18n.t("instances.info.descriptionPlaceholder")
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            Text {
                                text: I18n.t("instances.gameVersion.label")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                            }
                            DropdownButton {
                                Layout.fillWidth: true
                                options: [{ value: "", label: I18n.t("instances.gameVersion.default") }]
                                         .concat(GameVersions.branchChoices.map(function (v) {
                                             var gb = v.size_bytes > 0
                                                      ? (v.size_bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB"
                                                      : ""
                                             return { value: v.branch,
                                                      label: v.branch + (gb !== "" ? "  ·  " + gb : "") }
                                         }))
                                value: editorBranch.value
                                onPicked: (value) => editorBranch.value = value
                            }
                            Text {
                                text: I18n.t("instances.gameVersion.help")
                                color: Theme.textMuted
                                font.pixelSize: Typography.micro
                                font.family: Theme.fontFamily
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            visible: !editorModal.isNew
                            Text { text: I18n.t("instances.executable.label"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                            DropdownButton {
                                Layout.fillWidth: true
                                options: [{value: "", label: I18n.t("instances.executable.default")}]
                                    .concat(Profiles.executableOptions(editorBranch.value))
                                    .concat(editorExecutable.value !== "" && !Profiles.executableOptions(editorBranch.value).some(e => e.value === editorExecutable.value)
                                        ? [{value: editorExecutable.value, label: editorExecutable.value}] : [])
                                value: editorExecutable.value
                                onPicked: value => editorExecutable.value = value
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            Text { text: I18n.t("protons.label"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                            DropdownButton {
                                Layout.fillWidth: true
                                options: [{value: "", label: I18n.t("protons.automatic")}]
                                    .concat(Protons.installed.map(p => ({value: p.path, label: p.name})))
                                    .concat(editorProton.value !== "" && !Protons.installed.some(p => p.path === editorProton.value)
                                        ? [{value: editorProton.value, label: I18n.t("protons.missing") + " · " + editorProton.value}] : [])
                                value: editorProton.value
                                onPicked: value => editorProton.value = value
                            }
                            Text { Layout.fillWidth: true; text: I18n.t("protons.selectionHelp"); color: Theme.textMuted; font.pixelSize: Typography.micro; wrapMode: Text.Wrap }
                        }

                    }
                }

                // ---------------- katalog danych ---------------------------
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 124
                    radius: Dimensions.radiusMd
                    color: Theme.bg2
                    border.width: 1
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 8

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Icon { name: "folder"; size: 15; tint: Theme.info }
                            Text { text: I18n.t("instances.dataDir.title"); color: Theme.text; font.pixelSize: Typography.h3; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                            Item { Layout.fillWidth: true }
                            Text {
                                text: I18n.t("instances.dataDir.meta")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            AppTextField {
                                id: editorDataDir
                                Layout.fillWidth: true
                                placeholder: I18n.t("instances.dataDir.placeholder")
                                enabled: !editorModal.isDefault
                                onTextChanged: if (!settingDir) dirTouched = true
                            }
                            SecondaryButton {
                                text: I18n.t("instances.dataDir.select")
                                icon: "folder"
                                compact: true
                                enabled: !editorModal.isDefault
                                onClicked: editorDirDialog.openAt(editorDataDir.text || FileBrowser.homePath)
                            }
                        }

                        Text {
                            visible: editorModal.isDefault
                            Layout.fillWidth: true
                            text: I18n.t("instances.dataDir.defaultNotice")
                            color: Theme.warning
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            elide: Text.ElideRight
                        }
                    }
                }

                // ---------------- ustawienia piaskownicy -------------------
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 96
                    visible: !editorModal.isNew && Profiles.sandboxSupportsBranch(editorBranch.value)
                    radius: Dimensions.radiusMd
                    color: Theme.bg2
                    border.width: 1
                    border.color: Theme.border
                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 5
                            Text {
                                text: I18n.t("instances.sandbox.title")
                                color: Theme.text
                                font.pixelSize: Typography.h3
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }
                            Text {
                                text: I18n.t("instances.sandbox.hint")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                                wrapMode: Text.Wrap
                                Layout.fillWidth: true
                            }
                        }
                        SecondaryButton {
                            text: I18n.t("instances.sandbox.open")
                            icon: "sliders"
                            compact: true
                            onClicked: sandboxModal.openFor(editorModal.instanceId)
                        }
                    }
                }

                // ---------------- flagi ------------------------------------
                Rectangle {
                    Layout.fillWidth: true
                    // stała wysokość: w AppScrollView fillHeight nie działa
                    // (layout nie przydziela nadmiaru) - sekcja by się zwinęła
                    implicitHeight: 232
                    radius: Dimensions.radiusMd
                    color: Theme.bg2
                    border.width: 1
                    border.color: Theme.border

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 9

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Icon { name: "sliders"; size: 15; tint: Theme.accent }
                            Text { text: I18n.t("instances.launchOptions.title"); color: Theme.text; font.pixelSize: Typography.h3; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                            Item { Layout.fillWidth: true }
                            Text { text: I18n.t("instances.launchOptions.subtitle"); color: Theme.textMuted; font.pixelSize: Typography.caption; font.family: Theme.fontFamily }
                        }

                        GridLayout {
                            Layout.fillWidth: true
                            columns: 2
                            rowSpacing: 6
                            columnSpacing: 12

                            Repeater {
                                model: [
                                    { key: "noeos", code: "-noeos", titleKey: "instances.launchOptions.noeos", hintKey: "instances.launchOptions.noeosHint", ref: noeosCheck },
                                    { key: "noeac", code: "-noeac", titleKey: "instances.launchOptions.noeac", hintKey: "instances.launchOptions.noeacHint", ref: noeacCheck },
                                    { key: "skipNews", code: "-skipnewsscreen=true", titleKey: "instances.launchOptions.skipNews", hintKey: "instances.launchOptions.skipNewsHint", ref: skipNewsCheck },
                                    { key: "skipIntro", code: "-skipintro", titleKey: "instances.launchOptions.skipIntro", hintKey: "instances.launchOptions.skipIntroHint", ref: skipIntroCheck }
                                ]

                                RowLayout {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    spacing: 8

                                    ToggleSwitch {
                                        checked: modelData.ref.checked
                                        onToggled: (c) => modelData.ref.checked = c
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        spacing: 1
                                        Text {
                                            Layout.fillWidth: true
                                            text: I18n.t(modelData.titleKey)
                                            color: Theme.text
                                            font.pixelSize: Typography.small
                                            font.weight: Font.Medium
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: I18n.t(modelData.hintKey) + " · " + modelData.code
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.micro
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: 54
                            radius: 9
                            color: Theme.bg3
                            border.width: 1
                            border.color: Theme.border

                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 3
                                Text { text: I18n.t("instances.launchOptions.commandPreview"); color: Theme.textMuted; font.pixelSize: Typography.micro; font.family: Theme.fontFamily }
                                Text {
                                    Layout.fillWidth: true
                                    text: {
                                        let args = []
                                        if (editorDataDir.text.trim() !== "")
                                            args.push('"-UserDataFolder=Z:' + editorDataDir.text.trim() + '"')
                                        if (noeosCheck.checked) args.push("-noeos")
                                        if (noeacCheck.checked) args.push("-noeac")
                                        if (skipNewsCheck.checked) args.push("-skipnewsscreen=true")
                                        if (skipIntroCheck.checked) args.push("-skipintro")
                                        return args.length > 0 ? "%command% " + args.join(" ") : "%command%"
                                    }
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideMiddle
                                }
                            }
                        }
                    }
                }
            }
            }

            // pionowy separator jako wizualny "kręgosłup" okna
            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                visible: !editorModal.isNew
                color: Theme.border
            }

            // ================================================================
            // PRAWA: menedżer modów instancji
            // ================================================================
            ColumnLayout {
                id: editorRight
                visible: !editorModal.isNew
                Layout.preferredWidth: 520
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignTop
                spacing: 10

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Rectangle {
                        width: 36
                        height: 36
                        radius: 10
                        color: Theme.accentSoft
                        border.width: 1
                        border.color: Theme.rgba(Theme.accent, 0.28)
                        Icon { anchors.centerIn: parent; name: "package"; size: 17; tint: Theme.accent }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            text: I18n.t("instances.mods.title")
                            color: Theme.text
                            font.pixelSize: Typography.h2
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                        }
                        Text {
                            Layout.fillWidth: true
                            text: editorModal.isNew
                                  ? I18n.t("instances.mods.newCaption")
                                  : I18n.t("instances.mods.existingCaption")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            elide: Text.ElideRight
                        }
                    }

                    IconButton {
                        icon: "refresh-cw"
                        buttonSize: 32
                        iconSize: 15
                        tooltip: I18n.t("instances.mods.refresh")
                        enabled: !editorModal.isNew && !Game.isRunning
                        onClicked: editorModal.refreshMods()
                    }

                    StatusBadge {
                        visible: Game.isRunning
                        key: "warning"
                        label: I18n.t("instances.mods.running")
                    }
                }

                // mini statystyki
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 7

                    Rectangle {
                        Layout.fillWidth: true
                        height: 50
                        radius: 10
                        color: Theme.bg2
                        border.width: 1
                        border.color: Theme.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 7
                            anchors.bottomMargin: 7
                            spacing: 1
                            Text { text: editorModal.isNew ? "-" : editorModal.modManaged; color: Theme.text; font.pixelSize: Typography.body + 1; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                            Text { text: I18n.t("instances.stats.managed"); color: Theme.textMuted; font.pixelSize: Typography.micro; font.family: Theme.fontFamily }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 50
                        radius: 10
                        color: Theme.successSoft
                        border.width: 1
                        border.color: Theme.rgba(Theme.success, 0.22)
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 7
                            anchors.bottomMargin: 7
                            spacing: 1
                            Text { text: editorModal.isNew ? "-" : editorModal.modEnabled; color: Theme.success; font.pixelSize: Typography.body + 1; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                            Text { text: I18n.t("instances.stats.enabled"); color: Theme.textMuted; font.pixelSize: Typography.micro; font.family: Theme.fontFamily }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 50
                        radius: 10
                        color: Theme.bg2
                        border.width: 1
                        border.color: Theme.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 7
                            anchors.bottomMargin: 7
                            spacing: 1
                            Text { text: editorModal.isNew ? "-" : editorModal.modDisabled; color: Theme.textSecondary; font.pixelSize: Typography.body + 1; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                            Text { text: I18n.t("instances.stats.disabled"); color: Theme.textMuted; font.pixelSize: Typography.micro; font.family: Theme.fontFamily }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        height: 50
                        radius: 10
                        color: Theme.bg2
                        border.width: 1
                        border.color: Theme.border
                        ColumnLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.topMargin: 7
                            anchors.bottomMargin: 7
                            spacing: 1
                            Text { text: editorModal.isNew ? "-" : editorModal.modManual; color: Theme.textSecondary; font.pixelSize: Typography.body + 1; font.weight: Font.DemiBold; font.family: Theme.fontFamily }
                            Text { text: I18n.t("instances.stats.manual"); color: Theme.textMuted; font.pixelSize: Typography.micro; font.family: Theme.fontFamily }
                        }
                    }
                }

                // wyszukiwarka + akcje masowe
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    AppTextField {
                        id: editorModsSearch
                        Layout.fillWidth: true
                        placeholder: I18n.t("instances.mods.searchPlaceholder")
                        enabled: !editorModal.isNew
                    }

                    SecondaryButton {
                        text: I18n.t("instances.mods.enable")
                        icon: "check"
                        compact: true
                        enabled: !editorModal.isNew && !Game.isRunning && editorModal.modManaged > 0
                        onClicked: editorModal.bulkSet(true)
                    }

                    SecondaryButton {
                        text: I18n.t("instances.mods.disable")
                        icon: "x"
                        compact: true
                        enabled: !editorModal.isNew && !Game.isRunning && editorModal.modManaged > 0
                        onClicked: editorModal.bulkSet(false)
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    FilterChip { label: I18n.t("instances.mods.filterAll"); count: editorModal.modTotal; active: editorModFilter === "all"; onClicked: editorModFilter = "all" }
                    FilterChip { label: I18n.t("instances.mods.filterEnabled"); count: editorModal.modEnabled; active: editorModFilter === "enabled"; onClicked: editorModFilter = "enabled" }
                    FilterChip { label: I18n.t("instances.mods.filterDisabled"); count: editorModal.modDisabled; active: editorModFilter === "disabled"; onClicked: editorModFilter = "disabled" }
                    FilterChip { label: I18n.t("instances.mods.filterManual"); count: editorModal.modManual; active: editorModFilter === "manual"; onClicked: editorModFilter = "manual" }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: editorModal.isNew ? "" : I18n.format(editorModal.filteredMods().length === 1 ? "instances.mods.results.one" : "instances.mods.results.many", {count: editorModal.filteredMods().length})
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: Dimensions.radiusMd
                    color: Theme.bg1
                    border.width: 1
                    border.color: Theme.border
                    clip: true

                    // New instance: ten sam panel, tylko stan pusty.
                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 22
                        visible: editorModal.isNew
                        spacing: 10

                        Item { Layout.fillHeight: true }
                        Rectangle {
                            width: 62
                            height: 62
                            radius: 18
                            color: Theme.accentSoft
                            border.width: 1
                            border.color: Theme.rgba(Theme.accent, 0.28)
                            Layout.alignment: Qt.AlignHCenter
                            Icon { anchors.centerIn: parent; name: "package"; size: 28; tint: Theme.accent }
                        }
                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: I18n.t("profiles.modsEmptyTitle")
                            color: Theme.text
                            font.pixelSize: Typography.h3 + 1
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                        }
                        Text {
                            Layout.fillWidth: true
                            Layout.maximumWidth: 360
                            Layout.alignment: Qt.AlignHCenter
                            text: I18n.t("profiles.modsEmptySubtitle")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption + 1
                            font.family: Theme.fontFamily
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                        }
                        Item { Layout.fillHeight: true }
                    }

                    ListView {
                        acceptedButtons: Qt.NoButton
                        id: editorModsList
                        anchors.fill: parent
                        anchors.margins: 6
                        visible: !editorModal.isNew
                        model: editorModal.filteredMods()
                        spacing: 5
                        clip: true
                        boundsBehavior: Flickable.StopAtBounds
                        flickDeceleration: 5200
                        maximumFlickVelocity: 1800
                        ScrollBar.vertical: AppScrollBar {
                            policy: ScrollBar.AsNeeded
                        }

                        WheelHandler {
                            target: null
                            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                            onWheel: (event) => {
                                const maxY = Math.max(0, editorModsList.contentHeight - editorModsList.height)
                                if (maxY <= 0) { event.accepted = false; return }
                                editorModsList.cancelFlick()
                                const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                                editorModsList.contentY = Math.max(0, Math.min(maxY, editorModsList.contentY - step))
                                event.accepted = true
                            }
                        }

                        delegate: Rectangle {
                            id: modRow
                            required property var modelData
                            width: editorModsList.width - 10
                            height: 66
                            radius: 10
                            color: modelData.managed
                                   ? (modelData.enabled ? Theme.rgba(Theme.success, 0.055) : Theme.bg2)
                                   : Theme.bg2
                            border.width: 1
                            border.color: modelData.managed && modelData.enabled
                                            ? Theme.rgba(Theme.success, 0.22)
                                            : Theme.border

                            Behavior on color { ColorAnimation { duration: Theme.fast } }
                            Behavior on border.color { ColorAnimation { duration: Theme.fast } }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 9
                                spacing: 10

                                Rectangle {
                                    width: 34
                                    height: 34
                                    radius: 9
                                    color: modelData.managed
                                           ? (modelData.enabled ? Theme.successSoft : Theme.bg3)
                                           : Theme.infoSoft
                                    border.width: 1
                                    border.color: modelData.managed
                                                   ? Theme.rgba(modelData.enabled ? Theme.success : Theme.borderHover, 0.25)
                                                   : Theme.rgba(Theme.info, 0.25)

                                    Icon {
                                        anchors.centerIn: parent
                                        name: modelData.managed ? "package" : "wrench"
                                        size: 16
                                        tint: modelData.managed
                                              ? (modelData.enabled ? Theme.success : Theme.textSecondary)
                                              : Theme.info
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 3

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 6
                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.name || modelData.modId
                                            color: modelData.managed && !modelData.enabled ? Theme.textMuted : Theme.text
                                            font.pixelSize: Typography.small + 0.5
                                            font.weight: Font.Medium
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            visible: (modelData.version || "") !== ""
                                            text: "v" + modelData.version
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.micro
                                            font.family: Theme.fontFamily
                                        }
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        spacing: 5

                                        StatusBadge {
                                            key: !modelData.managed ? "info" : (modelData.enabled ? "enabled" : "disabled")
                                            label: !modelData.managed ? I18n.t("instances.mod.status.manual") : (modelData.enabled ? I18n.t("instances.mod.status.enabled") : I18n.t("instances.mod.status.disabled"))
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: !modelData.managed
                                                  ? I18n.t("instances.mod.location.manual")
                                                  : (modelData.inFolder ? I18n.t("instances.mod.location.present") : I18n.t("instances.mod.location.ready"))
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.micro
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                    }
                                }

                                ToggleSwitch {
                                    visible: modelData.managed
                                    checked: modelData.enabled
                                    enabled: !Game.isRunning
                                    onToggled: (checked) => page.setEditorMod(modelData.modId, checked)
                                }

                                IconButton {
                                    icon: "info"
                                    buttonSize: 30
                                    iconSize: 14
                                    tooltip: I18n.t("instances.mod.info")
                                    onClicked: editorModal.openModInfo(modelData)
                                }
                            }

                            HoverHandler { id: modHover }
                            Rectangle {
                                anchors.left: parent.left
                                anchors.top: parent.top
                                anchors.bottom: parent.bottom
                                width: 3
                                radius: 2
                                color: modelData.managed
                                       ? (modelData.enabled ? Theme.success : Theme.textFaint)
                                       : Theme.info
                                opacity: modHover.hovered ? 1 : 0.55
                            }
                        }

                        Item {
                            anchors.fill: parent
                            visible: editorModal.filteredMods().length === 0

                            ColumnLayout {
                                anchors.centerIn: parent
                                width: Math.min(parent.width - 40, 360)
                                spacing: 8
                                Icon {
                                    name: editorModsSearch.text.trim() !== "" ? "search" : "package"
                                    size: 28
                                    tint: Theme.textFaint
                                    Layout.alignment: Qt.AlignHCenter
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: editorModsSearch.text.trim() !== ""
                                          ? I18n.t("instances.mods.emptySearch")
                                          : I18n.t("instances.mods.emptyAll")
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.h3
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                    horizontalAlignment: Text.AlignHCenter
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: editorModsSearch.text.trim() !== ""
                                          ? I18n.t("instances.mods.emptySearchHint")
                                          : I18n.t("instances.mods.emptyAllHint")
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }
                }

                Text {
                    Layout.fillWidth: true
                    visible: !editorModal.isNew && editorModal.modManual > 0
                    text: I18n.t("instances.mods.manualNote")
                    color: Theme.textMuted
                    font.pixelSize: Typography.micro
                    font.family: Theme.fontFamily
                    elide: Text.ElideRight
                }
            }
        }

        footer: [
            SecondaryButton {
                text: I18n.t("instances.footer.cancel")
                icon: "x"
                compact: false
                onClicked: editorModal.close()
                visible: editorModal.isNew
            },
            SecondaryButton {
                text: editorModal.isNew ? I18n.t("instances.footer.createClose") : I18n.t("instances.footer.save")
                icon: "check"
                disabled: editorName.text.trim() === ""
                onClicked: page.saveEditor()
            }
        ]
    }

    Modal {
        id: sandboxInstancePicker
        title: I18n.t("instances.sandbox.chooseInstance")
        iconName: "sliders"
        cardWidth: 480
        property var options: []
        property string selectedId: ""
        ColumnLayout {
            Layout.fillWidth: true
            DropdownButton {
                Layout.fillWidth: true
                value: sandboxInstancePicker.selectedId
                options: sandboxInstancePicker.options
                onPicked: value => sandboxInstancePicker.selectedId = value
            }
        }
        footer: [
            SecondaryButton {
                text: I18n.t("common.close")
                icon: "x"
                onClicked: sandboxInstancePicker.close()
            },
            PrimaryButton {
                text: I18n.t("instances.sandbox.open")
                icon: "sliders"
                disabled: sandboxInstancePicker.selectedId === ""
                onClicked: {
                    const id = sandboxInstancePicker.selectedId
                    sandboxInstancePicker.close()
                    sandboxModal.openFor(id)
                }
            }
        ]
    }

    // Czytnik piaskownicy jest osobnym oknem. Kod pozostaje w launcherze,
    // nigdy nie zapisujemy go do plików świata.
    Modal {
        id: sandboxModal
        cardWidth: 720
        title: I18n.t("instances.sandbox.title")
        iconName: "sliders"
        property string instanceId: ""
        property string worldId: ""
        property var availableWorlds: []
        property var preview: ({valid: false, groups: [], code: "", count: 0})
        property bool saveOk: false
        property bool copyOk: false

        function openFor(instanceId) {
            sandboxModal.instanceId = instanceId
            availableWorlds = Profiles.sandboxWorlds(instanceId)
            worldId = availableWorlds.length ? availableWorlds[0].id : ""
            sandboxInput.text = ""
            saveOk = false
            copyOk = false
            refresh()
            open()
        }
        function selectWorld(next) {
            worldId = next
            sandboxInput.text = ""
            saveOk = false
            copyOk = false
            refresh()
        }
        function refresh() {
            preview = worldId !== "" ? Profiles.sandboxInspect(instanceId, worldId, sandboxInput.text)
                                     : {valid: false, error: "no_world", groups: [], code: "", count: 0}
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                text: I18n.t("instances.sandbox.readOnly")
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: I18n.t("instances.sandbox.world")
                    color: Theme.textSecondary
                    font.pixelSize: Typography.body
                }

                DropdownButton {
                    Layout.fillWidth: true
                    value: sandboxModal.worldId
                    options: sandboxModal.availableWorlds.map(w => ({value: w.id, label: w.label}))
                    onPicked: value => sandboxModal.selectWorld(value)
                }
            }

            AppTextField {
                id: sandboxInput
                Layout.fillWidth: true
                enabled: sandboxModal.worldId !== ""
                placeholder: I18n.t("instances.sandbox.codePlaceholder")
                onAccepted: sandboxModal.refresh()
                onTextChanged: {
                    sandboxModal.saveOk = false
                    sandboxModal.copyOk = false
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SecondaryButton {
                    text: I18n.t("instances.sandbox.preview")
                    icon: "search"
                    compact: true
                    enabled: sandboxModal.worldId !== ""
                    onClicked: sandboxModal.refresh()
                }
                SecondaryButton {
                    text: I18n.t("instances.sandbox.save")
                    icon: "save"
                    compact: true
                    enabled: sandboxModal.worldId !== ""
                    onClicked: {
                        sandboxModal.saveOk = Profiles.saveSandboxCode(sandboxModal.instanceId,
                                                     sandboxModal.worldId, sandboxInput.text)
                        sandboxModal.refresh()
                    }
                }
                SecondaryButton {
                    text: I18n.t("instances.sandbox.fromGame")
                    icon: "refresh-cw"
                    compact: true
                    enabled: sandboxModal.worldId !== ""
                    onClicked: {
                        sandboxInput.text = ""
                        sandboxModal.saveOk = false
                        sandboxModal.copyOk = false
                        sandboxModal.refresh()
                    }
                }
                SecondaryButton {
                    text: I18n.t("instances.sandbox.copyCode")
                    icon: "copy"
                    compact: true
                    enabled: sandboxModal.preview.valid && sandboxModal.preview.code.length > 0
                    onClicked: sandboxModal.copyOk = Profiles.copySandboxCode(sandboxModal.preview.code)
                }
                Item { Layout.fillWidth: true }
                Text {
                    visible: sandboxModal.preview.valid
                    text: I18n.format("instances.sandbox.changed", {count: sandboxModal.preview.count})
                    color: Theme.accent
                    font.pixelSize: Typography.caption
                    font.weight: Font.DemiBold
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: sandboxModal.copyOk || sandboxModal.saveOk

                Rectangle {
                    radius: 7
                    color: Theme.rgba(Theme.success, 0.12)
                    border.width: 1
                    border.color: Theme.rgba(Theme.success, 0.28)
                    implicitHeight: 28
                    implicitWidth: statusText.implicitWidth + 20

                    Text {
                        id: statusText
                        anchors.centerIn: parent
                        text: sandboxModal.copyOk ? I18n.t("instances.sandbox.copied")
                              : sandboxModal.saveOk ? I18n.t("instances.sandbox.saved") : ""
                        color: Theme.success
                        font.pixelSize: Typography.caption
                        font.weight: Font.Medium
                    }
                }

                Item { Layout.fillWidth: true }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: sandboxModal.preview.valid
                implicitHeight: 52
                radius: 8
                color: Theme.bg3
                border.width: 1
                border.color: Theme.border

                TextEdit {
                    anchors.fill: parent
                    anchors.margins: 9
                    text: sandboxModal.preview.code || ""
                    readOnly: true
                    selectByMouse: true
                    wrapMode: TextEdit.WrapAnywhere
                    color: Theme.text
                    font.pixelSize: Typography.caption
                    font.family: Theme.fontFamily
                    clip: true
                }
            }

            Text {
                Layout.fillWidth: true
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                wrapMode: Text.Wrap
                text: sandboxModal.preview.valid
                      ? (sandboxModal.preview.source === "game"
                         ? I18n.t("instances.sandbox.sourceGame")
                         : sandboxModal.preview.source === "saved"
                           ? I18n.t("instances.sandbox.sourceSaved")
                           : I18n.t("instances.sandbox.sourceInput"))
                      : I18n.t("instances.sandbox.error." + (sandboxModal.preview.error || "no_code"))
            }

            Text {
                visible: sandboxModal.preview.valid && sandboxModal.preview.unknown.length > 0
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                color: Theme.warning
                text: I18n.t("instances.sandbox.unknown")
                font.pixelSize: Typography.caption
            }

            AppScrollView {
                Layout.fillWidth: true
                // Lista dopasowuje się do okna, zamiast wypychać modal poza ekran.
                Layout.preferredHeight: Math.max(120, Math.min(250, sandboxModal.height - 520))
                contentHeight: sandboxItems.implicitHeight

                ColumnLayout {
                    id: sandboxItems
                    width: parent.width
                    spacing: 12

                    Repeater {
                        model: sandboxModal.preview.groups || []

                        ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 6

                            Rectangle {
                                Layout.fillWidth: true
                                height: 28
                                radius: 7
                                color: Theme.bg3

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 10

                                    Text {
                                        text: I18n.language === "pl" ? modelData.pl : modelData.en
                                        color: Theme.text
                                        font.pixelSize: Typography.body
                                        font.weight: Font.DemiBold
                                    }
                                    Item { Layout.fillWidth: true }
                                    Text {
                                        text: String(modelData.entries.length)
                                        color: Theme.textMuted
                                        font.pixelSize: Typography.caption
                                    }
                                }
                            }

                            Repeater {
                                model: modelData.entries

                                Rectangle {
                                    required property var modelData
                                    Layout.fillWidth: true
                                    radius: 10
                                    color: Theme.bg1
                                    border.width: 1
                                    border.color: Theme.border
                                    implicitHeight: entryColumn.implicitHeight + 18

                                    ColumnLayout {
                                        id: entryColumn
                                        anchors.fill: parent
                                        anchors.margins: 9
                                        spacing: 6

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 10

                                            Text {
                                                Layout.fillWidth: true
                                                color: Theme.text
                                                font.pixelSize: Typography.body
                                                font.weight: Font.Medium
                                                text: I18n.language === "pl" ? modelData.pl : modelData.en
                                                wrapMode: Text.Wrap
                                            }

                                            Rectangle {
                                                radius: 8
                                                color: Theme.rgba(modelData.verified ? Theme.accent : Theme.warning, 0.12)
                                                border.width: 1
                                                border.color: Theme.rgba(modelData.verified ? Theme.accent : Theme.warning, 0.3)
                                                implicitHeight: 28
                                                implicitWidth: valueText.implicitWidth + 18

                                                Text {
                                                    id: valueText
                                                    anchors.centerIn: parent
                                                    color: modelData.verified ? Theme.accent : Theme.warning
                                                    font.pixelSize: Typography.caption
                                                    font.weight: Font.DemiBold
                                                    text: I18n.language === "pl" ? modelData.value_pl : modelData.value_en
                                                }
                                            }
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 8

                                            Rectangle {
                                                radius: 6
                                                color: Theme.bg3
                                                border.width: 1
                                                border.color: Theme.border
                                                implicitHeight: 22
                                                implicitWidth: codeText.implicitWidth + 14

                                                Text {
                                                    id: codeText
                                                    anchors.centerIn: parent
                                                    color: Theme.textMuted
                                                    font.pixelSize: Typography.micro
                                                    font.family: Theme.fontFamily
                                                    text: modelData.code
                                                }
                                            }

                                            Text {
                                                Layout.fillWidth: true
                                                color: Theme.textMuted
                                                font.pixelSize: Typography.caption
                                                text: I18n.language === "pl"
                                                      ? modelData.description_short_pl
                                                      : modelData.description_short_en
                                                wrapMode: Text.Wrap
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        footer: [
            SecondaryButton {
                text: I18n.t("common.close")
                icon: "x"
                onClicked: sandboxModal.close()
            }
        ]
    }

    // filtr modyfikatora listy w edytorze: all / enabled / disabled / manual
    property string editorModFilter: "all"

    // flag backing store (ToggleSwitch renders; these hold the values)
    Item { id: noeosCheck; property bool checked: false }
    Item { id: noeacCheck; property bool checked: false }
    Item { id: skipNewsCheck; property bool checked: false }
    Item { id: skipIntroCheck; property bool checked: false }
    InstanceLogsModal { id: logsModal }
    Item { id: editorExecutable; property string value: "" }
    Item { id: editorProton; property string value: "" }
    Item { id: editorBranch; property string value: "" }

    // ---- stop game confirm ------------------------------------------------ #
    ConfirmModal {
        id: stopGameModal
        onConfirmed: Game.stopRunningGame()
    }

    // ---- delete confirm --------------------------------------------------- #
    ConfirmModal {
        id: deleteInstanceModal
        property string instanceToDelete: ""
        property string instanceNameToDelete: ""
        optionLabel: I18n.t("instances.delete.option")
        // druga linia obrony: modal mógł zostać otwarty, zanim gra wystartowała
        confirmDisabled: Game.isRunning
        onConfirmed: Profiles.remove(instanceToDelete, optionChecked)
    }
}
