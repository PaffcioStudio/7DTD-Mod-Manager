import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
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
    readonly property int gridColumns: width > 1000 ? 2 : 1

    // blokada zawartości strony na czas JAKIEGOKOLWEGO modala + 600 ms po
    // zamknięciu (doklik/fade-out nie trafia w karty pod spodem) - D24.
    // Deklaratywnie: odblokowana na starcie (bez modali), lock na otwarcie,
    // 600 ms grace po zamknięciu.
    readonly property bool anyModalOpen: editorModal.opened || deleteInstanceModal.opened
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
        noeosCheck.checked = true
        noeacCheck.checked = false
        skipNewsCheck.checked = true
        skipIntroCheck.checked = true
        settingDir = false
        editorModal.open()
    }

    function openGameVersions() {
        gameVersionsModal.open()
        Qt.callLater(() => {
            if (!GameVersions.hasSavedSession && !GameVersions.busy)
                GameVersions.startAuth()
        })
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
                                    editorBranch.value)
            editorModal.close()
            return
        }
        // tworzenie: modal zostaje otwarty przy bledzie walidacji (toast
        // z przyczyna pokazuje sie obok), zeby user nie stracil wpisywanych danych
        if (Profiles.createInstance(editorName.text.trim(), editorDataDir.text.trim(),
                                    editorDesc.text.trim(), noeosCheck.checked,
                                    noeacCheck.checked, skipNewsCheck.checked,
                                    skipIntroCheck.checked, editorBranch.value)) {
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

            Item { Layout.fillWidth: true }

            SecondaryButton {
                text: I18n.t("instances.gameVersions")
                icon: "download"
                onClicked: gameVersionsModal.open()
            }

            PrimaryButton {
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

        GameVersionsModal { id: gameVersionsModal }

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
                    model: Profiles.model

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
                        required property bool favorite

                        width: widthForColumns()
                        height: 214

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
                            favorite: profileDelegate.favorite

                            onFavoriteToggled: Profiles.toggleFavorite(profileDelegate.profileId)
                            onLaunchRequested: Profiles.launchInstance(profileDelegate.profileId)
                            onActivateRequested: Profiles.activate(profileDelegate.profileId)
                            onBuildModsRequested: Profiles.buildModsFor(profileDelegate.profileId)
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
                    implicitHeight: 214

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
                    TapHandler { onTapped: page.openNew() }
                }
            }
        }
    }

    // ---- folder picker for the editor ------------------------------------ #
    FolderDialog {
        id: editorDirDialog
        title: I18n.t("instances.folderPicker.title")
        onAccepted: {
            editorDataDir.text = editorDirDialog.selectedFolder.toString().replace("file://", "")
        }
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
                    implicitHeight: 272
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
                                         .concat(GameVersions.versions.map(function (v) {
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
                                onClicked: editorDirDialog.open()
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
                            policy: ScrollBar.AlwaysOn
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

    // filtr modyfikatora listy w edytorze: all / enabled / disabled / manual
    property string editorModFilter: "all"

    // flag backing store (ToggleSwitch renders; these hold the values)
    Item { id: noeosCheck; property bool checked: false }
    Item { id: noeacCheck; property bool checked: false }
    Item { id: skipNewsCheck; property bool checked: false }
    Item { id: skipIntroCheck; property bool checked: false }
    Item { id: editorBranch; property string value: "" }

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
