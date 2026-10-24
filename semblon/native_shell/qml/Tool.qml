import QtQuick

// One button for the whole app: keyboard focus ring, hover, press, accessible name.
Item {
    id: tool
    property string label: ""
    property string hint: ""
    property bool primary: false
    property bool quiet: false
    property bool selected: false
    property bool dimmed: false           // looks off, stays focusable, says why
    property string whyDimmed: "Add photos first"
    property int pixel: Theme.small
    property string family: Theme.ui
    signal activated()

    implicitWidth: caption.implicitWidth + Theme.pad * 1.6
    implicitHeight: 36
    activeFocusOnTab: true
    opacity: enabled ? 1 : 0.4
    z: tip.visible ? 20 : 0
    function fire() { if (!tool.dimmed) tool.activated() }

    Accessible.role: Accessible.Button
    Accessible.name: label
    Accessible.description: dimmed ? whyDimmed : hint
    Accessible.onPressAction: tool.fire()

    Keys.onReturnPressed: tool.fire()
    Keys.onEnterPressed: tool.fire()
    Keys.onSpacePressed: tool.fire()

    Rectangle {
        id: face
        anchors.fill: parent
        opacity: tool.dimmed ? 0.45 : 1
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
        opacity: tool.dimmed ? 0.55 : 1
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
        onClicked: tool.fire()
    }

    Rectangle {
        id: tip
        objectName: "whyTip"
        visible: tool.dimmed && (area.containsMouse || tool.activeFocus)
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.top
        anchors.bottomMargin: 8
        width: tipText.implicitWidth + 18
        height: tipText.implicitHeight + 10
        radius: Theme.radius
        color: Theme.raised
        border.width: 1
        border.color: Theme.amber
        Text { id: tipText; anchors.centerIn: parent; text: tool.whyDimmed; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.text }
    }
}
