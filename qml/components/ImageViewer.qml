import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Pełnoekranowy podgląd zrzutów ekranu w obrębie okna launchera.
// Użycie:  ImageViewer { id: viewer }  /  viewer.openAt(images, index)
// Strzałki w lewo/prawo (przyciski albo klawiatura) zmieniają zdjęcie,
// Esc albo klik w tło zamyka sam podgląd (drawer pod spodem zostaje).
Item {
    id: viewer

    property bool opened: false
    property var images: []
    property int currentIndex: 0

    readonly property int count: images ? images.length : 0
    readonly property bool multiple: count > 1
    readonly property string currentSource: count > 0 ? String(images[currentIndex] || "") : ""

    signal closed()

    function openAt(list, index) {
        images = list || []
        currentIndex = Math.max(0, Math.min(index || 0, count - 1))
        opened = count > 0
        if (opened)
            viewer.forceActiveFocus()
    }

    function close() {
        if (!opened)
            return
        opened = false
        closed()
    }

    function next() {
        if (multiple)
            currentIndex = (currentIndex + 1) % count
    }

    function prev() {
        if (multiple)
            currentIndex = (currentIndex - 1 + count) % count
    }

    anchors.fill: parent
    z: 100
    visible: backdrop.opacity > 0.001
    enabled: opened
    focus: opened

    Keys.onEscapePressed: (event) => { viewer.close(); event.accepted = true }
    Keys.onLeftPressed: (event) => { viewer.prev(); event.accepted = true }
    Keys.onRightPressed: (event) => { viewer.next(); event.accepted = true }

    // ---- tło: klik poza zdjęciem zamyka podgląd ------------------------- #
    Rectangle {
        id: backdrop
        anchors.fill: parent
        color: "#FA050608"
        opacity: viewer.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 140 } }

        MouseArea {
            anchors.fill: parent
            onClicked: viewer.close()
        }
    }

    // ---- zdjęcie -------------------------------------------------------- #
    Item {
        id: stage
        anchors.fill: parent
        anchors.leftMargin: 92
        anchors.rightMargin: 92
        anchors.topMargin: 64
        anchors.bottomMargin: 40
        opacity: viewer.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 140 } }

        Image {
            id: bigImage
            anchors.fill: parent
            source: viewer.opened ? viewer.currentSource : ""
            asynchronous: true
            cache: true
            fillMode: Image.PreserveAspectFit
            // nie ładujemy w pamięci więcej niż potrzeba nawet dla 8K
            sourceSize.width: 3000
            sourceSize.height: 3000
            smooth: true
            mipmap: true
        }

        // klik w samo zdjęcie nic nie robi (nie zamyka podglądu),
        // tylko pochłania kliknięcie, żeby nie doszło do tła
        MouseArea {
            x: bigImage.x + (bigImage.width - bigImage.paintedWidth) / 2
            y: bigImage.y + (bigImage.height - bigImage.paintedHeight) / 2
            width: bigImage.paintedWidth
            height: bigImage.paintedHeight
            onClicked: { /* pochłonięte */ }
            onWheel: (wheel) => {
                if (wheel.angleDelta.y < 0 || wheel.angleDelta.x < 0)
                    viewer.next()
                else if (wheel.angleDelta.y > 0 || wheel.angleDelta.x > 0)
                    viewer.prev()
            }
        }

        BusyIndicator {
            anchors.centerIn: parent
            running: bigImage.status === Image.Loading
            visible: running
        }

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 8
            visible: bigImage.status === Image.Error
            Icon {
                Layout.alignment: Qt.AlignHCenter
                name: "image"
                tint: "#99FFFFFF"
                size: 36
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: I18n.t("discover.gallery.loadFailed")
                color: "#B3FFFFFF"
                font.pixelSize: Typography.small
                font.family: Theme.fontFamily
            }
        }
    }

    // ---- pasek górny: licznik + zamknięcie ------------------------------ #
    Item {
        id: topBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 56
        opacity: viewer.opened ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 140 } }

        Rectangle {
            visible: viewer.multiple
            anchors.centerIn: parent
            height: 26
            width: counterText.implicitWidth + 24
            radius: 13
            color: "#66000000"
            border.width: 1
            border.color: "#26FFFFFF"

            Text {
                id: counterText
                anchors.centerIn: parent
                text: I18n.format("discover.gallery.counter", {
                    current: viewer.currentIndex + 1,
                    total: viewer.count
                })
                color: "#E6FFFFFF"
                font.pixelSize: Typography.small
                font.weight: Font.Medium
                font.family: Theme.fontFamily
            }
        }

        IconButton {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            icon: "x"
            tint: "#E6FFFFFF"
            hoverTint: "#FFFFFF"
            tooltip: I18n.t("discover.gallery.close")
            onClicked: viewer.close()
        }
    }

    // ---- strzałki po bokach --------------------------------------------- #
    GalleryArrow {
        visible: viewer.multiple
        anchors.left: parent.left
        anchors.leftMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        direction: -1
        size: 48
        opacity: viewer.opened ? 1 : 0
        onClicked: viewer.prev()
    }

    GalleryArrow {
        visible: viewer.multiple
        anchors.right: parent.right
        anchors.rightMargin: 22
        anchors.verticalCenter: parent.verticalCenter
        direction: 1
        size: 48
        opacity: viewer.opened ? 1 : 0
        onClicked: viewer.next()
    }
}
