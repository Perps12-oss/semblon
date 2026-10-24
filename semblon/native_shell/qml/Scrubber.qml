import QtQuick

// Film-edge scrubber: year and month ticks sized by how many photos each holds.
Item {
    id: edge
    property var roll
    property var density: shell.timelineDensity
    readonly property int total: Math.max(1, archiveModel.count)
    property real fraction: roll && roll.count > 1 ? roll.view.contentY / Math.max(1, roll.view.contentHeight - roll.view.height) : 0

    width: Theme.edge
    Accessible.role: Accessible.Slider
    Accessible.name: "Time scrubber. Up and down arrows move through your photos."
    activeFocusOnTab: true
    Keys.onUpPressed: roll.jumpToFraction(Math.max(0, fraction - 0.05))
    Keys.onDownPressed: roll.jumpToFraction(Math.min(1, fraction + 0.05))

    Rectangle {
        anchors.fill: parent
        color: Theme.surface
        Rectangle { width: 1; height: parent.height; color: Theme.line }
        Grain { anchors.fill: parent }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        color: "transparent"
        border.width: 2
        border.color: Theme.amber
        visible: edge.activeFocus
    }

    Column {
        id: ticks
        anchors.fill: parent
        anchors.topMargin: 10
        anchors.bottomMargin: 10
        Repeater {
            model: edge.density
            delegate: Item {
                width: ticks.width
                height: Math.max(26, ticks.height * modelData.count / edge.total)
                Rectangle { x: 6; y: 0; width: 14; height: 2; color: Theme.amber }
                Text {
                    x: 6; y: 4
                    text: modelData.label
                    font.family: Theme.ui
                    font.pixelSize: Theme.tiny
                    font.weight: Font.DemiBold
                    color: Theme.muted
                }
            }
        }
    }

    Rectangle {
        id: knob
        x: 3
        width: parent.width - 6
        height: 6
        radius: 3
        color: Theme.amber
        y: 10 + edge.fraction * (parent.height - 26)
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        function seek(my) { edge.roll.jumpToFraction(Math.max(0, Math.min(1, (my - 10) / (edge.height - 20)))) }
        onPressed: function (m) { edge.forceActiveFocus(); seek(m.y) }
        onPositionChanged: function (m) { if (pressed) seek(m.y) }
    }
}
