import QtQuick

// Film-edge scrubber: year and month marks sized by how many photos each holds.
// Hover shows where you would land. Drag to move. Up and down arrows work too.
Item {
    id: edge
    property var roll
    property var density: shell.timelineDensity
    property int curIndex: 0
    property real hoverY: -1
    readonly property bool dragging: seek.pressed
    readonly property bool hovered: seek.containsMouse || dragging
    readonly property real innerTop: 12
    readonly property real innerH: Math.max(1, height - 24)
    readonly property int total: roll ? roll.count : 0
    readonly property var segs: layoutSegments(density, innerH, total, roll ? roll.matchMode : false)
    readonly property real fraction: total > 1 ? curIndex / (total - 1) : 0

    width: Theme.edge
    z: 5
    Accessible.role: Accessible.Slider
    Accessible.name: "Time scrubber. Up and down arrows move through your photos."
    Accessible.description: labelAt(curIndex)
    activeFocusOnTab: true
    Keys.onUpPressed: roll.jumpToFraction(Math.max(0, fraction - 0.05))
    Keys.onDownPressed: roll.jumpToFraction(Math.min(1, fraction + 0.05))
    Keys.onPressed: function (event) {
        if (event.key === Qt.Key_Home) { roll.jumpToFraction(0); event.accepted = true }
        else if (event.key === Qt.Key_End) { roll.jumpToFraction(1); event.accepted = true }
    }

    readonly property var monthNames: ["January", "February", "March", "April", "May", "June", "July",
                                       "August", "September", "October", "November", "December"]

    // One block per year, tall enough to read, proportional to how many photos it holds.
    function layoutSegments(d, h, count, matching) {
        var out = []
        if (matching || !d || d.length === 0 || count <= 0)
            return out
        var sum = 0
        for (var i = 0; i < d.length; i++)
            sum += d[i].count || 0
        if (sum !== count)
            return out
        var raw = [], rawSum = 0
        for (var j = 0; j < d.length; j++) {
            var r = Math.max(46, h * (d[j].count || 0) / sum)
            raw.push(r)
            rawSum += r
        }
        var y = innerTop, start = 0
        for (var k = 0; k < d.length; k++) {
            var seg = { label: String(d[k].label), count: d[k].count || 0, start: start, y: y, h: raw[k] * h / rawSum, months: [] }
            var my = seg.y, ms = start
            var months = d[k].months || []
            for (var m = 0; m < months.length; m++) {
                var mh = seg.count > 0 ? seg.h * (months[m].count || 0) / seg.count : 0
                seg.months.push({ label: String(months[m].label), count: months[m].count || 0, start: ms, y: my, h: mh })
                my += mh
                ms += months[m].count || 0
            }
            out.push(seg)
            y += seg.h
            start += seg.count
        }
        return out
    }
    function indexToY(i) {
        if (segs.length === 0)
            return innerTop + (total > 1 ? i / (total - 1) : 0) * innerH
        for (var s = 0; s < segs.length; s++) {
            var g = segs[s]
            if (i < g.start + g.count || s === segs.length - 1)
                return g.y + Math.min(1, (i - g.start) / Math.max(1, g.count)) * g.h
        }
        return innerTop
    }
    function yToIndex(y) {
        var cy = Math.max(innerTop, Math.min(innerTop + innerH, y))
        if (segs.length === 0)
            return Math.round((cy - innerTop) / innerH * Math.max(0, total - 1))
        for (var s = 0; s < segs.length; s++) {
            var g = segs[s]
            if (cy <= g.y + g.h || s === segs.length - 1)
                return Math.max(0, Math.min(total - 1, g.start + Math.floor((cy - g.y) / Math.max(1, g.h) * g.count)))
        }
        return 0
    }
    function labelAt(i) {
        for (var s = 0; s < segs.length; s++) {
            var g = segs[s]
            if (i < g.start + g.count) {
                for (var m = 0; m < g.months.length; m++) {
                    var mo = g.months[m]
                    if (i < mo.start + mo.count) {
                        var n = parseInt(mo.label.substring(5, 7))
                        return n >= 1 && n <= 12 ? monthNames[n - 1] + " " + g.label : g.label
                    }
                }
                return g.label
            }
        }
        return total > 0 ? "Photo " + (i + 1) + " of " + total : ""
    }
    function isCurrentYear(g) { return curIndex >= g.start && curIndex < g.start + g.count }

    Connections {
        target: edge.roll ? edge.roll.view : null
        function onContentYChanged() { edge.curIndex = edge.roll.topIndex() }
        function onCountChanged() { edge.curIndex = edge.roll.topIndex() }
    }

    Rectangle {
        anchors.fill: parent
        color: edge.hovered ? Theme.line : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle { width: 1; height: parent.height; color: Theme.muted }
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

    Repeater {
        model: edge.segs
        delegate: Item {
            id: yearBlock
            readonly property bool here: edge.isCurrentYear(modelData)
            x: 0
            y: modelData.y
            width: edge.width
            height: modelData.h
            Rectangle { x: 4; width: parent.width - 8; height: 1; color: here ? Theme.amber : Theme.muted }
            Text {
                x: 7; y: 3
                visible: yearBlock.height >= 18
                text: modelData.label
                font.family: Theme.ui
                font.pixelSize: Theme.small
                font.weight: Font.Bold
                color: yearBlock.here ? Theme.amber : Theme.text
            }
            Repeater {
                model: modelData.months
                delegate: Item {
                    readonly property bool current: edge.curIndex >= modelData.start && edge.curIndex < modelData.start + modelData.count
                    x: 0
                    y: modelData.y - yearBlock.y
                    width: edge.width
                    height: modelData.h
                    Rectangle {
                        visible: index > 0
                        x: parent.width - 12; width: 8; height: 1
                        color: current ? Theme.amber : Theme.faint
                    }
                    Text {
                        visible: parent.height >= 15
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        y: index === 0 ? 17 : 1
                        text: edge.monthNames[Math.max(0, parseInt(modelData.label.substring(5, 7)) - 1)].substring(0, 3)
                        font.family: Theme.ui
                        font.pixelSize: 10
                        font.weight: current ? Font.Bold : Font.Medium
                        color: current ? Theme.amber : Theme.muted
                    }
                }
            }
        }
    }

    // Where you are now.
    Rectangle {
        id: knob
        visible: edge.total > 0
        x: 2
        width: parent.width - 4
        height: edge.dragging ? 6 : 4
        radius: 3
        color: Theme.amber
        y: edge.indexToY(edge.curIndex) - height / 2
        Behavior on y { enabled: !edge.dragging; NumberAnimation { duration: Theme.fast } }
        Behavior on height { NumberAnimation { duration: Theme.fast } }
    }

    // Hover or drag: say where you would land.
    Rectangle {
        id: bubble
        visible: edge.hovered && edge.hoverY >= 0 && edge.total > 0
        readonly property int idx: edge.yToIndex(edge.hoverY)
        x: -width - 8
        y: Math.max(4, Math.min(edge.height - height - 4, edge.hoverY - height / 2))
        width: bubbleText.implicitWidth + 20
        height: bubbleText.implicitHeight + 12
        radius: Theme.radius
        color: Theme.amber
        Text {
            id: bubbleText
            anchors.centerIn: parent
            text: edge.labelAt(bubble.idx)
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
        function go(my) {
            edge.hoverY = my
            edge.roll.jumpToIndex(edge.yToIndex(my))
        }
        onPressed: function (m) { edge.forceActiveFocus(); go(m.y) }
        onPositionChanged: function (m) { edge.hoverY = m.y; if (pressed) go(m.y) }
        onExited: edge.hoverY = -1
    }
}
