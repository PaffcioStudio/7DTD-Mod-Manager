import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Drawer szczegółów moda z katalogu 7daystodiemods.com (etap 13).
// Użycie:  WebModDrawer { id: webDrawer }   /   webDrawer.openWith(slug)
// Klik w kartę na Odkrywaj otwiera drawer; stąd wybór pliku do pobrania.
Item {
    id: drawer

    property bool opened: false
    property string slug: ""
    property string selectedGameVersion: ""
    property var details: ({})
    property string errorText: ""

    readonly property var stateKey: Downloads.modDownloads[slug] || ""
    readonly property bool downloading: ["queued", "downloading", "paused"].indexOf(stateKey) >= 0

    function openWith(s, gameVersion) {
        slug = s
        selectedGameVersion = (gameVersion || "").trim()
        details = ({})
        errorText = ""
        opened = true
        drawer.forceActiveFocus()
        WebDetails.fetch(s)
    }

    function close() {
        opened = false
    }

    function normalizedGameVersion(value) {
        var raw = (value || "").toString().toLowerCase().replace(/[^a-z0-9.]/g, "")
        var alpha = raw.match(/^(alpha|a)(\d+(?:\.\d+)*)$/)
        if (alpha)
            return "alpha" + alpha[2]
        var modern = raw.match(/^v(\d+(?:\.\d+)*)$/)
        if (modern)
            return "v" + modern[1]
        return ""
    }

    function versionParts(value) {
        var normalized = normalizedGameVersion(value)
        if (!normalized)
            return null
        var alpha = normalized.indexOf("alpha") === 0
        var prefix = alpha ? "alpha" : "v"
        var number = normalized.substring(prefix.length)
        return {kind: prefix, parts: number.split(".").map(function(n) { return parseInt(n, 10) })}
    }

    function versionsMatch(selected, detected) {
        var selectedInfo = versionParts(selected)
        if (!selectedInfo)
            return false
        var values = detected || []
        for (var i = 0; i < values.length; ++i) {
            var candidateInfo = versionParts(values[i])
            if (!candidateInfo || candidateInfo.kind !== selectedInfo.kind)
                continue
            if (candidateInfo.parts.join(".") === selectedInfo.parts.join("."))
                return true
            if (candidateInfo.parts.length === 1 &&
                candidateInfo.parts[0] === selectedInfo.parts[0])
                return true
            if (selectedInfo.parts.length === 1 &&
                candidateInfo.parts[0] === selectedInfo.parts[0])
                return true
        }
        return false
    }

    function declaredModVersionFallback() {
        var raw = drawer.details.gameVersions || ""
        return raw.split(",").map(function(v) { return v.trim() }).filter(function(v) { return v !== "" })
    }

    function fileAllowedForSelection(file) {
        var detected = file.detectedGameVersions || []
        var selected = drawer.selectedGameVersion
        if (selected !== "")
            return detected.length > 0
                   ? versionsMatch(selected, detected)
                   : (declaredModVersionFallback().length === 1 &&
                      versionsMatch(selected, declaredModVersionFallback()))

        // Bez wybranego filtra nie wybieramy w ciemno pliku z nieznaną/
        // wielowersyjną kompatybilnością. Bezpieczny wyjątek: mod sam
        // deklaruje dokładnie jedną wersję gry.
        if (detected.length === 0)
            return declaredModVersionFallback().length === 1
        return detected.length === 1
    }

    function selectedVersionLabel() {
        var normalized = normalizedGameVersion(drawer.selectedGameVersion)
        if (!normalized)
            return drawer.selectedGameVersion || ""
        if (normalized.indexOf("alpha") === 0)
            return "Alpha " + normalized.substring(5)
        return normalized.toUpperCase()
    }

    parent: Overlay.overlay
    anchors.fill: parent
    z: 400
    visible: scrim.opacity > 0.001
    enabled: opened

    Keys.onEscapePressed: close()

    Connections {
        target: WebDetails
        function onReady(s, details) {
            if (s === drawer.slug) drawer.details = details
        }
        function onFailed(s, error) {
            if (s === drawer.slug) drawer.errorText = error
        }
    }

    // ---- scrim --------------------------------------------------------- #
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Theme.rgba(Theme.bg0, 0.55)
        opacity: drawer.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 160 } }
        MouseArea {
            anchors.fill: parent
            onClicked: drawer.close()
        }
    }

    // ---- card ----------------------------------------------------------- #
    Rectangle {
        id: panel
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: Math.min(640, parent.width - 60)
        color: Theme.bg1
        border.width: 1
        border.color: Theme.border
        x: drawer.opened ? parent.width - width : parent.width
        Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

        // panel konsumuje kliknięcia - nic nie przelatuje do scrima/UI pod spodem
        MouseArea {
            anchors.fill: parent
            onClicked: { /* klik w panel - ignorowany */ }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // header
            RowLayout {
                Layout.fillWidth: true
                Layout.margins: 18
                spacing: 12

                ColumnLayout {
                    spacing: 3
                    Layout.fillWidth: true
                    Text {
                        Layout.fillWidth: true
                        text: drawer.details.title !== undefined ? drawer.details.title : drawer.slug
                        color: Theme.text
                        font.pixelSize: Typography.h2
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: {
                            const d = drawer.details
                            const parts = []
                            if (d.author !== undefined && d.author !== "") parts.push(I18n.resolveMessage(d.author))
                            if (d.version !== undefined && d.version !== "") parts.push("v" + d.version)
                            if (d.categories !== undefined && d.categories !== "") parts.push(d.categories)
                            return parts.join(" · ")
                        }
                        color: Theme.textMuted
                        font.pixelSize: Typography.small
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                }

                IconButton {
                    icon: "external-link"
                    tooltip: I18n.t("discover.drawer.openModPage")
                    visible: drawer.details.url !== undefined
                    onClicked: Qt.openUrlExternally(drawer.details.url || "")
                }
                IconButton {
                    icon: "x"
                    tooltip: I18n.t("discover.drawer.close")
                    onClicked: drawer.close()
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.border }

            // body
            AppScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentHeight: drawerBody.implicitHeight

                ColumnLayout {
                    id: drawerBody
                    width: Math.max(0, parent.width - 36)
                    x: 18
                    spacing: 18

                    BusyIndicator {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 30
                        running: WebDetails.busy
                        visible: WebDetails.busy && drawer.details.title === undefined
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: 20
                        visible: drawer.errorText !== ""
                        text: drawer.errorText !== "" ? I18n.format("discover.drawer.detailsError", {error: drawer.errorText}) : ""
                        color: Theme.warning
                        font.pixelSize: Typography.small
                        font.family: Theme.fontFamily
                        wrapMode: Text.WordWrap
                    }

                    // ---- pliki ------------------------------------------------- #
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.topMargin: 10
                        spacing: 8
                        visible: drawer.details.files !== undefined && drawer.details.files.length > 0

                        Text {
                            Layout.topMargin: 4
                            text: I18n.t("discover.drawer.filesTitle")
                            color: Theme.textMuted
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.letterSpacing: Typography.trackingCaps
                            font.family: Theme.fontFamily
                        }

                        Repeater {
                            model: drawer.details.files !== undefined ? drawer.details.files : []

                            Rectangle {
                                id: fileRow
                                required property var modelData
                                readonly property string rowState: Downloads.modDownloads[fileRow.modelData.fileRef] || ""
                                readonly property string modState: Downloads.modDownloads[drawer.slug] || ""
                                readonly property bool rowBusy: ["queued", "downloading", "paused"].indexOf(rowState) >= 0
                                readonly property bool rowCompatible: drawer.fileAllowedForSelection(fileRow.modelData)
                                readonly property bool rowLocked: rowBusy || ["queued", "downloading", "paused", "completed"].indexOf(modState) >= 0 || !rowCompatible
                                Layout.fillWidth: true
                                implicitHeight: fileRow.rowCompatible ? 58 : 78
                                radius: 9
                                color: fileHover.hovered ? Theme.bg3 : Theme.bg2
                                border.width: 1
                                border.color: Theme.border

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 12
                                    anchors.rightMargin: 10
                                    spacing: 10

                                    Icon {
                                        name: !fileRow.rowCompatible ? "alert-triangle" : fileRow.modelData.verified ? "shield" : "package"
                                        tint: !fileRow.rowCompatible ? Theme.warning : fileRow.modelData.verified ? Theme.success : Theme.textMuted
                                        size: 16
                                        Layout.alignment: Qt.AlignVCenter
                                    }

                                    ColumnLayout {
                                        spacing: 1
                                        Layout.fillWidth: true

                                        Text {
                                            Layout.fillWidth: true
                                            text: I18n.resolveMessage(fileRow.modelData.label)
                                            color: Theme.text
                                            font.pixelSize: Typography.small + 1
                                            font.weight: Font.Medium
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: {
                                                const parts = []
                                                const typeLabels = {
                                                    main: I18n.t("discover.drawer.fileType.main"),
                                                    optional: I18n.t("discover.drawer.fileType.optional"),
                                                    old: I18n.t("discover.drawer.fileType.old"),
                                                    external: I18n.t("discover.drawer.fileType.external")
                                                }
                                                const t = fileRow.modelData.fileType
                                                parts.push(typeLabels[t] || t)
                                                if (fileRow.modelData.version !== "") parts.push("v" + fileRow.modelData.version)
                                                if (fileRow.modelData.sizeText !== "") parts.push(fileRow.modelData.sizeText)
                                                return parts.join(" · ")
                                            }
                                            color: Theme.textMuted
                                            font.pixelSize: Typography.caption
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            visible: !fileRow.rowCompatible
                                            text: drawer.selectedGameVersion !== ""
                                                  ? I18n.format("discover.drawer.fileIncompatible", {
                                                        version: drawer.selectedVersionLabel()
                                                    })
                                                  : I18n.t("discover.drawer.fileVersionUnknown")
                                            color: Theme.warning
                                            font.pixelSize: Typography.caption
                                            font.family: Theme.fontFamily
                                            elide: Text.ElideRight
                                        }
                                    }

                                    SecondaryButton {
                                        text: fileRow.rowBusy ? I18n.t("discover.download.queued") : fileRow.modState === "completed" ? I18n.t("discover.download.completed") : I18n.t("discover.download.action")
                                        icon: fileRow.rowBusy ? "clock" : fileRow.modState === "completed" ? "check" : "download"
                                        compact: true
                                        disabled: fileRow.rowLocked
                                        onClicked: Downloads.startModDownloadWithFileVersion(
                                            drawer.slug, fileRow.modelData.fileRef,
                                            drawer.selectedGameVersion ||
                                            (drawer.details.gameVersions || "").split(", ")[0] || "")
                                    }
                                }

                                HoverHandler { id: fileHover }
                            }
                        }
                    }

                    // ---- opis -------------------------------------------------- #
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        visible: drawer.details.description !== undefined && drawer.details.description !== ""

                        Text {
                            text: I18n.t("discover.drawer.description")
                            color: Theme.textMuted
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.letterSpacing: Typography.trackingCaps
                            font.family: Theme.fontFamily
                        }

                        Text {
                            Layout.fillWidth: true
                            text: drawer.details.description || ""
                            textFormat: Text.MarkdownText
                            color: Theme.textSecondary
                            font.pixelSize: Typography.small
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                        }
                    }

                    // ---- changelog --------------------------------------------- #
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        visible: drawer.details.changelog !== undefined && drawer.details.changelog.length > 0

                        Text {
                            text: I18n.t("discover.drawer.changelog")
                            color: Theme.textMuted
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.letterSpacing: Typography.trackingCaps
                            font.family: Theme.fontFamily
                        }

                        Repeater {
                            model: drawer.details.changelog !== undefined ? drawer.details.changelog : []

                            ColumnLayout {
                                id: logEntry
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 2

                                Text {
                                    Layout.fillWidth: true
                                    text: (logEntry.modelData.version !== "" ? "v" + logEntry.modelData.version : "?")
                                          + (logEntry.modelData.date !== "" ? "  ·  " + logEntry.modelData.date : "")
                                    color: Theme.text
                                    font.pixelSize: Typography.small
                                    font.weight: Font.DemiBold
                                    font.family: Theme.fontFamily
                                }
                                Text {
                                    Layout.fillWidth: true
                                    visible: logEntry.modelData.changelog !== ""
                                    text: logEntry.modelData.changelog
                                    textFormat: Text.MarkdownText
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.caption + 0.5
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true; Layout.minimumHeight: 20 }
                }
            }
        }
    }
}
