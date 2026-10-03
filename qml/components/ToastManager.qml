import QtQuick
import "../theme"

// Toast stack pinned to the bottom-right corner of the window.
//     ToastManager { id: toasts }   /   toasts.show("Saved", "success")
//
// NOTE: required properties in the delegate replace the legacy `model`
// context property - roles are matched by name, so the ListModel stores
// them under distinct keys (msg/lvl/dtl) to avoid clashing with the
// public properties of Toast itself.
Column {
    id: manager

    spacing: 10

    property int maxVisible: 4

    function show(message, level, detail) {
        toastModel.append({
            msg: String(message),
            lvl: String(level || "info"),
            dtl: String(detail || "")
        })
        while (toastModel.count > maxVisible) {
            toastModel.remove(0)
        }
    }

    ListModel { id: toastModel }

    Repeater {
        model: toastModel

        Toast {
            id: toastDelegate

            required property string msg
            required property string lvl
            required property string dtl
            required property int index

            message: toastDelegate.msg
            level: toastDelegate.lvl
            detail: toastDelegate.dtl

            onDismissed: toastModel.remove(toastDelegate.index)
        }
    }

    // ---- transitions ---------------------------------------------------- #
    add: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.normal; easing.type: Easing.OutCubic }
            NumberAnimation { property: "x"; from: 60; to: 0; duration: Theme.normal; easing.type: Easing.OutCubic }
        }
    }

    move: Transition {
        NumberAnimation { property: "y"; duration: Theme.normal; easing.type: Easing.OutCubic }
    }
}
