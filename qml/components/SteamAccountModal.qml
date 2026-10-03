import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Konto Steam ma dwa tryby:
// 1) aktywna sesja -> mały, nieblokujący panel zakotwiczony pod ikonką,
//    podobny do menu powiadomień;
// 2) brak sesji / ponowne logowanie -> pełny modal z kodem QR.
Item {
    id: root
    objectName: "steamAccountModal"

    property Item anchorItem: null
    property Item menuParent: null
    property bool accountMenuOpen: false
    property bool opened: accountMenuOpen || qrModal.opened

    // mapToItem() nie jest śledzone przez bindingi QML, więc pozycję menu
    // przeliczamy wymuszając re-ewaluację przez layoutTick: przy otwarciu
    // (także po ustabilizowaniu layoutu) oraz gdy ikonka/nagłówek zmienią
    // rozmiar lub położenie (np. zmiana rozmiaru okna).
    property int layoutTick: 0
    onAccountMenuOpenChanged: {
        if (accountMenuOpen) {
            layoutTick++
            Qt.callLater(function() { root.layoutTick++ })
        }
    }

    Connections {
        target: root.anchorItem
        ignoreUnknownSignals: true
        function onXChanged() { root.layoutTick++ }
        function onYChanged() { root.layoutTick++ }
        function onWidthChanged() { root.layoutTick++ }
    }

    Connections {
        target: root.menuParent
        ignoreUnknownSignals: true
        function onWidthChanged() { root.layoutTick++ }
        function onHeightChanged() { root.layoutTick++ }
    }

    function open() {
        // Dla zapisanej sesji używamy zwykłego panelu typu menu/powiadomienie.
        // Nie korzystamy tu z Controls.Popup, ponieważ panel jest wtedy
        // w 100% kontrolowany przez naszą warstwę Overlay i nie może
        // „zniknąć” przez błędne pozycjonowanie względem komponentu nagłówka.
        if (GameVersions.hasSavedSession) {
            if (accountMenuOpen) {
                accountMenuOpen = false
                return
            }
            qrModal.close()
            accountMenuOpen = true
        } else {
            accountMenuOpen = false
            if (qrModal.opened) {
                qrModal.close()
                return
            }
            Qt.callLater(function() {
                if (!GameVersions.hasSavedSession && !qrModal.opened)
                    qrModal.open()
            })
        }
    }

    function close() {
        accountMenuOpen = false
        qrModal.close()
    }

    function openQrLogin() {
        accountMenuOpen = false
        Qt.callLater(function() {
            if (!qrModal.opened)
                qrModal.open()
        })
    }

    // Warstwa do zamykania menu kliknięciem poza kartą. Jest widoczna tylko
    // kiedy menu konta jest otwarte i nie posiada własnego tła - blokuje
    // jedynie zdarzenie pod spodem i od razu je zamyka.
    Item {
        id: accountDismissLayer
        parent: Overlay.overlay
        anchors.fill: parent
        visible: root.accountMenuOpen
        z: 9

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: root.accountMenuOpen = false
        }
    }

    // Menu leży w tym samym rodzicu co warstwa zamykająca (Overlay.overlay),
    // ale z wyższym z - dzięki temu przyciski dostają kliknięcia, a nie
    // niewidzialna warstwa przykrywająca całe okno. menuParent (nagłówek)
    // służy tylko jako punkt odniesienia: menu zaczyna się pod jego dolną
    // krawędzią i jest wyrównane do prawej krawędzi ikonki konta.
    Rectangle {
        id: accountMenu
        objectName: "steamAccountMenu"
        parent: Overlay.overlay
        visible: root.accountMenuOpen
        z: 1090
        width: Math.min(348, Math.max(300, (Overlay.overlay ? Overlay.overlay.width : 348) - 24))
        height: 186
        radius: Dimensions.radiusLg
        color: Theme.bg2
        border.width: 1
        border.color: Theme.borderHover
        x: {
            root.layoutTick
            const host = Overlay.overlay
            if (!host)
                return 12
            const right = accountAnchorRight(host)
            return Math.max(12, Math.min(host.width - width - 12, right - width))
        }
        y: {
            root.layoutTick
            const host = Overlay.overlay
            return host ? accountAnchorTopBoundary(host) : Dimensions.headerH
        }

        function accountAnchorRight(host) {
            if (!root.anchorItem)
                return host.width - 12
            return root.anchorItem.mapToItem(host, root.anchorItem.width, 0).x
        }

        function accountAnchorTopBoundary(host) {
            // Panel zaczyna się dokładnie na dolnej krawędzi nagłówka.
            if (root.menuParent)
                return root.menuParent.mapToItem(host, 0, root.menuParent.height).y
            if (!root.anchorItem)
                return Dimensions.headerH
            return root.anchorItem.mapToItem(host, 0, root.anchorItem.height).y
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: 11

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 40
                    height: 40
                    radius: 11
                    color: Theme.rgba(Theme.success, 0.13)
                    border.width: 1
                    border.color: Theme.rgba(Theme.success, 0.28)
                    Layout.alignment: Qt.AlignVCenter

                    Icon {
                        anchors.centerIn: parent
                        name: "user"
                        tint: Theme.success
                        size: 18
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: I18n.t("steamAccount.title")
                        color: Theme.text
                        font.pixelSize: Typography.body
                        font.weight: Font.DemiBold
                        font.family: Theme.fontFamily
                    }

                    Text {
                        Layout.fillWidth: true
                        text: I18n.format("steamAccount.connectedAs", {username: GameVersions.steamUsername})
                        color: Theme.textMuted
                        font.pixelSize: Typography.caption
                        font.family: Theme.fontFamily
                        elide: Text.ElideRight
                    }
                }

                Text {
                    text: I18n.t("steamAccount.connected")
                    color: Theme.success
                    font.pixelSize: Typography.micro
                    font.weight: Font.Bold
                    font.letterSpacing: Typography.trackingWide
                    font.family: Theme.fontFamily
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: Theme.border
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                SecondaryButton {
                    text: I18n.t("steamAccount.loginAgain")
                    icon: "user"
                    compact: true
                    onClicked: root.openQrLogin()
                }

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    text: I18n.t("steamAccount.logout")
                    icon: "x"
                    compact: true
                    onClicked: {
                        accountMenuOpen = false
                        GameVersions.logout()
                    }
                }
            }
        }
    }

    Modal {
        id: qrModal
        title: GameVersions.hasSavedSession ? I18n.t("steamAccount.reloginTitle") : I18n.t("steamAccount.connectTitle")
        iconName: "user"
        iconTint: Theme.accent
        cardWidth: 560

        function maybeStartAuth() {
            if (qrModal.opened && !GameVersions.hasSavedSession && !GameVersions.busy)
                GameVersions.startAuth()
        }

        onOpenedChanged: {
            if (opened)
                Qt.callLater(function() {
                    if (GameVersions.hasSavedSession)
                        GameVersions.reauthorize()
                    else
                        maybeStartAuth()
                })
            else if (GameVersions.busy && GameVersions.needsQr)
                GameVersions.cancel()
        }

        Connections {
            target: GameVersions
            function onChanged() { qrModal.maybeStartAuth() }
            function onAccountConnected(_username) { qrModal.close() }
        }

        AppScrollView {
            Layout.fillWidth: true
            Layout.preferredHeight: 540
            showScrollBar: false
            contentHeight: accountColumn.implicitHeight

            ColumnLayout {
                id: accountColumn
                width: Math.max(0, parent.width - 48)
                spacing: 16

                Rectangle {
                    visible: GameVersions.needsQr
                    Layout.fillWidth: true
                    Layout.preferredHeight: 420
                    radius: Dimensions.radiusMd
                    color: Theme.bg1
                    border.width: 1
                    border.color: Theme.rgba(Theme.accent, 0.45)

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: 14

                        Text {
                            Layout.alignment: Qt.AlignHCenter
                            text: I18n.t("steamAccount.qrHeader")
                            color: Theme.accent
                            font.pixelSize: Typography.micro + 0.5
                            font.weight: Font.DemiBold
                            font.letterSpacing: Typography.trackingCaps
                            font.family: Theme.fontFamily
                        }

                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            width: 240
                            height: 240
                            radius: 10
                            color: "#ffffff"

                            Image {
                                anchors.fill: parent
                                anchors.margins: 6
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
                            Layout.alignment: Qt.AlignHCenter
                            text: I18n.t("steamAccount.qrInstruction")
                            color: Theme.textMuted
                            font.pixelSize: Typography.caption
                            font.family: Theme.fontFamily
                        }
                    }
                }

                Rectangle {
                    visible: !GameVersions.needsQr
                    Layout.fillWidth: true
                    implicitHeight: 104
                    radius: 14
                    color: Theme.rgba(Theme.success, 0.055)
                    border.width: 1
                    border.color: Theme.rgba(Theme.success, 0.25)

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Icon {
                            name: "check"
                            tint: Theme.success
                            size: 22
                            Layout.alignment: Qt.AlignVCenter
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            Text {
                                text: I18n.t("steamAccount.readyTitle")
                                color: Theme.text
                                font.pixelSize: Typography.body
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }

                            Text {
                                Layout.fillWidth: true
                                text: I18n.t("steamAccount.readyMessage")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                Rectangle {
                    visible: GameVersions.busy && GameVersions.downloadingBranch !== ""
                    Layout.fillWidth: true
                    implicitHeight: 78
                    radius: 12
                    color: Theme.bg2
                    border.width: 1
                    border.color: Theme.rgba(Theme.accent, 0.22)

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Icon { name: "download"; size: 17; tint: Theme.accent }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                text: I18n.format("steamAccount.downloadingVersion", {branch: GameVersions.downloadingBranch})
                                color: Theme.text
                                font.pixelSize: Typography.small
                                font.weight: Font.DemiBold
                                font.family: Theme.fontFamily
                            }
                            Text {
                                text: I18n.t("steamAccount.downloadControlHint")
                                color: Theme.textMuted
                                font.pixelSize: Typography.caption
                                font.family: Theme.fontFamily
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }

        footer: [
            SecondaryButton {
                text: I18n.t("steamAccount.cancelLogin")
                icon: "x"
                onClicked: {
                    if (GameVersions.busy && GameVersions.needsQr)
                        GameVersions.cancel()
                    qrModal.close()
                }
            }
        ]
    }
}
