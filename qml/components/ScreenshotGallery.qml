import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Zrzuty ekranu moda w drawerze: jedno zdjęcie z przyciskami strzałek po
// lewej i prawej stronie. Klik w zdjęcie emituje fullscreenRequested(index),
// a drawer otwiera wtedy ImageViewer na całe okno launchera.
Rectangle {
    id: gallery

    property var images: []
    property int currentIndex: 0

    readonly property int count: images ? images.length : 0
    readonly property bool multiple: count > 1

    signal fullscreenRequested(int index)

    function next() {
        if (multiple)
            currentIndex = (currentIndex + 1) % count
    }

    function prev() {
        if (multiple)
            currentIndex = (currentIndex - 1 + count) % count
    }

    // nowa lista zdjęć (inny mod / dociągnięte szczegóły) = zaczynamy od pierwszego
    onImagesChanged: currentIndex = 0

    visible: count > 0
    radius: 10
    color: Theme.bg0
    border.width: 1
    border.color: Theme.border
    clip: true

    Image {
        id: shot
        anchors.fill: parent
        anchors.margins: 1
        source: gallery.count > 0 ? String(gallery.images[gallery.currentIndex] || "") : ""
        asynchronous: true
        cache: true
        fillMode: Image.PreserveAspectFit
        // do podglądu w drawerze wystarcza zmniejszona wersja
        sourceSize.width: 1280
        smooth: true
        mipmap: true
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 140 } }
    }

    // ładowanie / błąd
    BusyIndicator {
        anchors.centerIn: parent
        running: shot.status === Image.Loading
        visible: running
    }
    ColumnLayout {
        anchors.centerIn: parent
        spacing: 6
        visible: shot.status === Image.Error
        Icon {
            Layout.alignment: Qt.AlignHCenter
            name: "image"
            tint: Theme.textMuted
            size: 28
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: I18n.t("discover.gallery.loadFailed")
            color: Theme.textMuted
            font.pixelSize: Typography.small
            font.family: Theme.fontFamily
        }
    }

    // klik w zdjęcie = pełny ekran
    MouseArea {
        id: openArea
        anchors.fill: parent
        enabled: shot.status === Image.Ready
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: gallery.fullscreenRequested(gallery.currentIndex)
    }

    // podpowiedź "powiększ" - widoczna po najechaniu na zdjęcie
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        width: 30
        height: 30
        radius: 8
        color: "#80000000"
        border.width: 1
        border.color: "#26FFFFFF"
        opacity: openArea.containsMouse && shot.status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
        Icon {
            anchors.centerIn: parent
            name: "maximize"
            tint: "#E6FFFFFF"
            size: 15
        }
    }

    // licznik "2 / 5"
    Rectangle {
        visible: gallery.multiple
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottomMargin: 10
        height: 22
        width: counter.implicitWidth + 20
        radius: 11
        color: "#80000000"
        border.width: 1
        border.color: "#26FFFFFF"
        Text {
            id: counter
            anchors.centerIn: parent
            text: I18n.format("discover.gallery.counter", {
                current: gallery.currentIndex + 1,
                total: gallery.count
            })
            color: "#E6FFFFFF"
            font.pixelSize: Typography.caption
            font.weight: Font.Medium
            font.family: Theme.fontFamily
        }
    }

    // strzałki po lewej i prawej
    GalleryArrow {
        visible: gallery.multiple
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        direction: -1
        size: 36
        onClicked: gallery.prev()
    }
    GalleryArrow {
        visible: gallery.multiple
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        direction: 1
        size: 36
        onClicked: gallery.next()
    }
}
