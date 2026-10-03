import QtQuick
import QtQuick.Controls.Basic
import "../theme"

// Przewijana powierzchnia na Flickable (ScrollView nie eksponuje contentY
// do animacji - NumberAnimation na jego aliasie pada z "Cannot animate
// non-existent property"): ZAWSZE widoczny scrollbar + przyzwoity scroll
// myszki (animowany krok ~96 px/klik), touchpad 1:1 piksele.
// Użycie: ustaw contentWidth/contentHeight z zawartości, np.
//     contentHeight: kolumna.implicitHeight
Flickable {
    id: sv

    property bool showScrollBar: true   // false = ukryj pasek (np. tryb QR)
    // Match Odkrywaj exactly: the scrollbar overlays the viewport edge and
    // content itself stops 14 px before it. There is no painted gutter.
    readonly property real contentRightInset: showScrollBar ? 14 : 0
    contentWidth: Math.max(0, width - contentRightInset)

    clip: true
    boundsBehavior: Flickable.StopAtBounds
    flickDeceleration: 5200
    maximumFlickVelocity: 1800

    ScrollBar.vertical: AppScrollBar {
        z: 5
        policy: sv.showScrollBar ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff
        x: sv.width - width
        height: sv.height
    }

    // skok contentHeight (np. przeładowanie listy) nie może zostawić
    // contentY poza zakresem - inaczej widok otwiera się "gdzieś na dole"
    onContentHeightChanged:
        contentY = Math.max(0, Math.min(contentY, Math.max(0, contentHeight - height)))

    WheelHandler {
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onWheel: (event) => {
            const maxY = Math.max(0, sv.contentHeight - sv.height)
            if (maxY <= 0) { event.accepted = false; return }
            sv.cancelFlick()
            const step = Theme.wheelDelta(event.pixelDelta.y, event.angleDelta.y)
            sv.contentY = Math.max(0, Math.min(maxY, sv.contentY - step))
            event.accepted = true
        }
    }
}
