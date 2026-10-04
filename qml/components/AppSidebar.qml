import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Fixed application sidebar: logo, primary navigation, settings, version.
Item {
    id: sidebar

    signal navigateRequested(string page)

    property string activePage: "dashboard"
    property int updatesCount: 0
    property int downloadsActive: 0
    property bool titleBarDragEnabled: true

    implicitWidth: Dimensions.sidebarW

    // ------------------------------------------------------------------ #
    // navigation model
    // ------------------------------------------------------------------ #
    readonly property var navItems: [
        { page: "dashboard", key: "nav.dashboard", icon: "grid", badge: "none" },
        { page: "profiles",  key: "nav.instances", icon: "layers", badge: "none" },
        { page: "steam_releases", key: "nav.steamReleases", icon: "download", badge: "none" },
        { page: "game_profiles", key: "nav.gameProfiles", icon: "file-text", badge: "none" },
        { page: "discover",  key: "nav.discover", icon: "globe", badge: "" },
        { page: "mods",      key: "nav.mods", icon: "package", badge: "none" },
        { page: "modpacks",  key: "nav.backups", icon: "backpack", badge: "none" },
        { page: "updates",   key: "nav.updates", icon: "refresh-cw", badge: "count" },
        { page: "downloads", key: "nav.downloads", icon: "download", badge: "dot" }
    ]

    Rectangle {
        anchors.fill: parent
        color: Theme.bg1
    }

    Rectangle {
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 1
        color: Theme.border
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.topMargin: 18
        anchors.bottomMargin: 16
        anchors.leftMargin: 14
        anchors.rightMargin: 14
        spacing: 4

        // ---- logo -------------------------------------------------------- #
        Item {
            id: logoArea
            Layout.fillWidth: true
            Layout.bottomMargin: 22
            implicitHeight: 52

            // window drag handle (custom title bar)
            MouseArea {
                anchors.fill: parent
                enabled: sidebar.titleBarDragEnabled
                onPressed: (mouse) => {
                    const win = ApplicationWindow.window
                    if (win) win.startSystemMove()
                }
            }

            RowLayout {
                anchors.fill: parent
                spacing: 12

                Image {
                    source: Qt.resolvedUrl("../../assets/icons/app-icon.svg")
                    sourceSize.width: 44
                    sourceSize.height: 44
                    Layout.alignment: Qt.AlignVCenter
                }

                ColumnLayout {
                    spacing: 1
                    Layout.alignment: Qt.AlignVCenter

                    Text {
                        text: "7DTD"
                        color: Theme.text
                        font.pixelSize: Typography.h2 + 2
                        font.weight: Font.Bold
                        font.family: Theme.fontFamily
                    }

                    Text {
                        text: I18n.t("brand.manager")
                        color: Theme.accent
                        font.pixelSize: Typography.micro
                        font.weight: Font.DemiBold
                        font.letterSpacing: Typography.trackingWider
                        font.family: Theme.fontFamily
                    }
                }
            }
        }

        // ---- primary navigation ------------------------------------------ #
        Repeater {
            model: sidebar.navItems

            SidebarNavItem {
                required property var modelData
                pageName: modelData.page
                label: I18n.t(modelData.key)
                icon: modelData.icon
                active: sidebar.activePage === modelData.page
                badgeCount: modelData.badge === "count" ? sidebar.updatesCount : -1
                showDot: modelData.badge === "dot" && sidebar.downloadsActive > 0
                Layout.fillWidth: true
                onNav: (page) => sidebar.navigateRequested(page)
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.fillWidth: true
            height: 1
            color: Theme.border
            Layout.bottomMargin: 4
        }

        // ---- settings ----------------------------------------------------- #
        SidebarNavItem {
            pageName: "settings"
            label: I18n.t("nav.settings")
            icon: "sliders"
            active: sidebar.activePage === "settings"
            Layout.fillWidth: true
            onNav: (page) => sidebar.navigateRequested(page)
        }

        // ---- version footer ------------------------------------------------ #
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 14
            spacing: 6

            Rectangle {
                width: 5
                height: 5
                radius: 3
                color: Theme.success
                opacity: 0.8
            }

            Text {
                text: "v" + App.version
                color: Theme.textMuted
                font.pixelSize: Typography.caption
                font.family: Theme.fontFamily
            }

            Item { Layout.fillWidth: true }

            Text {
                text: "7DTD"
                color: Theme.textFaint
                font.pixelSize: Typography.micro
                font.letterSpacing: Typography.trackingWide
                font.family: Theme.fontFamily
            }
        }
    }

    // ------------------------------------------------------------------ #
    component SidebarNavItem: Item {
        id: navItem

        signal nav(string page)

        property string pageName: ""
        property string label: ""
        property string icon: ""
        property bool active: false
        property int badgeCount: -1
        property bool showDot: false

        implicitHeight: 42

        Rectangle {
            anchors.fill: parent
            radius: 10
            color: navItem.active ? Theme.accentSoft
                 : (hover.hovered ? Theme.bg3 : "transparent")
            Behavior on color { ColorAnimation { duration: Theme.fast } }
        }

        // left accent indicator
        Rectangle {
            visible: navItem.active
            width: 3
            radius: 2
            anchors.left: parent.left
            anchors.leftMargin: -7
            anchors.top: parent.top
            anchors.topMargin: 9
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 9
            color: Theme.accent

            Behavior on opacity { NumberAnimation { duration: Theme.normal } }
        }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 10
            spacing: 12

            Icon {
                name: navItem.icon
                size: 18
                tint: navItem.active ? Theme.accent
                     : (hover.hovered ? Theme.text : Theme.textSecondary)
                Layout.alignment: Qt.AlignVCenter
                Behavior on tint { ColorAnimation { duration: Theme.fast } }
            }

            Text {
                text: navItem.label
                color: navItem.active ? Theme.text
                     : (hover.hovered ? Theme.text : Theme.textSecondary)
                font.pixelSize: Typography.body
                font.weight: navItem.active ? Font.DemiBold : Font.Medium
                font.family: Theme.fontFamily
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                Behavior on color { ColorAnimation { duration: Theme.fast } }
            }

            // active downloads dot
            Rectangle {
                visible: navItem.showDot
                width: 9
                height: 9
                radius: 5
                color: Theme.accent
                Layout.alignment: Qt.AlignVCenter

                SequentialAnimation on opacity {
                    running: navItem.showDot && Theme.animationsEnabled
                    loops: Animation.Infinite
                    NumberAnimation { from: 1.0; to: 0.35; duration: 900; easing.type: Easing.InOutQuad }
                    NumberAnimation { from: 0.35; to: 1.0; duration: 900; easing.type: Easing.InOutQuad }
                }
            }

            // updates count badge
            Rectangle {
                visible: navItem.badgeCount > 0
                width: badgeText.implicitWidth + 12
                height: 20
                radius: 10
                color: Theme.accentSoftUp
                Layout.alignment: Qt.AlignVCenter

                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: navItem.badgeCount
                    color: Theme.accent
                    font.pixelSize: Typography.caption
                    font.weight: Font.DemiBold
                    font.family: Theme.fontFamily
                }
            }
        }

        HoverHandler { id: hover }
        TapHandler { onTapped: navItem.nav(navItem.pageName) }
    }
}
