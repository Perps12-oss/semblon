import QtQuick

// Ctrl+K: every action in plain words, filtered as you type.
Item {
    id: palette
    property bool open: false
    property var actions: []
    signal chosen(string id)
    visible: open
    onOpenChanged: if (open) { filter.text = ""; filter.forceActiveFocus() }

    readonly property var shown: {
        var q = filter.text.trim().toLowerCase()
        return actions.filter(function (a) { return q === "" || a.label.toLowerCase().indexOf(q) >= 0 })
    }

    Rectangle { anchors.fill: parent; color: Theme.scrim; MouseArea { anchors.fill: parent; onClicked: palette.open = false } }
    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        y: parent.height * 0.18
        width: Math.min(parent.width - 40, 520)
        height: list.contentHeight + 76
        radius: Theme.radius * 1.6
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        Accessible.role: Accessible.Dialog
        Accessible.name: "Everything you can do"
        TextInput {
            id: filter
            x: 18; y: 14; width: parent.width - 36; height: 36
            verticalAlignment: TextInput.AlignVCenter
            font.family: Theme.ui
            font.pixelSize: Theme.lead
            color: Theme.text
            Accessible.name: "Type to filter actions"
            Keys.onEscapePressed: palette.open = false
            Keys.onDownPressed: list.incrementCurrentIndex()
            Keys.onUpPressed: list.decrementCurrentIndex()
            onAccepted: if (palette.shown.length > 0) { palette.chosen(palette.shown[list.currentIndex].id); palette.open = false }
            onTextChanged: list.currentIndex = 0
            Text { visible: filter.text === ""; text: "What would you like to do?"; font: filter.font; color: Theme.faint }
        }
        ListView {
            id: list
            x: 8; y: 62; width: parent.width - 16
            height: Math.min(contentHeight, 360)
            model: palette.shown
            clip: true
            delegate: Rectangle {
                width: list.width; height: 38; radius: Theme.radius
                color: ListView.isCurrentItem ? Theme.amberSoft : "transparent"
                Text {
                    x: 12; anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    font.family: Theme.ui; font.pixelSize: Theme.body; color: Theme.text
                }
                MouseArea { anchors.fill: parent; onClicked: { palette.chosen(modelData.id); palette.open = false } }
                Accessible.role: Accessible.Button
                Accessible.name: modelData.label
            }
        }
    }
}
