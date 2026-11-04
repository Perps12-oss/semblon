import QtQuick

// Phase 3 precision temporal loupe — destination feedback during drag/settle.
// Jump indicator uses Phase 1 canonical chronology only (full-archive axis).
// Phase 2 density silhouette is decoration drawn on that axis, never a coordinate source.
Item {
    id: loupe
    objectName: "temporalLoupe"

    property var geometry: null          // frozen Phase 1 snapshot
    property var frozenSegment: null     // viewport segment at Armed
    property var yearRibbon: []          // Phase 2 cells (photoCount / sampleIds only)
    property int destinationYear: -1
    property bool destinationUndated: false
    property real pointerYearFrac: -1    // dated pointer position; -1 if undated/unknown
    property bool pointerOverEmpty: false
    property real pointerX: 0            // coords in this item's parent
    property real pointerY: 0
    property real windowW: 800
    property real windowH: 600
    property bool reducedMotion: Theme.reducedMotion

    readonly property bool undatedMode: destinationUndated
    readonly property int photoCount: {
        if (destinationUndated || destinationYear < 0)
            return 0
        for (var i = 0; i < yearRibbon.length; i++) {
            if (yearRibbon[i].year === destinationYear)
                return yearRibbon[i].photoCount || 0
        }
        if (geometry && geometry.years) {
            for (var j = 0; j < geometry.years.length; j++) {
                if (geometry.years[j].year === destinationYear)
                    return geometry.years[j].photoCount || 0
            }
        }
        return 0
    }
    readonly property var sampleIds: {
        if (destinationUndated || destinationYear < 0)
            return []
        for (var i = 0; i < yearRibbon.length; i++) {
            if (yearRibbon[i].year === destinationYear && yearRibbon[i].hasTiny)
                return (yearRibbon[i].sampleIds || []).slice(0, 4)
        }
        return []
    }
    readonly property string primaryText: {
        if (destinationUndated)
            return "Undated"
        if (destinationYear >= 0)
            return "Landing on " + destinationYear
        return ""
    }
    readonly property string secondaryText: {
        if (destinationUndated)
            return "Outside the calendar — release does not navigate"
        if (pointerOverEmpty && pointerYearFrac >= 0)
            return Math.floor(pointerYearFrac) + " is empty — no photographs"
        if (destinationYear >= 0 && photoCount > 0)
            return photoCount + (photoCount === 1 ? " photograph" : " photographs")
        return ""
    }
    readonly property string accessAnnounce: {
        if (destinationUndated)
            return "Undated. Release does not navigate."
        if (destinationYear < 0)
            return ""
        var fromY = frozenFromYear()
        if (fromY >= 0 && fromY !== destinationYear)
            return "Year " + destinationYear + ", jumping from " + fromY + "."
        return "Year " + destinationYear + "."
    }

    // Placement hysteresis state (owned by the loupe, not AppState).
    property bool flipV: false
    property bool flipH: false

    width: Theme.loupePanelW
    height: undatedMode
            ? (primaryCol.implicitHeight + 16)
            : (primaryCol.implicitHeight + Theme.loupeAxisH + (sampleIds.length ? Theme.loupeThumb + 12 : 0) + 20)
    z: 40
    // Visibility owned by Scrubber (tracking/settling + flag).
    Accessible.ignored: true
    // Not focusable — presentation only.
    activeFocusOnTab: false

    function frozenFromYear() {
        if (!frozenSegment || frozenSegment.timeHi === undefined)
            return -1
        return Math.floor(frozenSegment.timeHi)
    }

    function stripTForYearFrac(g, yearFrac) {
        if (!g || g.calendarFirst > g.calendarLast)
            return 0
        var top = g.calendarLast + 1
        var bottom = g.calendarFirst
        if (top === bottom)
            return 0
        var local = (top - yearFrac) / (top - bottom)
        return Math.max(0, Math.min(1, local))
    }

    function axisYForYearFrac(yearFrac) {
        return stripTForYearFrac(geometry, yearFrac) * Theme.loupeAxisH
    }

    function updatePlacement() {
        var ox = Theme.loupeOffsetX
        var oy = Theme.loupeOffsetY
        // Desired top-left in parent space (parent = scrubber).
        var wantX = pointerX + (flipH ? -width - ox : ox)
        var wantY = pointerY + (flipV ? 8 : oy)

        // Hysteresis: flip when within margin of window edge; unflip only after retreat.
        var global = mapToItem(null, 0, 0)
        // Use pointer in assumed window coords via parent chain — scrubber maps.
        var px = pointerX
        var py = pointerY
        // Approximate window edges from provided window size and scrubber-relative pointer.
        // Parent (scrubber) sits at the right; pointerX is local to scrubber.
        if (!flipH && (px + ox + width > Theme.edge + Theme.loupeEdgeMargin))
            flipH = true
        else if (flipH && px < Theme.edge - Theme.loupeUnflipDistance)
            flipH = false

        if (!flipV && py + oy < Theme.loupeEdgeMargin)
            flipV = true
        else if (flipV && py > Theme.loupeUnflipDistance)
            flipV = false

        wantX = pointerX + (flipH ? -width - ox : ox)
        wantY = pointerY + (flipV ? 8 : oy)

        // Clamp within scrubber's parent (the table stage) if sizes known.
        var maxX = Math.max(0, windowW - width - 4)
        var maxY = Math.max(0, windowH - height - 4)
        // Convert want to stage coords roughly: scrubber is at right.
        x = wantX
        y = Math.max(2, Math.min(Math.max(2, (parent ? parent.height : windowH) - height - 2), wantY))
    }

    onPointerXChanged: updatePlacement()
    onPointerYChanged: updatePlacement()
    onWidthChanged: updatePlacement()
    onHeightChanged: updatePlacement()
    onVisibleChanged: {
        if (visible) {
            flipV = false
            flipH = false
            updatePlacement()
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: Theme.radius
        color: Theme.raised
        border.width: 1
        border.color: Theme.line
        opacity: 0.97
    }

    Column {
        id: primaryCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 8
        spacing: 4

        Text {
            objectName: "loupePrimary"
            width: parent.width
            text: loupe.primaryText
            font.family: Theme.ui
            font.pixelSize: Theme.small
            font.weight: Font.DemiBold
            color: Theme.text
            wrapMode: Text.WordWrap
        }
        Text {
            objectName: "loupeSecondary"
            width: parent.width
            visible: text !== ""
            text: loupe.secondaryText
            font.family: Theme.ui
            font.pixelSize: Theme.tiny
            color: Theme.muted
            wrapMode: Text.WordWrap
        }
    }

    // Full-archive jump indicator — coordinates from Phase 1 geometry only.
    Item {
        id: axis
        objectName: "loupeJumpAxis"
        visible: !loupe.undatedMode && loupe.geometry && loupe.destinationYear >= 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: primaryCol.bottom
        anchors.topMargin: 8
        height: Theme.loupeAxisH

        readonly property real axisLeft: 10
        readonly property real axisMid: axisLeft + Theme.loupeAxisW / 2

        // Density silhouette — decoration from yearRibbon counts, positioned via canonical t.
        Repeater {
            model: {
                var g = loupe.geometry
                if (!g || g.calendarFirst > g.calendarLast)
                    return []
                var out = []
                var years = g.calendarLast - g.calendarFirst + 1
                var band = Theme.loupeAxisH / Math.max(1, years)
                for (var i = 0; i < years; i++) {
                    var year = g.calendarLast - i
                    var count = 0
                    var populated = false
                    for (var r = 0; r < loupe.yearRibbon.length; r++) {
                        if (loupe.yearRibbon[r].year === year) {
                            count = loupe.yearRibbon[r].photoCount || 0
                            populated = true
                            break
                        }
                    }
                    if (!populated && g.years) {
                        for (var y = 0; y < g.years.length; y++) {
                            if (g.years[y].year === year) {
                                populated = g.years[y].populated
                                count = g.years[y].photoCount || 0
                                break
                            }
                        }
                    }
                    out.push({
                        year: year,
                        y: i * band,
                        h: band,
                        populated: populated,
                        count: count
                    })
                }
                return out
            }
            delegate: Item {
                y: modelData.y
                height: Math.max(1, modelData.h)
                width: parent.width
                // Silhouette bar — width from density, y from calendar index (= canonical t).
                Rectangle {
                    x: axis.axisLeft
                    width: {
                        if (!modelData.populated)
                            return 2
                        var c = Math.max(0, modelData.count)
                        var t = Math.min(1, Math.log(1 + c) / Math.log(1 + 5000))
                        return 4 + t * (Theme.loupeAxisW - 4)
                    }
                    height: Math.max(1, parent.height - 1)
                    color: modelData.populated ? Theme.amberSoft : Theme.line
                    opacity: modelData.populated ? 0.85 : 0.35
                }
            }
        }

        // Empty-interval hatch between pointer year and resolved destination.
        Rectangle {
            id: emptyHatch
            objectName: "loupeEmptyHatch"
            visible: loupe.pointerOverEmpty && loupe.pointerYearFrac >= 0 && loupe.destinationYear >= 0
            x: axis.axisLeft
            width: Theme.loupeAxisW
            color: Theme.faint
            opacity: 0.35
            y: {
                var a = loupe.axisYForYearFrac(loupe.pointerYearFrac)
                var b = loupe.axisYForYearFrac(loupe.destinationYear + 0.5)
                return Math.min(a, b)
            }
            height: {
                var a = loupe.axisYForYearFrac(loupe.pointerYearFrac)
                var b = loupe.axisYForYearFrac(loupe.destinationYear + 0.5)
                return Math.max(2, Math.abs(a - b))
            }
            // Simple hatch via alternating opacity strips.
            Column {
                anchors.fill: parent
                spacing: 2
                Repeater {
                    model: Math.max(1, Math.floor(parent.parent.height / 4))
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: Theme.bg
                        opacity: 0.5
                    }
                }
            }
        }

        // Vertical axis rule.
        Rectangle {
            x: axis.axisMid
            width: 1
            height: parent.height
            color: Theme.line
        }

        // Frozen current-position mark (Armed viewport — does not chase contentY).
        Rectangle {
            id: originMark
            objectName: "loupeOriginMark"
            visible: loupe.frozenSegment && loupe.frozenSegment.timeHi !== undefined
            width: 10
            height: 4
            radius: 1
            color: Theme.muted
            x: axis.axisMid - width / 2
            y: {
                var s = loupe.frozenSegment
                if (!s || s.timeHi === undefined)
                    return 0
                var mid = (s.timeLo !== undefined) ? (s.timeLo + s.timeHi) / 2 : s.timeHi
                return loupe.axisYForYearFrac(mid) - height / 2
            }
        }

        // Destination mark — resolved populated detent (teleports across empty gaps).
        Rectangle {
            id: destMark
            objectName: "loupeDestMark"
            visible: loupe.destinationYear >= 0
            width: 12
            height: 6
            radius: 2
            color: Theme.amber
            x: axis.axisMid - width / 2
            y: loupe.axisYForYearFrac(loupe.destinationYear + 0.5) - height / 2
        }

        // Legible interval between marks.
        Rectangle {
            objectName: "loupeJumpSpan"
            visible: originMark.visible && destMark.visible
            x: axis.axisMid - 1
            width: 2
            color: Theme.amber
            opacity: 0.45
            y: Math.min(originMark.y + originMark.height / 2, destMark.y + destMark.height / 2)
            height: Math.max(2, Math.abs((originMark.y + originMark.height / 2) - (destMark.y + destMark.height / 2)))
        }
    }

    // Optional ≤4 cache-only thumbs — hidden entirely when cold.
    Row {
        id: thumbRow
        objectName: "loupeThumbs"
        visible: !loupe.undatedMode && loupe.sampleIds.length > 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: axis.bottom
        anchors.topMargin: 8
        anchors.leftMargin: 8
        anchors.rightMargin: 8
        spacing: 3
        Repeater {
            model: loupe.sampleIds
            delegate: Rectangle {
                width: Theme.loupeThumb
                height: Theme.loupeThumb
                radius: 3
                color: Theme.amberSoft
                clip: true
                Image {
                    anchors.fill: parent
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    source: modelData ? ("image://archive/cs/" + modelData) : ""
                }
            }
        }
    }

    Behavior on opacity {
        NumberAnimation { duration: loupe.reducedMotion ? 0 : Theme.fast }
    }
}
