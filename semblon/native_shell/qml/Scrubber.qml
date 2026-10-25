import QtQuick

// Film-edge scrubber: one even slot per month under its year. Photo density shows as a short
// bar, never as distance. The marker lives on the left rail, away from every label.
// Click or drag to land on a month's header. Up, Down, Home and End step through months.
Item {
    id: edge
    property var roll
    property real hoverY: -1
    readonly property bool dragging: seek.pressed
    readonly property bool hovered: seek.containsMouse || dragging
    readonly property real innerTop: 14
    readonly property real innerH: Math.max(1, height - 28)
    readonly property int total: roll ? roll.count : 0
    readonly property var months: roll ? roll.monthList : []
    readonly property string currentKey: roll ? roll.currentMonth : ""
    readonly property real fraction: total > 1 ? linearIndex / (total - 1) : 0
    property int linearIndex: 0
    readonly property var slots: buildSlots(months, innerH)
    readonly property real unit: slots.unit
    readonly property real railW: 5

    width: Theme.edge
    z: 5
    Accessible.role: Accessible.Slider
    Accessible.name: "Time scrubber. Up and down arrows move month by month."
    Accessible.description: roll && roll.heading !== "" ? roll.heading : ""
    activeFocusOnTab: true
    Keys.onPressed: function (event) {
        if (event.key === Qt.Key_Up) { step(-1); event.accepted = true }
        else if (event.key === Qt.Key_Down) { step(1); event.accepted = true }
        else if (event.key === Qt.Key_Home) { stepTo(0); event.accepted = true }
        else if (event.key === Qt.Key_End) { stepTo(months.length - 1); event.accepted = true }
    }

    readonly property var shortMonths: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    function buildSlots(list, h) {
        var out = { items: [], unit: 0, labelEvery: 1 }
        if (!list || list.length === 0)
            return out
        var years = 0, last = "#"
        for (var i = 0; i < list.length; i++) {
            var y = list[i].key === "" ? "" : list[i].key.substring(0, 4)
            if (y !== last) { years++; last = y }
        }
        var weight = list.length + years * 1.15
        var u = Math.min(24, h / weight)
        var maxCount = 1
        for (var c = 0; c < list.length; c++)
            maxCount = Math.max(maxCount, list[c].count)
        var at = innerTop, prevYear = "#"
        for (var k = 0; k < list.length; k++) {
            var m = list[k]
            var yr = m.key === "" ? "" : m.key.substring(0, 4)
            if (yr !== prevYear) {
                out.items.push({ kind: "year", label: m.key === "" ? "Undated" : yr, y: at, h: u * 1.15, key: m.key, index: k })
                at += u * 1.15
                prevYear = yr
            }
            var mon = m.key === "" ? "" : edge.shortMonths[parseInt(m.key.substring(5, 7)) - 1]
            out.items.push({ kind: "month", label: mon, y: at, h: u, key: m.key, index: k, count: m.count, share: m.count / maxCount, title: m.title })
            at += u
        }
        out.unit = u
        out.labelEvery = u >= 13 ? 1 : (u >= 8 ? 3 : 0)
        return out
    }
    function slotAt(y) {
        var items = slots.items
        for (var i = 0; i < items.length; i++)
            if (y < items[i].y + items[i].h)
                return items[i]
        return items.length > 0 ? items[items.length - 1] : null
    }
    function monthIndexOf(key) {
        for (var i = 0; i < months.length; i++)
            if (months[i].key === key)
                return i
        return 0
    }
    function stepTo(i) {
        if (months.length === 0) {
            if (roll) roll.jumpToFraction(i <= 0 ? 0 : 1)
            return
        }
        roll.jumpToMonth(months[Math.max(0, Math.min(months.length - 1, i))].key)
    }
    function step(d) {
        if (months.length === 0) {
            if (roll) roll.jumpToFraction(Math.max(0, Math.min(1, fraction + d * 0.05)))
            return
        }
        stepTo(monthIndexOf(currentKey) + d)
    }
    function slotFor(key) {
        var items = slots.items
        for (var i = 0; i < items.length; i++)
            if (items[i].kind === "month" && items[i].key === key)
                return items[i]
        return null
    }
    function go(my) {
        hoverY = my
        if (slots.items.length === 0) {
            roll.jumpToFraction(Math.max(0, Math.min(1, (my - innerTop) / innerH)))
            return
        }
        var s = slotAt(my)
        if (s)
            roll.jumpToMonth(s.key)
    }

    Connections {
        target: edge.roll ? edge.roll.view : null
        function onContentYChanged() { edge.linearIndex = edge.roll.topIndex() }
    }

    Rectangle {
        anchors.fill: parent
        color: edge.hovered ? Theme.line : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle { width: 1; height: parent.height; color: Theme.muted }
        Rectangle { x: 1; width: edge.railW; height: parent.height; color: Theme.bg; opacity: 0.45 }
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

    // Slots: year headers and months.
    Repeater {
        model: edge.slots.items
        delegate: Item {
            id: slot
            readonly property bool isYear: modelData.kind === "year"
            readonly property bool here: !isYear && modelData.key === edge.currentKey
            readonly property bool hoverHere: edge.hovered && edge.hoverY >= modelData.y && edge.hoverY < modelData.y + modelData.h
            y: modelData.y
            width: edge.width
            height: modelData.h

            Rectangle {
                visible: slot.isYear
                x: edge.railW + 3; width: parent.width - edge.railW - 6; height: 1; color: Theme.muted
            }
            Text {
                visible: slot.isYear && slot.height >= 12
                x: edge.railW + 5
                y: 2
                text: modelData.label
                font.family: Theme.ui
                font.pixelSize: 12
                font.weight: Font.Bold
                color: Theme.text
            }
            // Density: a short bar, longer for busier months.
            Rectangle {
                visible: !slot.isYear
                anchors.right: parent.right
                anchors.rightMargin: 5
                anchors.verticalCenter: parent.verticalCenter
                width: 3 + 15 * (modelData.share || 0)
                height: Math.max(1, Math.min(3, slot.height - 2))
                color: slot.here || slot.hoverHere ? Theme.amber : Theme.faint
            }
            Rectangle {
                visible: slot.here && edge.slots.labelEvery > 0
                x: edge.railW + 3
                anchors.verticalCenter: parent.verticalCenter
                width: monthLabel.implicitWidth + 8
                height: Math.min(slot.height, monthLabel.implicitHeight + 2)
                radius: 2
                color: Theme.amberSoft
            }
            Text {
                id: monthLabel
                visible: !slot.isYear && edge.slots.labelEvery > 0
                         && (slot.here || modelData.index % edge.slots.labelEvery === 0)
                x: edge.railW + 7
                anchors.verticalCenter: parent.verticalCenter
                text: modelData.label
                font.family: Theme.ui
                font.pixelSize: 10
                font.weight: slot.here ? Font.Bold : Font.Medium
                color: slot.here ? Theme.amber : Theme.muted
            }
        }
    }

    // Where you are now: a marker on the left rail, so it never crosses a label.
    Rectangle {
        id: marker
        objectName: "scrubMarker"
        readonly property var cur: edge.slotFor(edge.currentKey)
        visible: edge.total > 0 && (edge.slots.items.length === 0 || cur !== null)
        x: 1
        width: edge.railW
        radius: 2
        color: Theme.amber
        height: cur ? Math.max(4, cur.h) : (edge.dragging ? 8 : 6)
        y: cur ? cur.y : edge.innerTop + edge.fraction * (edge.innerH - height)
        Behavior on y { enabled: !edge.dragging; NumberAnimation { duration: Theme.fast } }
    }

    // Hover or drag: say where you would land, on its own backplate to the left.
    Rectangle {
        id: bubble
        visible: edge.hovered && edge.hoverY >= 0 && edge.total > 0 && bubbleText.text !== ""
        readonly property var s: edge.slotAt(edge.hoverY)
        x: -width - 8
        y: Math.max(4, Math.min(edge.height - height - 4, edge.hoverY - height / 2))
        width: bubbleText.implicitWidth + 20
        height: bubbleText.implicitHeight + 12
        radius: Theme.radius
        color: Theme.amber
        Text {
            id: bubbleText
            anchors.centerIn: parent
            text: bubble.s ? (bubble.s.kind === "month" ? bubble.s.title : bubble.s.label) : ""
            font.family: Theme.ui
            font.pixelSize: Theme.small
            font.weight: Font.DemiBold
            color: Theme.onAmber
        }
    }

    MouseArea {
        id: seek
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onPressed: function (m) { edge.forceActiveFocus(); edge.go(m.y) }
        onPositionChanged: function (m) { edge.hoverY = m.y; if (pressed) edge.go(m.y) }
        onExited: edge.hoverY = -1
    }
}
