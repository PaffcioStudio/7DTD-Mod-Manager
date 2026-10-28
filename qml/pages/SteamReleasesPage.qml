import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../components"
import "../theme"
import "../i18n"

// Dedicated Steam release management area.
// Backend operations continue to be owned by GameVersionsManager.
PageShell {
    id: page
    pageName: "steam_releases"
    maxWidth: 1080
    signal logoutRequested()

    property string pendingDeleteBranch: ""
    property string pendingReinstallBranch: ""
    property string importFeedback: ""
    property bool importFeedbackError: false
    property string codeFeedback: ""
    property string selectedHistoricalBranch: "alpha5.0"
    readonly property var selectedHistorical: {
        const releases = GameVersions.historicalReleases
        for (let i = 0; i < releases.length; ++i) {
            if (releases[i].branch === selectedHistoricalBranch)
                return releases[i]
        }
        return releases.length > 0 ? releases[0] : {}
    }

    FolderPickerModal {
        id: importGameFolder
        pickerTitle: I18n.t("steamReleases.legacy.importTitle")
        confirmText: I18n.t("folderPicker.chooseFolder")
        onFolderPicked: function(path) {
            const failure = GameVersions.importVersion(path, page.selectedHistoricalBranch, customReleaseName.text)
            if (failure !== "") {
                page.importFeedbackError = true
                page.importFeedback = I18n.resolveMessage(failure)
                Bus.toast(page.importFeedback, "error")
            } else {
                page.importFeedbackError = false
                page.importFeedback = I18n.format("steamReleases.legacy.importSuccess", {
                    branch: customReleaseName.text.trim() !== ""
                        ? customReleaseName.text.trim() : page.selectedHistoricalBranch
                })
                Bus.toast(page.importFeedback, "success")
            }
        }
    }

    function fmtSize(bytes) {
        var value = Number(bytes)
        if (!isFinite(value) || value <= 0)
            return "0 B"

        var units = ["B", "KB", "MB", "GB", "TB"]
        var unitIndex = 0
        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024
            unitIndex++
        }

        var decimals = unitIndex === 0 ? 0 : (value >= 100 ? 0 : (value >= 10 ? 1 : 2))
        return value.toFixed(decimals) + " " + units[unitIndex]
    }

    function fmtDate(value) {
        if (value === undefined || value === null || String(value).trim() === "")
            return ""
        var date = new Date(value)
        if (isNaN(date.getTime()))
            return String(value)
        return Qt.formatDateTime(date, "yyyy-MM-dd HH:mm")
    }

    function openSteamArea() {
        GameVersions.refreshAvailable()
        if (!GameVersions.hasSavedSession && !GameVersions.busy)
            GameVersions.startAuth()
    }

    function releaseRecord(branch) {
        return GameVersions.versions.find(function(v) { return v.branch === branch })
    }

    function askDeleteRelease(branch) {
        const entry = releaseRecord(branch)
        if (!entry || GameVersions.busy)
            return
        const imported = entry.origin === "imported"
        pendingDeleteBranch = branch
        deleteInstalledModal.ask(
            I18n.t(imported ? "steamReleases.removeImportTitle" : "steamReleases.deleteTitle"),
            I18n.format(imported ? "steamReleases.removeImportMessage" : "steamReleases.deleteMessage", {branch: branch}),
            I18n.t(imported ? "steamReleases.removeImport" : "steamReleases.deleteConfirm"),
            true
        )
    }

    function askReinstallRelease(branch) {
        pendingReinstallBranch = branch
        reinstallModal.ask(
            I18n.t("steamReleases.reinstallTitle"),
            I18n.format("steamReleases.reinstallMessage", {branch: branch}),
            I18n.t("steamReleases.reinstallConfirm"),
            false
        )
    }

    function startCodeDownload() {
        if (GameVersions.busy || depotCode.text.trim() === "")
            return
        codeFeedback = ""
        if (!GameVersions.downloadCode(depotCode.text))
            codeFeedback = GameVersions.status
    }

    ConfirmModal {
        id: reinstallModal
        onConfirmed: {
            const branch = page.pendingReinstallBranch
            page.pendingReinstallBranch = ""
            if (branch !== "")
                GameVersions.reinstall(branch)
        }
        onRejected: page.pendingReinstallBranch = ""
    }

    ConfirmModal {
        id: deleteInstalledModal
        onConfirmed: {
            const branch = page.pendingDeleteBranch
            page.pendingDeleteBranch = ""
            if (branch !== "")
                GameVersions.deleteVersion(branch)
        }
        onRejected: page.pendingDeleteBranch = ""
    }

    onActiveChanged: {
        if (active)
            Qt.callLater(openSteamArea)
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Dimensions.pagePad
        anchors.topMargin: Dimensions.spacingLg
        spacing: Dimensions.spacingMd


        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            SecondaryButton {
                text: I18n.t("steamReleases.refresh")
                icon: "refresh-cw"
                enabled: !GameVersions.busy
                onClicked: GameVersions.refreshAvailable()
            }
        }

        // =========================== QR LOGIN ================================ #
    AppScrollView {
        visible: GameVersions.needsQr
        Layout.fillWidth: true
        Layout.fillHeight: true
        showScrollBar: false
        contentHeight: qrCol.implicitHeight

        ColumnLayout {
            id: qrCol
            width: Math.max(0, parent.width - 48)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 14

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 390
                radius: 16
                color: Theme.bg1
                border.width: 1
                border.color: Theme.border

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 3
                    radius: 2
                    color: Theme.accent
                }

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 48, 520)
                    spacing: 13

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10

                        Rectangle {
                            Layout.preferredWidth: 34
                            Layout.preferredHeight: 34
                            radius: 10
                            color: Theme.accentSoft
                            Icon { anchors.centerIn: parent; name: "user"; size: 16; tint: Theme.accent }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: I18n.t("steamReleases.connectSteam")
                                color: Theme.text
                                font.pixelSize: Typography.h2
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }
                            Text {
                                text: I18n.t("steamReleases.qrHint")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption + 0.5
                                font.family: Theme.fontFamily
                            }
                        }
                    }

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 228
                        height: 228
                        radius: 14
                        color: "#FFFFFF"

                        Image {
                            anchors.fill: parent
                            anchors.margins: 8
                            source: GameVersions.qrDataUrl
                            fillMode: Image.PreserveAspectFit
                            visible: GameVersions.qrDataUrl !== ""
                        }

                        BusyIndicator {
                            anchors.centerIn: parent
                            running: GameVersions.qrDataUrl === ""
                            visible: running
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.qrRefresh")
                        color: Theme.textSecondary
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }

            SecondaryButton {
                Layout.alignment: Qt.AlignRight
                text: I18n.t("steamReleases.cancelAuth")
                icon: "x"
                onClicked: GameVersions.cancel()
            }
        }
    }

            AppScrollView {
        visible: !GameVersions.needsQr
        Layout.fillWidth: true
        Layout.fillHeight: true
        contentHeight: versionsCol.implicitHeight

        ColumnLayout {
            id: versionsCol
            width: Math.max(0, parent.width - 48)
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: 14

            // -------------------------- ACCOUNT --------------------------- #
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 82
                radius: 15
                color: Theme.bg1
                border.width: 1
                border.color: Theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 44
                        Layout.preferredHeight: 44
                        radius: 13
                        color: Theme.successSoft
                        border.width: 1
                        border.color: Theme.rgba(Theme.success, 0.28)
                        Icon { anchors.centerIn: parent; name: "check"; size: 19; tint: Theme.success }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8

                            Text {
                                text: I18n.t("steamReleases.account")
                                color: Theme.text
                                font.pixelSize: Typography.body + 1
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }

                            StatusBadge {
                                key: "success"
                                label: I18n.t("steamReleases.connected")
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: GameVersions.steamUsername !== ""
                                  ? I18n.format("steamReleases.loggedInAs", {username: GameVersions.steamUsername})
                                  : I18n.t("steamReleases.savedSession")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            elide: Text.ElideRight
                        }
                    }

                    SecondaryButton {
                        text: I18n.t("steamReleases.relogin")
                        icon: "user"
                        compact: true
                        enabled: !GameVersions.busy
                        onClicked: GameVersions.reauthorize()
                    }
                    SecondaryButton {
                        objectName: "steamReleasesLogout"
                        text: I18n.t("steamAccount.logout")
                        icon: "x"
                        compact: true
                        enabled: !GameVersions.busy
                        onClicked: page.logoutRequested()
                    }
                }
            }

            // ------------------- STARE WERSJE / IMPORT --------------------- #
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: legacyContent.implicitHeight + 32
                radius: 15
                color: Theme.bg1
                border.width: 1
                border.color: Theme.border

                ColumnLayout {
                    id: legacyContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        Icon { name: "archive"; size: 19; tint: Theme.accent }
                        Text {
                            text: I18n.t("steamReleases.legacy.title")
                            color: Theme.text
                            font.pixelSize: Typography.h2
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                            Layout.fillWidth: true
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.legacy.description")
                        color: Theme.textSecondary
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }

                    DropdownButton {
                        Layout.fillWidth: true
                        value: page.selectedHistoricalBranch
                        options: GameVersions.historicalReleases.map(function(release) {
                            return {
                                value: release.branch,
                                label: (release.label_key ? I18n.t(release.label_key) : release.label) + " · " + release.date
                                    + (release.download_available ? "" : " · " + I18n.t("steamReleases.legacy.unavailable"))
                            }
                        })
                        onPicked: function(value) { page.selectedHistoricalBranch = value }
                    }

                    Text {
                        Layout.fillWidth: true
                        text: page.selectedHistorical.steam_branch
                              ? I18n.t("steamReleases.legacy.steamBranch")
                              : "Depot " + page.selectedHistorical.depot
                                + " · manifest " + page.selectedHistorical.manifest
                                + " · Windows " + page.selectedHistorical.osarch + "-bit"
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }

                    Text {
                        Layout.fillWidth: true
                        visible: page.selectedHistorical.download_available === false
                        text: I18n.format("steamReleases.legacy.downloadUnavailable", {
                            branch: page.selectedHistoricalBranch,
                            depot: page.selectedHistorical.depot
                        })
                        color: Theme.warning
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        PrimaryButton {
                            readonly property bool installed: GameVersions.versions.some(function(v) {
                                return v.branch === page.selectedHistoricalBranch && v.installed
                            })
                            text: installed ? I18n.t("steamReleases.downloaded")
                                            : I18n.t("steamReleases.legacy.download")
                            icon: installed ? "check" : "download"
                            disabled: GameVersions.busy || installed || page.selectedHistorical.download_available === false
                            onClicked: GameVersions.download(page.selectedHistoricalBranch)
                        }
                        SecondaryButton {
                            readonly property var entry: GameVersions.versions.find(function(v) {
                                return v.branch === page.selectedHistoricalBranch
                            })
                            visible: !!entry && entry.installed && entry.origin !== "imported"
                            text: I18n.t("steamReleases.reinstall")
                            icon: "refresh-cw"
                            disabled: GameVersions.busy || page.selectedHistorical.download_available === false
                            onClicked: page.askReinstallRelease(page.selectedHistoricalBranch)
                        }
                        SecondaryButton {
                            readonly property var entry: page.releaseRecord(page.selectedHistoricalBranch)
                            visible: !!entry
                            text: I18n.t(entry && entry.origin === "imported"
                                         ? "steamReleases.removeImport" : "steamReleases.uninstall")
                            icon: "trash"
                            danger: true
                            disabled: GameVersions.busy
                            onClicked: page.askDeleteRelease(page.selectedHistoricalBranch)
                        }
                        Text {
                            Layout.fillWidth: true
                            text: I18n.t("steamReleases.legacy.queueHint")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        height: 1
                        color: Theme.border
                    }

                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.legacy.importDescription")
                        color: Theme.textSecondary
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        AppTextField {
                            id: customReleaseName
                            Layout.fillWidth: true
                            placeholder: I18n.t("steamReleases.legacy.customName")
                        }
                        SecondaryButton {
                            text: I18n.t("steamReleases.legacy.import")
                            icon: "folder-plus"
                            enabled: !GameVersions.busy
                            onClicked: {
                                page.importFeedback = ""
                                importGameFolder.openAt(FileBrowser.homePath)
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        visible: page.importFeedback !== ""
                        implicitHeight: importFeedbackText.implicitHeight + 22
                        radius: 10
                        color: Theme.rgba(page.importFeedbackError ? Theme.danger : Theme.success, 0.09)
                        border.width: 1
                        border.color: Theme.rgba(page.importFeedbackError ? Theme.danger : Theme.success, 0.35)

                        Text {
                            id: importFeedbackText
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            text: page.importFeedback
                            color: page.importFeedbackError ? Theme.danger : Theme.success
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.legacy.importHint")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: depotCodeContent.implicitHeight + 32
                radius: 15
                color: Theme.bg1
                border.width: 1
                border.color: Theme.border

                ColumnLayout {
                    id: depotCodeContent
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 16
                    spacing: 12

                    Text {
                        text: I18n.t("steamReleases.code.title")
                        color: Theme.text
                        font.pixelSize: Typography.body + 1
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }
                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.code.description")
                        color: Theme.textSecondary
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        AppTextField {
                            id: depotCode
                            objectName: "steamDepotCodeInput"
                            Layout.fillWidth: true
                            placeholder: "251570 251576 1730022800995997518"
                            enabled: !GameVersions.busy
                            onAccepted: page.startCodeDownload()
                            onTextChanged: page.codeFeedback = ""
                        }
                        PrimaryButton {
                            objectName: "steamDepotCodeDownload"
                            text: I18n.t("steamReleases.code.download")
                            icon: "download"
                            disabled: GameVersions.busy || depotCode.text.trim() === ""
                            onClicked: page.startCodeDownload()
                        }
                    }
                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.code.hint")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                    Text {
                        Layout.fillWidth: true
                        visible: page.codeFeedback !== ""
                        text: I18n.resolveMessage(page.codeFeedback)
                        color: Theme.warning
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // ------------------------ DOWNLOAD ---------------------------- #
            Rectangle {
                Layout.fillWidth: true
                visible: GameVersions.busy && GameVersions.downloadingBranch !== ""
                implicitHeight: 96
                radius: 15
                color: Theme.accentSoft
                border.width: 1
                border.color: Theme.rgba(Theme.accent, 0.28)

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 12

                    Rectangle {
                        Layout.preferredWidth: 42
                        Layout.preferredHeight: 42
                        radius: 12
                        color: Theme.bg2
                        border.width: 1
                        border.color: Theme.rgba(Theme.accent, 0.26)
                        Icon { anchors.centerIn: parent; name: "download"; size: 18; tint: Theme.accent }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            Text {
                                text: I18n.format("steamReleases.downloading", {branch: GameVersions.downloadingBranch})
                                color: Theme.text
                                font.pixelSize: Typography.body + 1
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }

                            Text {
                                text: Math.round(GameVersions.progress) + "%"
                                color: Theme.accent
                                font.pixelSize: Typography.body
                                font.weight: Font.Bold
                                font.family: Theme.fontFamily
                            }
                        }

                        SlimProgress {
                            Layout.fillWidth: true
                            value: GameVersions.progress / 100
                            barHeight: 6
                            indeterminate: GameVersions.progress <= 0
                        }

                        Text {
                            text: GameVersions.status !== "" ? I18n.resolveMessage(GameVersions.status) : I18n.t("steamReleases.downloadStatus")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }

                    SecondaryButton {
                        text: I18n.t("steamReleases.downloadCancel")
                        icon: "x"
                        compact: true
                        danger: true
                        onClicked: GameVersions.cancel()
                    }
                }
            }

            // -------------------- STATUS / ERROR -------------------------- #
            Rectangle {
                Layout.fillWidth: true
                visible: !GameVersions.busy && GameVersions.status !== ""
                implicitHeight: gameVersionStatus.implicitHeight + 24
                radius: 12
                color: Theme.rgba(Theme.textMuted, 0.045)
                border.width: 1
                border.color: Theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 9

                    Icon { name: "info"; size: 15; tint: Theme.textMuted }

                    Text {
                        id: gameVersionStatus
                        Layout.fillWidth: true
                        text: I18n.resolveMessage(GameVersions.status)
                        color: Theme.textSecondary
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }

            // --------------------- INSTALLED ------------------------------ #
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: GameVersions.versions.length > 0

                SectionHeader {
                    title: I18n.t("steamReleases.installedTitle")
                    caption: I18n.t("steamReleases.installedCaption")
                    StatusBadge {
                        key: "success"
                        label: I18n.format("steamReleases.installedBadge", {count: GameVersions.versions.length})
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 10
                    rowSpacing: 10

                    Repeater {
                        model: GameVersions.versions

                        Rectangle {
                            id: installedCard
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.preferredHeight: 72
                            radius: 13
                            color: Theme.bg2
                            border.width: 1
                            border.color: Theme.border

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 11
                                spacing: 10

                                Rectangle {
                                    Layout.preferredWidth: 34
                                    Layout.preferredHeight: 34
                                    radius: 10
                                    color: installedCard.modelData.installed ? Theme.successSoft : Theme.bg1
                                    Icon {
                                        anchors.centerIn: parent
                                        name: installedCard.modelData.installed ? "check" : "alert-triangle"
                                        size: 15
                                        tint: installedCard.modelData.installed ? Theme.success : Theme.danger
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: installedCard.modelData.branch
                                        color: Theme.text
                                        font.pixelSize: Typography.body
                                        font.weight: Font.DemiBold
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                    Text {
                                        text: installedCard.modelData.installed
                                              ? fmtSize(installedCard.modelData.size_bytes)
                                                + (installedCard.modelData.downloaded_at !== ""
                                                   ? " · " + fmtDate(installedCard.modelData.downloaded_at) : "")
                                              : I18n.t("steamReleases.incompleteStatus")
                                        color: Theme.textMuted
                                        font.pixelSize: Typography.caption
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                IconButton {
                                    buttonSize: 30
                                    iconSize: 14
                                    icon: installedCard.modelData.installed ? "refresh-cw" : "download"
                                    tooltip: installedCard.modelData.installed
                                             ? I18n.t("steamReleases.reinstall")
                                             : I18n.t("steamReleases.repairIncomplete")
                                    enabled: !GameVersions.busy && installedCard.modelData.origin !== "imported"
                                    onClicked: {
                                        if (installedCard.modelData.installed)
                                            page.askReinstallRelease(installedCard.modelData.branch)
                                        else
                                            GameVersions.download(installedCard.modelData.branch)
                                    }
                                }

                                IconButton {
                                    buttonSize: 30
                                    iconSize: 13
                                    icon: "trash"
                                    danger: true
                                    tooltip: I18n.t(installedCard.modelData.origin === "imported"
                                                     ? "steamReleases.removeImport" : "steamReleases.uninstall")
                                    enabled: !GameVersions.busy
                                    onClicked: page.askDeleteRelease(installedCard.modelData.branch)
                                }
                            }
                        }
                    }
                }
            }

            // ---------------------- AVAILABLE ----------------------------- #
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: GameVersions.hasSavedSession && GameVersions.available.length > 0

                SectionHeader {
                    title: I18n.t("steamReleases.availableTitle")
                    caption: I18n.t("steamReleases.availableCaption")
                    StatusBadge {
                        key: "info"
                        label: I18n.format("steamReleases.availableBadge", {count: GameVersions.available.length})
                    }
                }

                Repeater {
                    model: GameVersions.available

                    Rectangle {
                        id: branchRow
                        required property var modelData
                        readonly property bool installed:
                            GameVersions.versions.some(v => v.branch === branchRow.modelData.branch && v.installed)
                        readonly property bool downloading:
                            GameVersions.downloadingBranch === branchRow.modelData.branch

                        Layout.fillWidth: true
                        implicitHeight: downloading ? 82 : 64
                        radius: 13
                        color: branchHover.hovered ? Theme.bg3 : Theme.bg2
                        border.width: 1
                        border.color: downloading
                                      ? Theme.rgba(Theme.accent, 0.34)
                                      : branchHover.hovered ? Theme.borderHover : Theme.border

                        Behavior on color { ColorAnimation { duration: Theme.fast } }
                        Behavior on border.color { ColorAnimation { duration: Theme.fast } }

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 10
                            spacing: 11

                            Rectangle {
                                Layout.preferredWidth: 36
                                Layout.preferredHeight: 36
                                radius: 11
                                color: branchRow.modelData.branch === "public"
                                       ? Theme.accentSoft
                                       : Theme.bg1
                                border.width: 1
                                border.color: branchRow.modelData.branch === "public"
                                              ? Theme.rgba(Theme.accent, 0.22)
                                              : Theme.border
                                Icon {
                                    anchors.centerIn: parent
                                    name: branchRow.modelData.branch === "public" ? "star" : "package"
                                    size: 16
                                    tint: branchRow.modelData.branch === "public" ? Theme.accent : Theme.textSecondary
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 7

                                    Text {
                                        text: branchRow.modelData.branch
                                        color: branchRow.modelData.branch === "public" ? Theme.accent : Theme.text
                                        font.pixelSize: Typography.body
                                        font.weight: Font.DemiBold
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                    }

                                    StatusBadge {
                                        visible: branchRow.modelData.branch === "public"
                                        key: "update"
                                        label: I18n.t("steamReleases.stable")
                                    }
                                }

                                Text {
                                    text: "build " + branchRow.modelData.buildid
                                          + (branchRow.modelData.size_bytes > 0
                                             ? " · " + fmtSize(branchRow.modelData.size_bytes) : "")
                                    color: Theme.textMuted
                                    font.pixelSize: Typography.caption
                                    font.family: Theme.fontFamily
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                SlimProgress {
                                    Layout.fillWidth: true
                                    visible: branchRow.downloading
                                    value: GameVersions.progress / 100
                                    barHeight: 4
                                }
                            }

                            SecondaryButton {
                                visible: branchRow.installed && GameVersions.versions.some(function(v) {
                                    return v.branch === branchRow.modelData.branch && v.origin !== "imported"
                                })
                                text: I18n.t("steamReleases.reinstall")
                                icon: "refresh-cw"
                                compact: true
                                disabled: GameVersions.busy
                                onClicked: page.askReinstallRelease(branchRow.modelData.branch)
                            }

                            SecondaryButton {
                                readonly property var entry: page.releaseRecord(branchRow.modelData.branch)
                                visible: !!entry
                                text: I18n.t(entry && entry.origin === "imported"
                                             ? "steamReleases.removeImport" : "steamReleases.uninstall")
                                icon: "trash"
                                danger: true
                                compact: true
                                disabled: GameVersions.busy
                                onClicked: page.askDeleteRelease(branchRow.modelData.branch)
                            }

                            PrimaryButton {
                                Layout.preferredWidth: 112
                                Layout.minimumWidth: 112
                                Layout.maximumWidth: 112
                                text: branchRow.installed ? I18n.t("steamReleases.downloaded")
                                      : branchRow.downloading
                                        ? Math.round(GameVersions.progress) + "%"
                                        : I18n.t("steamReleases.download")
                                icon: branchRow.installed ? "check" : "download"
                                busy: branchRow.downloading
                                disabled: GameVersions.busy || branchRow.installed
                                onClicked: GameVersions.download(branchRow.modelData.branch)
                            }
                        }

                        HoverHandler { id: branchHover }
                    }
                }
            }

            // ---------------------- EMPTY / INFO -------------------------- #
            Text {
                Layout.fillWidth: true
                visible: GameVersions.available.length === 0 && GameVersions.hasSavedSession
                text: I18n.t("steamReleases.loading")
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 52
                radius: 12
                color: Theme.bg1
                border.width: 1
                border.color: Theme.border

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 11
                    spacing: 9
                    Icon { name: "info"; size: 15; tint: Theme.textMuted }
                    Text {
                        Layout.fillWidth: true
                        text: I18n.t("steamReleases.storageInfo")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
    }
}
