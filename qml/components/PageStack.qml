import QtQuick
import "../theme"

// Animated page container - keeps all pages alive (state preserved),
// cross-fades on switch and reports the current page name.
Item {
    id: root

    property int currentIndex: 0

    readonly property string currentPage: {
        if (currentIndex >= 0 && currentIndex < children.length && children[currentIndex])
            return children[currentIndex].pageName || ""
        return ""
    }

    function go(name) {
        for (let i = 0; i < children.length; i++) {
            const child = children[i]
            if (child && child.pageName === name) {
                if (i !== currentIndex) {
                    currentIndex = i
                    _apply()
                }
                return true
            }
        }
        return false
    }

    function _apply() {
        for (let i = 0; i < children.length; i++) {
            const child = children[i]
            if (child && child.pageName !== undefined) {
                child.active = (i === currentIndex)
            }
        }
        pageChanged()
    }

    signal pageChanged()

    onChildrenChanged: Qt.callLater(_apply)

    Component.onCompleted: {
        if (currentIndex < 0 || currentIndex >= children.length) currentIndex = 0
        _apply()
    }
}
