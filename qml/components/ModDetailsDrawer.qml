import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Right-side details drawer with slide-in animation.
// Usage:  ModDetailsDrawer { id: drawer }   /   drawer.openWith("mod-id")
Item {
    id: drawer

    property bool opened: false
    property string modId: ""
    property var modData: ({})

    readonly property color catColor: modData.category !== undefined ? Theme.catColor(modData.category) : Theme.accent

    // baner z miniaturą: tekst zawsze JASNY na przyciemnionym zdjęciu
    // (niezależnie od motywu); bez miniatury - kolory motywu
    readonly property bool hasImage: modData.thumbUrl !== undefined && modData.thumbUrl !== ""
    readonly property color bannerText: hasImage ? "#F2F5FA" : Theme.text
    readonly property color bannerMuted: hasImage ? "#AEB9CC" : Theme.textMuted

    function openWith(id) {
        modId = id
        modData = Mods.modDetails(id)
        opened = true
        drawer.forceActiveFocus()
    }

    function close() {
        opened = false
    }

    function reload() {
        if (modId !== "" && Mods !== null) modData = Mods.modDetails(modId)
    }

    parent: Overlay.overlay
    anchors.fill: parent
    z: 400
    visible: scrim.opacity > 0.001
    enabled: opened

    Keys.onEscapePressed: close()

    Connections {
        target: Mods
        function onModChanged(id) {
            if (id === drawer.modId) drawer.reload()
        }
        function onModRemoved(id) {
            if (id === drawer.modId) drawer.close()
        }
    }

    // ---- scrim ------------------------------------------------------------ #
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Theme.scrimColor
        opacity: drawer.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.normal } }

        // MouseArea (nie pasywny TapHandler!) - konsumuje kliknięcia, żeby
        // nie trafiały w przyciski strony pod spodem (bug klasy D24)
        MouseArea {
            anchors.fill: parent
            onClicked: drawer.close()
        }
    }

    // ---- panel ------------------------------------------------------------ #
    Item {
        id: panel
        width: 480
        height: parent.height
        x: drawer.opened ? parent.width - width : parent.width

        Behavior on x { NumberAnimation { duration: Theme.slow; easing.type: Easing.OutQuint } }

        SoftShadow { source: panelBg; elevation: 3 }

        Rectangle {
            id: panelBg
            anchors.fill: parent
            color: Theme.bg1
            border.width: 1
            border.color: Theme.borderHover
        }

        // panel konsumuje kliknięcia w tło/kartę - nic nie przelatuje do UI
        // pod spodem; deklarowane PRZED treścią, więc realne kontrolki
        // (przyciski, przełączniki) siedzą wyżej i działają normalnie
        MouseArea {
            anchors.fill: parent
            onClicked: { /* klik w panel - ignorowany */ }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ---- banner -------------------------------------------------- #
            Item {
                Layout.fillWidth: true
                implicitHeight: 176
                clip: true

                // miniatura moda na całą szerokość banera (etap 17);
                // PRZYCZEMNIONA (jasne fotki zabijają czytelność tekstu),
                // ciemny gradient poziomy pod tytuł/autor/wersję
                Image {
                    anchors.fill: parent
                    source: drawer.modData.thumbUrl !== undefined ? drawer.modData.thumbUrl : ""
                    visible: drawer.modData.thumbUrl !== undefined && drawer.modData.thumbUrl !== ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }

                Rectangle {
                    anchors.fill: parent
                    visible: drawer.modData.thumbUrl !== undefined && drawer.modData.thumbUrl !== ""
                    color: Theme.rgba(Theme.imageOverlay, 0.38)
                }

                Rectangle {
                    anchors.fill: parent
                    visible: drawer.modData.thumbUrl !== undefined && drawer.modData.thumbUrl !== ""
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.rgba(Theme.imageOverlay, 0.8) }
                        GradientStop { position: 0.55; color: Theme.rgba(Theme.imageOverlay, 0.4) }
                        GradientStop { position: 1.0; color: Theme.rgba(Theme.imageOverlay, 0.12) }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    visible: !drawer.hasImage
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.rgba(drawer.catColor, 0.32) }
                        GradientStop { position: 1.0; color: Theme.bg1 }
                    }
                }

                // watermark icon (tylko gdy brak miniatury)
                Icon {
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    anchors.verticalCenter: parent.verticalCenter
                    name: Theme.catIcon(drawer.modData.category !== undefined ? drawer.modData.category : "Gameplay")
                    tint: Theme.rgba(drawer.catColor, 0.55)
                    size: 92
                    visible: !(drawer.modData.thumbUrl !== undefined && drawer.modData.thumbUrl !== "")
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 1
                    color: Theme.border
                }

                ColumnLayout {
                    anchors.left: parent.left
                    anchors.leftMargin: 26
                    anchors.right: parent.right
                    anchors.rightMargin: 26
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 18
                    spacing: 6

                    Text {
                        text: drawer.modData.name !== undefined ? drawer.modData.name : ""
                        color: drawer.bannerText
                        font.pixelSize: Typography.h1
                        font.weight: Font.Bold
                        font.family: Theme.fontFamily
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }

                    RowLayout {
                        spacing: 8

                        Text {
                            text: drawer.modData.version !== undefined ? ("v" + drawer.modData.version) : ""
                            color: drawer.bannerMuted
                            font.pixelSize: Typography.small
                            font.weight: Font.Medium
                            font.family: Theme.fontFamily
                        }

                        Text {
                            visible: drawer.modData.newVersion !== undefined && drawer.modData.newVersion !== ""
                            text: (drawer.modData.newVersion !== undefined && drawer.modData.newVersion !== "")
                                  ? "→ v" + drawer.modData.newVersion : ""
                            color: Theme.accent
                            font.pixelSize: Typography.small
                            font.weight: Font.DemiBold
                            font.family: Theme.fontFamily
                        }

                        Text {
                            text: drawer.modData.author !== undefined ? I18n.format("mod.drawer.author", {author: drawer.modData.author}) : ""
                            color: drawer.bannerMuted
                            font.pixelSize: Typography.small
                            font.family: Theme.fontFamily
                        }
                    }
                }

                IconButton {
                    anchors.top: parent.top
                    anchors.topMargin: 14
                    anchors.right: parent.right
                    anchors.rightMargin: 14
                    icon: "x"
                    tooltip: I18n.t("mod.drawer.close")
                    onClicked: drawer.close()
                }
            }

            // ---- scrollable content --------------------------------------- #
            Flickable {
                id: flick
                Layout.fillWidth: true
                Layout.fillHeight: true
                contentWidth: width
                contentHeight: contentCol.implicitHeight + 40
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                flickDeceleration: 5200
                maximumFlickVelocity: 1800

                ScrollBar.vertical: AppScrollBar {}

                WheelHandler {
                    target: null
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    onWheel: (event) => {
                        const maxY = Math.max(0, flick.contentHeight - flick.height)
                        if (maxY <= 0) { event.accepted = false; return }
                        flick.cancelFlick()
                        const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
                        flick.contentY = Math.max(0, Math.min(maxY, flick.contentY - step))
                        event.accepted = true
                    }
                }

                ColumnLayout {
                    id: contentCol
                    x: 26
                    y: 22
                    width: flick.width - 52
                    spacing: 18

                    // badges
                    RowLayout {
                        spacing: 8

                        StatusBadge {
                            key: drawer.modData.inConflict ? "conflict"
                                : drawer.modData.hasUpdate ? "update"
                                : drawer.modData.enabled ? "enabled" : "disabled"
                        }

                        StatusBadge {
                            visible: drawer.modData.hasUpdate === true
                            key: "update"
                            label: "v" + (drawer.modData.newVersion || "")
                        }
                    }

                    // stat rows
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 12
                        rowSpacing: 10

                        DetailStat { icon: "hard-drive"; label: I18n.t("mod.drawer.size");      value: drawer.modData.sizeText !== undefined ? drawer.modData.sizeText : "-" }
                        DetailStat { icon: "star";       label: I18n.t("mod.drawer.rating");   value: drawer.modData.rating !== undefined ? (drawer.modData.rating + " / 5") : "-" }
                        DetailStat { icon: "download";   label: I18n.t("mod.drawer.downloads"); value: drawer.modData.downloadsText !== undefined ? drawer.modData.downloadsText : "-" }
                        DetailStat { icon: "calendar";   label: I18n.t("mod.drawer.installed"); value: drawer.modData.installedText !== undefined ? I18n.resolveMessage(drawer.modData.installedText) : "-" }
                        DetailStat { icon: "clock";      label: I18n.t("mod.drawer.updated");  value: drawer.modData.updatedText !== undefined ? I18n.resolveMessage(drawer.modData.updatedText) : "-" }
                        DetailStat { icon: "tag";        label: I18n.t("mod.drawer.game");     value: drawer.modData.gameVersion !== undefined ? drawer.modData.gameVersion : "-" }
                    }

                    // description
                    ColumnLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        DrawerSectionLabel { text: I18n.t("mod.drawer.description") }

                        Text {
                            Layout.fillWidth: true
                            text: drawer.modData.description !== undefined ? drawer.modData.description : ""
                            color: Theme.textSecondary
                            font.pixelSize: Typography.body
                            font.family: Theme.fontFamily
                            wrapMode: Text.WordWrap
                            lineHeight: 1.45
                        }
                    }

                    // tags
                    ColumnLayout {
                        spacing: 8
                        Layout.fillWidth: true
                        visible: drawer.modData.tags !== undefined && drawer.modData.tags.length > 0

                        DrawerSectionLabel { text: I18n.t("mod.drawer.tags") }

                        Flow {
                            spacing: 6
                            Layout.fillWidth: true

                            Repeater {
                                model: drawer.modData.tags !== undefined ? drawer.modData.tags : []

                                Rectangle {
                                    required property var modelData
                                    width: tagLabel.implicitWidth + 16
                                    height: 22
                                    radius: 6
                                    color: Theme.bg3
                                    border.width: 1
                                    border.color: Theme.border

                                    Text {
                                        id: tagLabel
                                        anchors.centerIn: parent
                                        text: parent.modelData
                                        color: Theme.textSecondary
                                        font.pixelSize: Typography.caption
                                        font.family: Theme.fontFamily
                                    }
                                }
                            }
                        }
                    }

                    // requirements & dependencies
                    ColumnLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        DrawerSectionLabel { text: I18n.t("mod.drawer.requirements") }

                        Text {
                            Layout.fillWidth: true
                            text: "7 Days to Die " + (drawer.modData.gameVersion !== undefined ? drawer.modData.gameVersion : "")
                            color: Theme.textSecondary
                            font.pixelSize: Typography.small
                            font.family: Theme.fontFamily
                        }
                    }

                    ColumnLayout {
                        spacing: 8
                        Layout.fillWidth: true

                        DrawerSectionLabel { text: I18n.t("mod.drawer.dependencies") }

                        Text {
                            Layout.fillWidth: true
                            visible: !drawer.modData.dependencies || drawer.modData.dependencies.length === 0
                            text: I18n.t("mod.drawer.noDependencies")
                            color: Theme.textMuted
                            font.pixelSize: Typography.small
                            font.family: Theme.fontFamily
                        }

                        Repeater {
                            model: drawer.modData.dependencies !== undefined ? drawer.modData.dependencies : []

                            RowLayout {
                                required property var modelData
                                spacing: 8
                                Layout.fillWidth: true

                                Icon { name: "chevron-right"; size: 12; tint: Theme.textMuted }
                                Text {
                                    text: parent.modelData
                                    color: Theme.textSecondary
                                    font.pixelSize: Typography.small
                                    font.family: Theme.fontFamily
                                }
                            }
                        }
                    }

                    // conflicts
                    ColumnLayout {
                        spacing: 10
                        Layout.fillWidth: true
                        visible: drawer.modData.conflictNames !== undefined && drawer.modData.conflictNames.length > 0

                        DrawerSectionLabel { text: I18n.t("mod.drawer.conflicts") }

                        Rectangle {
                            Layout.fillWidth: true
                            implicitHeight: conflictCol.implicitHeight + 28
                            radius: Dimensions.radiusMd
                            color: Theme.warningSoft
                            border.width: 1
                            border.color: Theme.rgba(Theme.warning, 0.3)

                            ColumnLayout {
                                id: conflictCol
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 6

                                Icon {
                                    name: "alert-triangle"
                                    tint: Theme.warning
                                    size: 17
                                }

                                Text {
                                    Layout.fillWidth: true
                                    text: I18n.format("mod.drawer.conflictsWith", {names: (drawer.modData.conflictNames || []).join(", ")})
                                    color: Theme.warning
                                    font.pixelSize: Typography.small
                                    font.weight: Font.Medium
                                    font.family: Theme.fontFamily
                                    wrapMode: Text.WordWrap
                                }

                                SecondaryButton {
                                    text: I18n.t("mod.drawer.viewConflicts")
                                    compact: true
                                    onClicked: { drawer.close(); Bus.goTo("conflicts") }
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }
                }
            }

            // ---- footer --------------------------------------------------- #
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 78
                color: Theme.bg1

                Rectangle {
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 1
                    color: Theme.border
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 22
                    anchors.rightMargin: 22
                    spacing: 10

                    PrimaryButton {
                        Layout.fillWidth: true
                        text: drawer.modData.enabled === true ? I18n.t("mod.drawer.disable") : I18n.t("mod.drawer.enable")
                        icon: drawer.modData.enabled === true ? "x" : "check"
                        danger: drawer.modData.enabled === true
                        onClicked: {
                            Mods.toggleMod(drawer.modId)
                            drawer.reload()
                        }
                    }

                    IconButton {
                        icon: "folder"
                        tooltip: I18n.t("mod.drawer.openFolder")
                        buttonSize: 42
                        iconSize: 17
                        onClicked: Mods.openFolder(drawer.modId)
                    }

                    IconButton {
                        icon: "trash"
                        tooltip: I18n.t("mod.drawer.uninstall")
                        buttonSize: 42
                        iconSize: 17
                        danger: true
                        onClicked: uninstallConfirm.open()
                    }
                }
            }
        }

        // uninstall confirmation
        ConfirmModal {
            id: uninstallConfirm
            title: I18n.t("mod.drawer.uninstallTitle")
            message: I18n.format("mod.drawer.uninstallMessage", {name: drawer.modData.name || I18n.t("mod.drawer.unnamed")})
            confirmLabel: I18n.t("mod.drawer.uninstall")
            danger: true
            onConfirmed: {
                drawer.close()
                Mods.uninstallMod(drawer.modId)
            }
        }
    }

    component DrawerSectionLabel: Text {
        color: Theme.textMuted
        font.pixelSize: Typography.micro + 0.5
        font.weight: Font.DemiBold
        font.letterSpacing: Typography.trackingCaps
        font.family: Theme.fontFamily
    }

    component DetailStat: RowLayout {
        property string icon: ""
        property string label: ""
        property string value: ""

        spacing: 9
        Layout.fillWidth: true

        Rectangle {
            width: 30
            height: 30
            radius: 9
            color: Theme.bg2
            border.width: 1
            border.color: Theme.border
            Layout.alignment: Qt.AlignVCenter

            Icon {
                anchors.centerIn: parent
                name: parent.parent.icon
                tint: Theme.textSecondary
                size: 14
            }
        }

        ColumnLayout {
            spacing: 1
            Layout.fillWidth: true

            Text {
                text: label
                color: Theme.textMuted
                font.pixelSize: Typography.micro
                font.letterSpacing: Typography.trackingWide
                font.family: Theme.fontFamily
            }

            Text {
                text: value
                color: Theme.text
                font.pixelSize: Typography.small + 0.5
                font.weight: Font.Medium
                font.family: Theme.fontFamily
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }
}
