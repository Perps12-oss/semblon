import QtQuick

// A floating panel with a close affordance, grain, and Escape to dismiss.
Rectangle {
    id: sheet
    property string heading: ""
    property bool open: false
    default property alias content: body.data
    signal dismissed()

    visible: opacity > 0.01
    opacity: open ? 1 : 0
    color: Theme.surface
    radius: Theme.radius * 1.6
    border.width: 1
    border.color: Theme.line
    clip: true
    scale: open ? 1 : 0.97
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    Behavior on scale { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }

    Accessible.role: Accessible.Pane
    Accessible.name: heading

    Grain { anchors.fill: parent }

    Text {
        id: title
        x: Theme.pad * 1.5
        y: Theme.pad
        text: sheet.heading
        font.family: Theme.display
        font.pixelSize: Theme.title
        font.weight: Font.Medium
        color: Theme.text
    }
    Tool {
        id: closer
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.pad
        label: "Close"
        quiet: true
        onActivated: sheet.dismissed()
    }
    Item {
        id: body
        anchors.fill: parent
        anchors.topMargin: title.y + title.implicitHeight + Theme.pad
        anchors.margins: Theme.pad * 1.5
    }
    Keys.onEscapePressed: sheet.dismissed()
}
