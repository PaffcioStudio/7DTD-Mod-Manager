import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Nowoczesny modal zarządzania wersjami gry Steam.
//
// Układ normalny:
//   - pasek konta Steam
//   - aktywne pobieranie
//   - kompaktowa siatka pobranych wersji
//   - lista dostępnych branchy Steam
//
// Pobieranie pozostaje niezależne od modala konta Steam; modal wersji gry
// udostępnia pełne sterowanie pobieraniem wraz z anulowaniem.
Modal {
    id: root
    title: I18n.t("gameVersions.title")
    iconName: "download"
    cardWidth: 900

    function fmtSize(bytes) {
        if (!bytes || bytes <= 0) return ""
        const gb = bytes / (1024 * 1024 * 1024)
        return (gb >= 10 ? gb.toFixed(1) : gb.toFixed(2)) + " GB"
    }

    function fmtDate(value) {
        const raw = String(value || "").replace("T", " ")
        if (!raw) return ""
        return raw.length > 16 ? raw.slice(0, 16) : raw
    }

    Component.onCompleted: GameVersions.refreshAvailable()

    Connections {
        target: GameVersions
        function onVersionsChanged() { GameVersions.refreshAvailable() }
    }

    Connections {
        target: root
        function onOpenedChanged() {
            if (!root.opened && GameVersions.busy && GameVersions.needsQr)
                GameVersions.cancel()
        }
    }

    // =========================== QR LOGIN ================================ #
    AppScrollView {
        visible: GameVersions.needsQr
        Layout.fillWidth: true
        Layout.preferredHeight: 500
        showScrollBar: false
        contentHeight: qrCol.implicitHeight

        ColumnLayout {
            id: qrCol
            width: Math.max(0, parent.width - 48)
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
                                text: I18n.t("gameVersions.connectSteam")
                                color: Theme.text
                                font.pixelSize: Typography.h2
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }
                            Text {
                                text: I18n.t("gameVersions.qrHint")
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
                        text: I18n.t("gameVersions.qrRefresh")
                        color: Theme.textSecondary
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }

            SecondaryButton {
                Layout.alignment: Qt.AlignRight
                text: I18n.t("gameVersions.cancelAuth")
                icon: "x"
                onClicked: GameVersions.cancel()
            }
        }
    }

    // =========================== NORMAL ================================ #
    AppScrollView {
        visible: !GameVersions.needsQr
        Layout.fillWidth: true
        Layout.preferredHeight: 560
        contentHeight: versionsCol.implicitHeight

        ColumnLayout {
            id: versionsCol
            width: Math.max(0, parent.width - 48)
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
                                text: I18n.t("gameVersions.account")
                                color: Theme.text
                                font.pixelSize: Typography.body + 1
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }

                            StatusBadge {
                                key: "success"
                                label: I18n.t("gameVersions.connected")
                            }
                        }

                        Text {
                            Layout.fillWidth: true
                            text: GameVersions.steamUsername !== ""
                                  ? I18n.format("gameVersions.loggedInAs", {username: GameVersions.steamUsername})
                                  : I18n.t("gameVersions.savedSession")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            elide: Text.ElideRight
                        }
                    }

                    SecondaryButton {
                        text: I18n.t("gameVersions.relogin")
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
                                text: I18n.format("gameVersions.downloading", {branch: GameVersions.downloadingBranch})
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
                            text: GameVersions.status !== "" ? I18n.resolveMessage(GameVersions.status) : I18n.t("gameVersions.downloadStatus")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                            Layout.fillWidth: true
                            elide: Text.ElideRight
                        }
                    }

                    SecondaryButton {
                        text: I18n.t("gameVersions.downloadCancel")
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
                    title: I18n.t("gameVersions.installedTitle")
                    caption: I18n.t("gameVersions.installedCaption")
                    StatusBadge {
                        key: "success"
                        label: I18n.format("gameVersions.installedBadge", {count: GameVersions.versions.length})
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
                                    tooltip: I18n.t("gameVersions.deleteInstalled")
                                    enabled: !GameVersions.busy
                                    onClicked: GameVersions.deleteVersion(installedCard.modelData.branch)
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
                    title: I18n.t("gameVersions.availableTitle")
                    caption: I18n.t("gameVersions.availableCaption")
                    StatusBadge {
                        key: "info"
                        label: I18n.format("gameVersions.availableBadge", {count: GameVersions.available.length})
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
                                        label: I18n.t("gameVersions.stable")
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
                                text: branchRow.installed ? I18n.t("gameVersions.downloaded")
                                      : branchRow.downloading
                                        ? Math.round(GameVersions.progress) + "%"
                                        : I18n.t("gameVersions.download")
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
                text: I18n.t("gameVersions.loading")
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
                        text: I18n.t("gameVersions.storageInfo")
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }

    footer: [
        SecondaryButton {
            text: I18n.t("gameVersions.refresh")
            icon: "refresh-cw"
            enabled: !GameVersions.busy
            onClicked: GameVersions.refreshAvailable()
        },
        PrimaryButton {
            text: I18n.t("gameVersions.close")
            icon: "x"
            onClicked: root.closeRequested()
        }
    ]
}
