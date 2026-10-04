import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs
import "../components"
import "../theme"
import "../i18n"

PageShell {
    id: page
    pageName: "settings"
    maxWidth: 1060

    property string currentSection: "general"
    property int selectedGameIndex: 0
    property bool gameDetectionBusy: false

    function openSection(key) {
        const wanted = (key || "").toString()
        if (sections.some(s => s.key === wanted))
            currentSection = wanted
    }

    Connections {
        target: Downloads
        function onArchivePreviewReady(sizeText, count) {
            if (count === 0) {
                Bus.toast(I18n.t("settings.download.archives.none"), "info")
                return
            }
            cleanArchivesModal.ask(I18n.t("settings.download.archives.confirmTitle"),
                I18n.format("settings.download.archives.confirmMessage", {count: count, size: sizeText}), I18n.t("settings.download.archives.clear"), true)
        }
    }

    ConfirmModal {
        id: cleanArchivesModal
        onConfirmed: Downloads.cleanArchives()
    }

    property var sections: []

    function refreshI18n() {
        page.sections = [
            { key: "general", label: I18n.t("settings.section.general"), icon: "sliders" },
            { key: "game", label: I18n.t("settings.section.game"), icon: "gamepad" },
            { key: "downloads", label: I18n.t("settings.section.downloads"), icon: "download" },
            { key: "appearance", label: I18n.t("settings.section.appearance"), icon: "palette" },
            { key: "advanced", label: I18n.t("settings.section.advanced"), icon: "terminal" },
            { key: "about", label: I18n.t("settings.section.about"), icon: "info" }
        ]
    }

    Component.onCompleted: refreshI18n()

    Connections {
        target: I18n
        function onLanguageChanged() { page.refreshI18n() }
    }

    readonly property var accents: [
        { name: "Ember",  value: "#FF7A38" },
        { name: "Toxic",  value: "#84CC16" },
        { name: "Blood",  value: "#EF5D5D" },
        { name: "Cyan",   value: "#38BDF8" },
        { name: "Violet", value: "#A78BFA" },
        { name: "Gold",   value: "#F5B841" }
    ]

    // ---- dialogs ---------------------------------------------------------- #
    FileDialog {
        id: exeDialog
        title: I18n.t("settings.game.fileDialog.exe")
        nameFilters: [I18n.t("settings.game.fileDialog.exeFilter"), I18n.t("settings.game.fileDialog.allFiles")]
        onAccepted: {
            const exe = exeDialog.selectedFile.toString().replace("file://", "")
            const dir = exe.substring(0, exe.lastIndexOf("/"))
            Settings.gameExecutable = exe
            // automatycznie: katalog gry = katalog pliku exe, mody = <katalog>/Mods
            Settings.gameDirectory = dir
            Settings.modsDirectory = dir + "/Mods"
        }
    }

    FolderDialog {
        id: gameDirDialog
        title: I18n.t("settings.game.fileDialog.gameDir")
        onAccepted: {
            const dir = gameDirDialog.selectedFolder.toString().replace("file://", "")
            Settings.gameDirectory = dir
            // mody gry podążają za katalogiem instalacji
            Settings.modsDirectory = dir + "/Mods"
        }
    }

    FolderDialog {
        id: modsDirDialog
        title: I18n.t("settings.game.fileDialog.modsDir")
        onAccepted: {
            Settings.modsDirectory = modsDirDialog.selectedFolder.toString().replace("file://", "")
        }
    }

    FolderDialog {
        id: downloadDirDialog
        title: I18n.t("settings.game.fileDialog.downloadDir")
        onAccepted: {
            Settings.downloadDirectory = downloadDirDialog.selectedFolder.toString().replace("file://", "")
        }
    }

    Timer {
        id: gameDetectionTimer
        interval: 80
        repeat: false
        onTriggered: {
            const result = Game.detect()
            page.gameDetectionBusy = false
            if (result.multiple === true) {
                page.selectedGameIndex = 0
                gameDetectionModal.open()
            }
        }
    }

    Modal {
        id: gameDetectionModal
        title: I18n.t("settings.game.detectModal.title")
        iconName: "gamepad"
        cardWidth: 640

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                Layout.fillWidth: true
                text: I18n.t("settings.game.detectModal.message")
                color: Theme.textSecondary
                font.pixelSize: Typography.body
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
            }

            AppScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(320, Math.max(96, contentHeight + 4))
                contentHeight: candidatesColumn.implicitHeight
                clip: true

                ColumnLayout {
                    id: candidatesColumn
                    width: parent.width
                    spacing: 8

                    Repeater {
                        model: Game.detectionCandidates

                        Rectangle {
                            id: candidateRow
                            required property var modelData
                            required property int index

                            readonly property bool selected: page.selectedGameIndex === index

                            Layout.fillWidth: true
                            implicitHeight: candidateText.implicitHeight + candidateSubtext.implicitHeight + 26
                            radius: 10
                            color: selected ? Theme.accentSoft : (candidateHover.hovered ? Theme.bg3 : Theme.bg2)
                            border.width: 1
                            border.color: selected ? Theme.rgba(Theme.accent, 0.55) : Theme.border

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 12
                                spacing: 12

                                Icon {
                                    name: candidateRow.selected ? "check-circle" : "hard-drive"
                                    size: 18
                                    tint: candidateRow.selected ? Theme.accent : Theme.textMuted
                                    Layout.alignment: Qt.AlignTop
                                    Layout.topMargin: 2
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Text {
                                        id: candidateText
                                        Layout.fillWidth: true
                                        text: candidateRow.modelData.gameDir
                                        color: Theme.text
                                        font.pixelSize: Typography.body
                                        font.weight: Font.DemiBold
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WrapAnywhere
                                    }

                                    Text {
                                        id: candidateSubtext
                                        Layout.fillWidth: true
                                        text: candidateRow.modelData.source + "  ·  " + candidateRow.modelData.executable
                                        color: Theme.textMuted
                                        font.pixelSize: Typography.caption
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WrapAnywhere
                                    }
                                }
                            }

                            HoverHandler { id: candidateHover }
                            TapHandler { onTapped: page.selectedGameIndex = candidateRow.index }
                        }
                    }
                }
            }
        }

        footer: [
            SecondaryButton { text: I18n.t("settings.cancel"); onClicked: gameDetectionModal.close() },
            PrimaryButton {
                text: I18n.t("settings.game.useLocation")
                icon: "check"
                disabled: Game.detectionCandidates.length === 0
                onClicked: {
                    const candidate = Game.detectionCandidates[page.selectedGameIndex]
                    if (candidate !== undefined && Game.applyDetectedGame(candidate.gameDir))
                        gameDetectionModal.close()
                }
            }
        ]
    }

    // ---- layout ------------------------------------------------------------ #
    RowLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingXxl

        // section nav
        ColumnLayout {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 210
            Layout.maximumWidth: 210
            spacing: 4

            Repeater {
                model: page.sections

                Item {
                    id: navItem
                    required property var modelData

                    readonly property bool active: page.currentSection === modelData.key

                    implicitHeight: 40
                    Layout.fillWidth: true

                    Rectangle {
                        anchors.fill: parent
                        radius: 10
                        color: navItem.active ? Theme.accentSoft
                             : (navHover.hovered ? Theme.bg3 : "transparent")
                        Behavior on color { ColorAnimation { duration: Theme.fast } }
                    }

                    Rectangle {
                        visible: navItem.active
                        width: 3
                        radius: 2
                        anchors.left: parent.left
                        anchors.leftMargin: -7
                        anchors.top: parent.top
                        anchors.topMargin: 8
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 8
                        color: Theme.accent
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 13
                        anchors.rightMargin: 13
                        spacing: 12

                        Icon {
                            name: navItem.modelData.icon
                            size: 16
                            tint: navItem.active ? Theme.accent
                                 : (navHover.hovered ? Theme.text : Theme.textSecondary)
                        }

                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignLeft
                            text: navItem.modelData.label
                            color: navItem.active ? Theme.text : Theme.textSecondary
                            font.pixelSize: Typography.body
                            font.weight: navItem.active ? Font.DemiBold : Font.Medium
                            font.family: Theme.fontFamily
                        }
                    }

                    HoverHandler { id: navHover }
                    TapHandler { onTapped: page.currentSection = navItem.modelData.key }
                }
            }
        }

        // content
        AppScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: Dimensions.spacingMd
            contentHeight: settingsColumn.implicitHeight

            ColumnLayout {
                id: settingsColumn
                width: Math.min(parent.width, page.currentSection === "about" ? 900 : 760)
                spacing: 10

                PageDescription {
                    text: I18n.t("settings.subtitle")
                    maxTextWidth: 760
                }

                // =========================================================== #
                // GENERAL
                // =========================================================== #
                SettingsSection {
                    visible: page.currentSection === "general"
                    title: I18n.t("settings.section.general")
                    caption: I18n.t("settings.section.generalCaption")

                    SettingsRow {
                        label: I18n.t("settings.language.label")
                        description: I18n.t("settings.language.description")
                        DropdownButton {
                            options: [
                                { value: "pl", label: I18n.t("settings.language.pl") },
                                { value: "en", label: I18n.t("settings.language.en") }
                            ]
                            value: Settings.language
                            onPicked: (value) => {
                                Settings.language = value
                                Bus.toast(I18n.languageChangedToast(), "info")
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.theme.label")
                        description: I18n.t("settings.theme.description")
                        DropdownButton {
                            options: [
                                { value: "dark", label: I18n.t("settings.theme.dark") },
                                { value: "light", label: I18n.t("settings.theme.light") },
                                { value: "stalker", label: I18n.t("settings.theme.stalker") },
                                { value: "stalker-light", label: I18n.t("settings.theme.stalkerLight") }
                            ]
                            value: Settings.themeMode
                            onPicked: (value) => Settings.themeMode = value
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.startMinimized.label")
                        description: I18n.t("settings.startMinimized.description")
                        ToggleSwitch {
                            checked: Settings.startMinimized
                            onToggled: (checked) => Settings.startMinimized = checked
                        }
                    }
                }

                // =========================================================== #
                // GAME
                // =========================================================== #
                SettingsSection {
                    visible: page.currentSection === "game"
                    title: I18n.t("settings.section.game")
                    caption: I18n.t("settings.section.gameCaption")

                    SettingsRow {
                        label: I18n.t("settings.game.detect.label")
                        description: I18n.t("settings.game.detect.description")
                        SecondaryButton {
                            text: page.gameDetectionBusy ? I18n.t("settings.game.searching") : I18n.t("settings.game.detectNow")
                            icon: page.gameDetectionBusy ? "refresh-cw" : "search"
                            busy: page.gameDetectionBusy
                            disabled: page.gameDetectionBusy
                            onClicked: {
                                page.gameDetectionBusy = true
                                Bus.toast(I18n.t("settings.game.searchToast"), "info")
                                gameDetectionTimer.restart()
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.game.file.label")
                        description: Settings.gameExecutable === ""
                            ? I18n.t("settings.game.file.notSet")
                            : Settings.gameExecutable
                        Row {
                            spacing: 8
                            SecondaryButton { text: I18n.t("settings.game.browse"); icon: "folder"; onClicked: exeDialog.open() }
                            SecondaryButton {
                                text: I18n.t("settings.game.clear")
                                icon: "x"
                                visible: Settings.gameExecutable !== ""
                                onClicked: Settings.gameExecutable = ""
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.game.directory.label")
                        description: Settings.gameDirectory === ""
                            ? I18n.t("settings.game.directory.notSet")
                            : Settings.gameDirectory
                        Row {
                            spacing: 8
                            SecondaryButton { text: I18n.t("settings.game.browse"); icon: "folder"; onClicked: gameDirDialog.open() }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.game.mods.label")
                        description: Settings.modsDirectory === ""
                            ? I18n.t("settings.game.mods.notSet")
                            : Settings.modsDirectory
                        Row {
                            spacing: 8
                            SecondaryButton { text: I18n.t("settings.game.browse"); icon: "folder"; onClicked: modsDirDialog.open() }
                            SecondaryButton {
                                text: I18n.t("settings.game.rescan")
                                icon: "refresh-cw"
                                visible: Settings.modsDirectory !== ""
                                onClicked: Mods.rescanGameMods()
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.game.status.label")
                        description: Game.statusKey !== "" ? I18n.format(Game.statusKey, Game.statusValues) : Game.statusText
                        StatusBadge {
                            key: Game.isDetected ? "success" : "disabled"
                            label: Game.isDetected ? I18n.t("settings.game.status.detected") : I18n.t("settings.game.status.notDetected")
                        }
                    }
                }

                // =========================================================== #
                // DOWNLOADS
                // =========================================================== #
                SettingsSection {
                    visible: page.currentSection === "downloads"
                    title: I18n.t("settings.section.downloads")
                    caption: I18n.t("settings.section.downloadsCaption")

                    SettingsRow {
                        label: I18n.t("settings.download.directory.label")
                        description: Settings.downloadDirectory
                        SecondaryButton { text: I18n.t("settings.game.browse"); icon: "folder"; onClicked: downloadDirDialog.open() }
                    }

                    SettingsRow {
                        label: I18n.t("settings.download.concurrent.label")
                        description: I18n.t("settings.download.concurrent.description")
                        DropdownButton {
                            options: [
                                { value: "1", label: "1" },
                                { value: "2", label: "2" },
                                { value: "3", label: "3" },
                                { value: "4", label: "4" },
                                { value: "5", label: "5" }
                            ]
                            value: String(Settings.maxConcurrentDownloads)
                            onPicked: (value) => Settings.maxConcurrentDownloads = parseInt(value)
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.download.archives.label")
                        description: Downloads.archiveDirectory
                        SecondaryButton {
                            text: Downloads.archiveBusy ? I18n.t("settings.download.archives.processing") : I18n.t("settings.download.archives.clear")
                            icon: Downloads.archiveBusy ? "refresh-cw" : "trash"
                            busy: Downloads.archiveBusy
                            disabled: Downloads.archiveBusy
                            onClicked: Downloads.previewArchives()
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.download.cleanup.label")
                        description: I18n.t("settings.download.cleanup.description")
                        DropdownButton {
                            options: [
                                { value: "never", label: I18n.t("settings.download.cleanup.never") },
                                { value: "24h", label: I18n.t("settings.download.cleanup.24h") },
                                { value: "7d", label: I18n.t("settings.download.cleanup.7d") }
                            ]
                            value: Settings.autoCleanDownloads
                            onPicked: (value) => Settings.autoCleanDownloads = value
                        }
                    }
                }

                // =========================================================== #
                // UPDATES
                // =========================================================== #
                SettingsSection {
                    visible: page.currentSection === "downloads"
                    title: I18n.t("updates.title")
                    caption: I18n.t("settings.updates.sectionCaption")

                    SettingsRow {
                        label: I18n.t("settings.updates.checkStart.label")
                        description: I18n.t("settings.updates.checkStart.description")
                        ToggleSwitch {
                            checked: Settings.autoCheckUpdates
                            onToggled: (checked) => Settings.autoCheckUpdates = checked
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.updates.auto.label")
                        description: I18n.t("settings.updates.auto.description")
                        ToggleSwitch {
                            checked: Settings.autoUpdateMods
                            onToggled: (checked) => Settings.autoUpdateMods = checked
                        }
                    }
                }

                // =========================================================== #
                // APPEARANCE
                // =========================================================== #
                SettingsSection {
                    visible: page.currentSection === "appearance"
                    title: I18n.t("settings.section.appearance")
                    caption: I18n.t("settings.section.appearanceCaption")

                    SettingsRow {
                        label: I18n.t("settings.appearance.accent.label")
                        description: I18n.t("settings.appearance.accent.description")
                        Row {
                            spacing: 8

                            Repeater {
                                model: page.accents

                                Item {
                                    id: swatch
                                    required property var modelData

                                    width: 32
                                    height: 32

                                    readonly property bool selected: Settings.accentColor.toLowerCase()
                                                     === swatch.modelData.value.toLowerCase()

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 10
                                        color: swatch.modelData.value
                                        border.width: 2
                                        border.color: swatch.selected ? Theme.text : "transparent"
                                    }

                                    Icon {
                                        anchors.centerIn: parent
                                        name: "check"
                                        size: 14
                                        tint: "#1C0E05"
                                        visible: swatch.selected
                                    }

                                    TapHandler {
                                        onTapped: Settings.accentColor = swatch.modelData.value
                                    }

                                    HoverHandler { id: swatchHover }
                                    ToolTip.visible: swatchHover.hovered
                                    ToolTip.text: I18n.t("settings.accent." + swatch.modelData.name)
                                    ToolTip.delay: 350
                                }
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.appearance.scale.label")
                        description: I18n.format("settings.appearance.scale.description", {percent: Math.round(Settings.uiScale * 100)})
                        Item {
                            implicitWidth: 220
                            implicitHeight: 38

                            RowLayout {
                                anchors.fill: parent
                                spacing: 12

                                Slider {
                                    id: scaleSlider
                                    Layout.fillWidth: true
                                    from: 0.85
                                    to: 1.2
                                    stepSize: 0.05
                                    value: Settings.uiScale

                                    background: Rectangle {
                                        x: scaleSlider.leftPadding
                                        y: scaleSlider.topPadding + scaleSlider.availableHeight / 2 - height / 2
                                        width: scaleSlider.availableWidth
                                        height: 5
                                        radius: 3
                                        color: Theme.bg4

                                        Rectangle {
                                            width: scaleSlider.visualPosition * parent.width
                                            height: parent.height
                                            radius: 3
                                            color: Theme.accent
                                        }
                                    }

                                    handle: Rectangle {
                                        x: scaleSlider.leftPadding + scaleSlider.visualPosition * (scaleSlider.availableWidth - width)
                                        y: scaleSlider.topPadding + scaleSlider.availableHeight / 2 - height / 2
                                        width: 17
                                        height: 17
                                        radius: 9
                                        color: Theme.text
                                        border.width: 4
                                        border.color: Theme.accent
                                    }

                                    onMoved: Settings.uiScale = value
                                }

                                Text {
                                    text: Math.round(Settings.uiScale * 100) + "%"
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.small
                                    font.weight: Font.Medium
                                    font.family: Theme.fontFamily
                                }
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.appearance.animations.label")
                        description: I18n.t("settings.appearance.animations.description")
                        ToggleSwitch {
                            checked: Settings.animationsEnabled
                            onToggled: (checked) => Settings.animationsEnabled = checked
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.appearance.heroRotation.label")
                        description: I18n.t("settings.appearance.heroRotation.description")
                        ToggleSwitch {
                            checked: Settings.heroRotationEnabled
                            onToggled: (checked) => Settings.heroRotationEnabled = checked
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.appearance.windowFrame.label")
                        description: I18n.t("settings.appearance.windowFrame.description")
                        ToggleSwitch {
                            checked: Settings.customWindowFrame
                            onToggled: (checked) => Settings.customWindowFrame = checked
                        }
                    }
                }

                // =========================================================== #
                // ADVANCED
                // =========================================================== #
                SettingsSection {
                    visible: page.currentSection === "advanced"
                    title: I18n.t("settings.section.advanced")
                    caption: I18n.t("settings.section.advancedCaption")

                    SettingsRow {
                        label: I18n.t("settings.advanced.logging.label")
                        description: I18n.format("settings.advanced.logging.description", {path: App.logsDir})
                        ToggleSwitch {
                            checked: Settings.loggingEnabled
                            onToggled: (checked) => {
                                Settings.loggingEnabled = checked
                                Bus.toast(checked ? I18n.t("settings.advanced.logging.enabled")
                                                  : I18n.t("settings.advanced.logging.disabled"), "info")
                            }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.advanced.debug.label")
                        description: I18n.t("settings.advanced.debug.description")
                        ToggleSwitch {
                            checked: Settings.debugMode
                            onToggled: (checked) => Settings.debugMode = checked
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.advanced.folders.label")
                        description: I18n.t("settings.advanced.folders.description")
                        Row {
                            spacing: 8
                            SecondaryButton { text: I18n.t("settings.advanced.logs"); icon: "terminal"; onClicked: App.openLogsFolder() }
                            SecondaryButton { text: I18n.t("settings.advanced.config"); icon: "folder"; onClicked: App.openConfigFolder() }
                        }
                    }

                    SettingsRow {
                        label: I18n.t("settings.advanced.reset.label")
                        description: I18n.t("settings.advanced.reset.description")
                        SecondaryButton {
                            text: I18n.t("settings.advanced.reset.label")
                            icon: "rotate-ccw"
                            onClicked: resetConfirm.ask(
                                I18n.t("settings.advanced.reset.label"),
                                I18n.t("settings.advanced.reset.message"),
                                I18n.t("settings.advanced.reset.confirm"), true)
                        }
                    }
                }

                // =========================================================== #
                // ABOUT
                // =========================================================== #
                ColumnLayout {
                    visible: page.currentSection === "about"
                    Layout.fillWidth: true
                    spacing: 14

                    Text {
                        text: I18n.t("settings.about.title")
                        color: Theme.text
                        font.pixelSize: Typography.h2
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }

                    Text {
                        text: I18n.t("settings.about.subtitle")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption + 0.5
                        font.family: Theme.fontFamily
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.border
                    }

                    GridLayout {
                        id: aboutTopGrid
                        Layout.fillWidth: true
                        columns: width >= 720 ? 2 : 1
                        columnSpacing: 12
                        rowSpacing: 12

                        Panel {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 158
                            pad: 18

                            RowLayout {
                                anchors.fill: parent
                                spacing: 14

                                Rectangle {
                                    Layout.preferredWidth: 64
                                    Layout.preferredHeight: 64
                                    radius: 18
                                    color: Theme.accentSoft
                                    border.width: 1
                                    border.color: Theme.rgba(Theme.accent, 0.35)

                                    Image {
                                        anchors.centerIn: parent
                                        width: 42
                                        height: 42
                                        source: Qt.resolvedUrl("../../assets/icons/app-icon.svg")
                                        fillMode: Image.PreserveAspectFit
                                        smooth: true
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 5

                                    Text {
                                        Layout.fillWidth: true
                                        text: "7DTD Mod Manager"
                                        color: Theme.text
                                        font.pixelSize: Typography.h1
                                        font.weight: Font.Bold
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        Layout.fillWidth: true
                                        text: I18n.t("settings.about.manager")
                                        color: Theme.textSecondary
                                        font.pixelSize: Typography.body
                                        font.family: Theme.fontFamily
                                        wrapMode: Text.WordWrap
                                    }

                                    RowLayout {
                                        spacing: 8
                                        StatusBadge { key: "info"; label: "v" + App.version }
                                        Text {
                                            text: I18n.t("settings.about.versionPlatform")
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.small
                                            font.family: Theme.fontFamily
                                        }
                                    }
                                }
                            }
                        }

                        Panel {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 158
                            pad: 18

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 7

                                Text {
                                    text: I18n.t("settings.about.author")
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: Typography.trackingWide
                                    font.family: Theme.fontFamily
                                }

                                Text {
                                    text: "Paffcio"
                                    color: Theme.text
                                    font.pixelSize: Typography.h2
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: I18n.t("settings.about.github")
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.small
                                    font.family: Theme.fontFamily
                                }

                                SecondaryButton {
                                    text: I18n.t("settings.about.openGithub")
                                    icon: "external-link"
                                    onClicked: App.openUrl("https://github.com/paffciostudio")
                                }
                            }
                        }

                        Panel {
                            Layout.fillWidth: true
                            Layout.columnSpan: aboutTopGrid.columns
                            Layout.preferredHeight: 126
                            pad: 18

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 6

                                Text {
                                    text: I18n.t("settings.about.project")
                                    color: Theme.text
                                    font.pixelSize: Typography.h2
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: I18n.t("settings.about.projectText")
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.body
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: width >= 720 ? 2 : 1
                        columnSpacing: 12
                        rowSpacing: 12

                        Panel {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 156
                            pad: 18

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 10

                                Text {
                                    text: I18n.t("settings.about.technologies")
                                    color: Theme.text
                                    font.pixelSize: Typography.h2
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    spacing: 7
                                    Repeater {
                                        model: ["Python", "PySide6", "Qt / QML", "Steam", "DepotDownloader", "Proton"]
                                        delegate: Rectangle {
                                            required property string modelData
                                            width: techText.implicitWidth + 20
                                            height: 30
                                            radius: 9
                                            color: Theme.bg3
                                            border.width: 1
                                            border.color: Theme.border
                                            Text {
                                                id: techText
                                                anchors.centerIn: parent
                                                text: modelData
                                                color: Theme.textSecondary
                                                font.pixelSize: Typography.small
                                                font.weight: Font.Medium
                                                font.family: Theme.fontFamily
                                            }
                                        }
                                    }
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: I18n.format("settings.about.versionDetails", {qt: App.qtVersion, python: App.pythonVersion})
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                }
                            }
                        }

                        Panel {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 156
                            pad: 18

                            ColumnLayout {
                                anchors.fill: parent
                                spacing: 8

                                Text {
                                    text: I18n.t("settings.about.useful")
                                    color: Theme.text
                                    font.pixelSize: Typography.h2
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: I18n.format("settings.about.logs", {path: App.logsDir})
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideMiddle
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 8
                                    SecondaryButton { text: I18n.t("settings.about.openLogs"); icon: "terminal"; onClicked: App.openLogsFolder() }
                                    SecondaryButton { text: I18n.t("settings.about.dataFolder"); icon: "folder"; onClicked: App.openConfigFolder() }
                                }
                            }
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Text {
                            text: I18n.t("settings.about.faq")
                            color: Theme.text
                            font.pixelSize: Typography.h2
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                        }

                        Text {
                            text: I18n.t("settings.about.faqSubtitle")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption + 0.5
                            font.family: Theme.fontFamily
                        }

                        FaqItem {
                            question: I18n.t("settings.about.faq.steamQ")
                            answer: I18n.t("settings.about.faq.steamA")
                        }
                        FaqItem {
                            question: I18n.t("settings.about.faq.instanceQ")
                            answer: I18n.t("settings.about.faq.instanceA")
                        }
                        FaqItem {
                            question: I18n.t("settings.about.faq.presetsQ")
                            answer: I18n.t("settings.about.faq.presetsA")
                        }
                        FaqItem {
                            question: I18n.t("settings.about.faq.logsQ")
                            answer: I18n.t("settings.about.faq.logsA")
                        }
                        FaqItem {
                            question: I18n.t("settings.about.faq.appUpdatesQ")
                            answer: I18n.t("settings.about.faq.appUpdatesA")
                        }
                    }

                Item { Layout.fillHeight: true; Layout.minimumHeight: 16 }
            }
        }
    }

    ConfirmModal {
        id: resetConfirm
        onConfirmed: {
            Settings.resetToDefaults()
            Bus.toast(I18n.t("settings.advanced.reset.toast"), "success")
        }
    }

    // ------------------------------------------------------------------ #
    // inline building blocks
    // ------------------------------------------------------------------ #
    component SettingsSection: ColumnLayout {
        id: section

        property string title: ""
        property string caption: ""

        spacing: 4
        Layout.fillWidth: true
        Layout.bottomMargin: 22
        Layout.maximumWidth: 10000

        Text {
            text: section.title
            color: Theme.text
            font.pixelSize: Typography.h2
            font.weight: Font.DemiBold
            font.family: Theme.fontFamily
        }

        Text {
            text: section.caption
            color: Theme.textMuted
            font.pixelSize: Typography.caption + 0.5
            font.family: Theme.fontFamily
            Layout.bottomMargin: 10
        }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
        }
    }

    component FaqItem: ColumnLayout {
        id: faq

        property string question: ""
        property string answer: ""
        property bool expanded: false

        Layout.fillWidth: true
        spacing: 8

        Rectangle {
            id: questionCard
            Layout.fillWidth: true
            implicitHeight: Math.max(46, questionRow.implicitHeight + 20)
            radius: Dimensions.radiusMd
            color: faq.expanded ? Theme.bg3 : Theme.bg2
            border.width: 1
            border.color: faq.expanded ? Theme.borderStrong : Theme.border

            RowLayout {
                id: questionRow
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 12
                spacing: 10

                Text {
                    id: questionText
                    Layout.fillWidth: true
                    text: faq.question
                    color: Theme.text
                    font.pixelSize: Typography.small + 1
                    font.weight: Font.Medium
                    font.family: Theme.fontFamily
                    wrapMode: Text.WordWrap
                    maximumLineCount: 3
                }

                Icon {
                    name: faq.expanded ? "chevron-up" : "chevron-down"
                    size: 16
                    tint: Theme.textMuted
                    Layout.alignment: Qt.AlignVCenter
                }
            }

            TapHandler { onTapped: faq.expanded = !faq.expanded }
        }

        Text {
            visible: faq.expanded
            Layout.fillWidth: true
            Layout.leftMargin: 14
            Layout.rightMargin: 14
            textFormat: Text.RichText
            text: faq.answer
            color: Theme.textSecondary
            font.pixelSize: Typography.body
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }
    }

    component SettingsRow: RowLayout {
        id: row

        property string label: ""
        property string description: ""

        spacing: 20
        Layout.fillWidth: true
        Layout.maximumWidth: 10000
        Layout.topMargin: 14
        Layout.bottomMargin: 6

        ColumnLayout {
            spacing: 3
            Layout.fillWidth: true

            Text {
                text: row.label
                color: Theme.text
                font.pixelSize: Typography.small + 1
                font.weight: Font.Medium
                font.family: Theme.fontFamily
            }

            Text {
                text: row.description
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                Layout.maximumWidth: 10000
            }
        }
    }
}

}
