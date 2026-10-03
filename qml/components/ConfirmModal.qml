import QtQuick
import QtQuick.Layouts
import "../theme"
import "../i18n"

// Standard confirmation dialog (danger-aware).
Modal {
    id: root

    signal confirmed()
    signal rejected()

    property string message: ""
    property string confirmLabel: I18n.t("common.confirm.confirm")
    property string cancelLabel: I18n.t("common.confirm.cancel")
    property bool danger: false
    property bool confirmDisabled: false

    iconName: danger ? "alert-triangle" : "info"
    iconTint: danger ? Theme.danger : Theme.accent

    // jednorazowa blokada: podwojne klikniecie w Potwierdz nie moze
    // wywolac akcji dwa razy ani 'przeltec' w elementy strony pod modalem
    property bool _fired: false

    function ask(titleText, messageText, confirmText, isDanger) {
        root.message = messageText
        root.confirmLabel = confirmText || I18n.t("common.confirm.confirm")
        root.danger = isDanger === true
        root._fired = false
        root.title = titleText
        open()
    }

    Text {
        text: root.message
        color: Theme.textSecondary
        font.pixelSize: Typography.body + 0.5
        font.family: Theme.fontFamily
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        lineHeight: 1.35
    }

    // opcjonalny checkbox (np. "usun też pliki danych") - domyślnie ukryty
    property bool optionChecked: false
    property string optionLabel: ""

    RowLayout {
        visible: root.optionLabel !== ""
        spacing: 10
        Layout.fillWidth: true

        Rectangle {
            Layout.alignment: Qt.AlignTop
            width: 30
            height: 30
            radius: 9
            color: root.optionChecked ? Theme.rgba(Theme.danger, 0.25) : Theme.bg2
            border.width: 1
            border.color: root.optionChecked ? Theme.rgba(Theme.danger, 0.6) : Theme.border

            Icon {
                anchors.centerIn: parent
                name: "check"
                size: 14
                tint: Theme.danger
                visible: root.optionChecked
            }

            TapHandler { onTapped: root.optionChecked = !root.optionChecked }
        }

        Text {
            Layout.fillWidth: true
            text: root.optionLabel
            color: Theme.text
            font.pixelSize: Typography.small
            font.family: Theme.fontFamily
            wrapMode: Text.WordWrap
        }
    }

    footer: [
        PrimaryButton {
            text: root.confirmLabel
            danger: root.danger
            icon: root.danger ? "trash" : "check"
            disabled: root.confirmDisabled
            onClicked: { if (root._fired || root.confirmDisabled) return; root._fired = true; root.close(); root.confirmed() }
        },
        SecondaryButton {
            text: root.cancelLabel
            onClicked: { root.close(); root.rejected() }
        }
    ]
}
