import QtQuick
import QtQuick.Controls.Basic
import "../../qml/components"

ApplicationWindow {
    id: win
    visible: true
    width: 800; height: 600
    // kontener przesuwa sie PO utworzeniu przycisku (jak strona po animacji / layout)
    Item {
        id: shifter
        x: 0; y: 0
        IconButton { id: btn; icon: "pencil"; tooltip: "Edytuj instancje" }
    }
    Component.onCompleted: { shifter.x = 500; shifter.y = 300 }

    function tipInfo() {
        let tip = null
        const kids = Overlay.overlay.children
        for (let i = 0; i < kids.length; ++i)
            if (kids[i].objectName === "iconButtonTip") tip = kids[i]
        const b = btn.mapToItem(null, 0, 0)
        return tip ? {tx: tip.x, ty: tip.y, tw: tip.width, th: tip.height, op: tip.opacity,
                      bx: b.x, by: b.y, bw: btn.width, bh: btn.height} : null
    }
}
