import QtQuick

// One button for the whole app: keyboard focus ring, hover, press, accessible name.
Item {
    id: tool
    property string label: ""
    property string hint: ""
    property bool primary: false
    property bool quiet: false
    property bool selected: false
    property int pixel: Theme.small
    property string family: Theme.ui
    signal activated()

    implicitWidth: caption.implicitWidth + Theme.pad * 1.6
    implicitHeight: 36
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.4

    Accessible.role: Accessible.Button
    Accessible.name: label
    Accessible.description: hint
    Accessible.onPressAction: tool.activated()

    Keys.onReturnPressed: tool.activated()
    Keys.onEnterPressed: tool.activated()
    Keys.onSpacePressed: tool.activated()

    Rectangle {
        id: face
        anchors.fill: parent
        radius: Theme.pill
        color: tool.primary ? Theme.amber
             : tool.selected ? Theme.amberSoft
             : area.containsMouse ? Theme.raised
             : tool.quiet ? "transparent" : Theme.surface
        border.width: tool.primary || tool.quiet ? 0 : 1
        border.color: tool.selected ? Theme.amber : Theme.line
        scale: area.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: Theme.fast } }
        Behavior on color { ColorAnimation { duration: Theme.fast } }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -3
        radius: Theme.pill
        color: "transparent"
        border.width: 2
        border.color: Theme.amber
        visible: tool.activeFocus
    }
    Text {
        id: caption
        anchors.centerIn: parent
        text: tool.label
        font.family: tool.family
        font.pixelSize: tool.pixel
        font.weight: tool.primary ? Font.DemiBold : Font.Medium
        color: tool.primary ? Theme.onAmber : tool.selected ? Theme.amber : Theme.text
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tool.activated()
    }
}
