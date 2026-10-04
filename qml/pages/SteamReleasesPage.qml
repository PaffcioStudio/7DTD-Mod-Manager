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

    property string pendingDeleteBranch: ""

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

    function askDeleteRelease(branch) {
        pendingDeleteBranch = branch
        deleteInstalledModal.ask(
            I18n.t("steamReleases.deleteTitle"),
            I18n.format("steamReleases.deleteMessage", {branch: branch}),
            I18n.t("steamReleases.deleteConfirm"),
            true
        )
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

        PageDescription {
            text: I18n.t("steamReleases.subtitle")
            maxTextWidth: 760
        }

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
                                    color: Theme.successSoft
                                    Icon { anchors.centerIn: parent; name: "check"; size: 15; tint: Theme.success }
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
                                        text: fmtSize(installedCard.modelData.size_bytes)
                                              + (installedCard.modelData.downloaded_at !== ""
                                                 ? " · " + fmtDate(installedCard.modelData.downloaded_at) : "")
                                        color: Theme.textMuted
                                        font.pixelSize: Typography.caption
                                        font.family: Theme.fontFamily
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }
                                }

                                IconButton {
                                    buttonSize: 30
                                    iconSize: 13
                                    icon: "trash"
                                    danger: true
                                    tooltip: I18n.t("steamReleases.deleteInstalled")
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
                            GameVersions.versions.some(v => v.branch === branchRow.modelData.branch)
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
