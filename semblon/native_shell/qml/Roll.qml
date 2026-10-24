import QtQuick
import QtQuick.Shapes

// The Roll: the whole archive as one canvas, laid out as months, then days, then rows of prints.
// Every month and every day starts on its own row under its own divider, and every count is that
// section's own count.
Item {
    id: roll

    property real cellTarget: 168
    property real cellSize: cellTarget
    readonly property real minCell: 44
    readonly property real maxCell: 560
    readonly property int columns: Math.max(1, Math.floor(width / cellSize))
    readonly property real cellW: width / columns
    readonly property real monthH: 64
    readonly property real dayH: 34

    property var rows: []                    // month / day / photos rows, in display order
    property var monthList: []               // [{key, title, count, first, row}]
    property var photoRows: []               // row numbers that hold pictures
    property var monthMap: ({})
    property int photoCount: 0
    readonly property int count: photoCount
    readonly property alias view: grid

    property int currentPhoto: 0
    property var selected: ({})
    property int selCount: 0
    property int selAnchor: 0
    property string currentMonth: ""
    property string pinnedMonth: ""
    property string heading: ""
    property int headingCount: 0
    property int laidColumns: -1
    property bool zooming: false
    property int zoomAnchor: 0
    property bool internalMove: false

    property bool matchMode: shell.matchesOnRoll
    readonly property bool farOut: cellSize < 96
    property real bottomInset: 120           // the bottom bar's height plus a margin
    property bool dragPreview: false         // lets a screenshot show the lit edge
    readonly property bool lit: dropArea.containsDrag || dragPreview
    readonly property bool scrolling: grid.moving || settle.running
    readonly property real headerHeight: band.height
    readonly property bool dayBreaks: !matchMode && cellSize >= 120

    signal opened(string mediaId, rect cell)

    Behavior on cellSize {
        NumberAnimation { duration: Theme.medium; easing.type: Theme.easing }
    }

    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

    // --- layout -------------------------------------------------------------------------
    function relayout(anchor) {
        var atTop = grid.contentY <= -grid.topMargin + 2
        var keep = anchor !== undefined && anchor >= 0 ? anchor : (rows.length > 0 ? topIndex() : 0)
        var res = shell.rollLayout(columns, !matchMode, dayBreaks)
        var r = res.rows || []
        var pr = [], n = 0
        for (var i = 0; i < r.length; i++) {
            if (r[i].kind === "photos") {
                pr.push(i)
                n = r[i].first + r[i].n
            }
        }
        var map = {}
        var ms = res.months || []
        for (var m = 0; m < ms.length; m++)
            map[ms[m].key] = ms[m]
        laidColumns = columns
        rows = r
        photoRows = pr
        monthList = ms
        monthMap = map
        photoCount = n
        currentPhoto = clamp(currentPhoto, 0, Math.max(0, n - 1))
        if (selCount > 0 && !matchMode) {
            // Drop selections that no longer exist.
            var keepSel = {}, c = 0
            for (var k in selected)
                if (parseInt(k) < n) { keepSel[k] = true; c++ }
            selected = keepSel
            selCount = c
        }
        Qt.callLater(function () {
            if (n > 0 && (!atTop || zooming))
                jumpToIndex(keep)
            refreshHeading()
        })
    }

    function photoPos(i) {
        var lo = 0, hi = photoRows.length - 1, found = 0
        while (lo <= hi) {
            var mid = (lo + hi) >> 1
            if (rows[photoRows[mid]].first <= i) { found = mid; lo = mid + 1 }
            else hi = mid - 1
        }
        return found
    }
    function rowOfPhoto(i) { return photoRows.length === 0 ? 0 : photoRows[photoPos(i)] }
    function startOfRow(r) {
        var s = r
        while (s > 0 && rows[s - 1].kind !== "photos")
            s--
        return s
    }
    function placeRow(r) {
        if (rows.length === 0)
            return
        internalMove = true
        grid.positionViewAtIndex(r, ListView.Beginning)
        var it = grid.itemAtIndex(r)
        if (it) {
            var y = it.y - band.height
            var maxY = grid.contentHeight - grid.height + grid.bottomMargin
            grid.contentY = clamp(y, -grid.topMargin, Math.max(-grid.topMargin, maxY))
        }
        internalMove = false
    }

    // --- reading the position -----------------------------------------------------------
    function rowAtTop() {
        var y = grid.contentY + band.height + 2
        var r = grid.indexAt(grid.width / 2, y)
        if (r < 0)
            r = grid.indexAt(grid.width / 2, y + 14)
        return r < 0 ? 0 : r
    }
    function topIndex() {
        if (rows.length === 0)
            return 0
        return rows[Math.min(rows.length - 1, rowAtTop())].first
    }
    function refreshHeading() {
        if (photoCount <= 0 || rows.length === 0) {
            heading = ""; headingCount = 0; currentMonth = ""
            return
        }
        if (matchMode) {
            heading = "Closest matches"; headingCount = photoCount; currentMonth = ""
            return
        }
        var key = pinnedMonth !== "" ? pinnedMonth : rows[Math.min(rows.length - 1, rowAtTop())].month
        var m = monthMap[key]
        currentMonth = key
        heading = m ? m.title : "Undated"
        headingCount = m ? m.count : 0
    }

    // --- moving -------------------------------------------------------------------------
    function jumpToIndex(index) {
        if (photoCount <= 0)
            return
        var n = clamp(index, 0, photoCount - 1)
        placeRow(startOfRow(rowOfPhoto(n)))
        currentPhoto = n
        pinnedMonth = ""
        refreshHeading()
    }
    function jumpToFraction(f) {
        jumpToIndex(Math.round(f * Math.max(0, photoCount - 1)))
    }
    function jumpToMonth(key) {
        var m = monthMap[key]
        if (!m)
            return
        placeRow(m.row)
        currentPhoto = m.first
        pinnedMonth = key
        refreshHeading()
    }
    // Where a month's header row sits in the viewport right now (for the scrubber and for checks).
    function monthTopInView(key) {
        var m = monthMap[key]
        var it = m ? grid.itemAtIndex(m.row) : null
        return it ? it.y - grid.contentY : -1
    }
    function ensureVisible(i) {
        var r = rowOfPhoto(i)
        var it = grid.itemAtIndex(r)
        if (!it) {
            grid.positionViewAtIndex(r, ListView.Contain)
            it = grid.itemAtIndex(r)
        }
        if (!it)
            return
        internalMove = true
        var top = it.y - grid.contentY
        var bottom = top + it.height
        if (top < band.height + 4) {
            var s = grid.itemAtIndex(startOfRow(r))
            var ty = (s ? s.y : it.y) - band.height - 4
            grid.contentY = Math.max(-grid.topMargin, ty)
        } else if (bottom > grid.height - bottomInset) {
            grid.contentY += bottom - (grid.height - bottomInset)
        }
        internalMove = false
        pinnedMonth = ""
        refreshHeading()
    }
    function zoomBy(factor) {
        zoomAnchor = topIndex()
        zooming = true
        zoomHold.restart()
        cellTarget = clamp(cellTarget * factor, minCell, maxCell)
    }
    function zoomTo(size) {
        zoomAnchor = topIndex()
        zooming = true
        zoomHold.restart()
        cellTarget = clamp(size, minCell, maxCell)
    }
    function verticalStep(i, dir, steps) {
        var pos = photoPos(i)
        var row = rows[photoRows[pos]]
        var col = i - row.first
        var to = clamp(pos + dir * steps, 0, photoRows.length - 1)
        if (to === pos)
            return dir < 0 ? (pos === 0 ? i : row.first) : i
        var next = rows[photoRows[to]]
        return next.first + Math.min(col, next.n - 1)
    }
    function moveTo(i, extend) {
        var n = clamp(i, 0, Math.max(0, photoCount - 1))
        currentPhoto = n
        if (extend)
            selectRange(selAnchor, n)
        else
            selAnchor = n
        ensureVisible(n)
    }

    // --- selection ----------------------------------------------------------------------
    function isSelected(i) { return selected[i] === true }
    function toggleSelect(i) {
        var next = {}
        for (var k in selected)
            next[k] = true
        if (next[i]) delete next[i]
        else next[i] = true
        selected = next
        selCount = Object.keys(next).length
    }
    function selectRange(a, b) {
        var next = {}
        var lo = Math.min(a, b), hi = Math.max(a, b)
        for (var i = lo; i <= hi; i++)
            next[i] = true
        selected = next
        selCount = hi - lo + 1
    }
    function selectAll() {
        if (photoCount > 0)
            selectRange(0, photoCount - 1)
    }
    function clearSelection() {
        selected = ({})
        selCount = 0
    }
    function clickPhoto(i, modifiers, rect) {
        currentPhoto = i
        grid.forceActiveFocus()
        if (modifiers & Qt.ControlModifier) {
            toggleSelect(i)
            selAnchor = i
        } else if (modifiers & Qt.ShiftModifier) {
            selectRange(selAnchor, i)
        } else {
            clearSelection()
            selAnchor = i
            opened(shell.cellInfo(i).mediaId, rect)
        }
    }
    function openCurrent() {
        if (photoCount <= 0)
            return
        var it = grid.itemAtIndex(rowOfPhoto(currentPhoto))
        var col = currentPhoto - rows[rowOfPhoto(currentPhoto)].first
        var p = it ? it.mapToItem(roll, col * cellW, 0) : Qt.point(width / 2 - 50, height / 2 - 50)
        opened(shell.cellInfo(currentPhoto).mediaId, Qt.rect(p.x, p.y, cellW, cellW))
    }

    onColumnsChanged: if (columns !== laidColumns) relayout(zooming ? zoomAnchor : -1)
    onCellSizeChanged: if (zooming && photoCount > 0) jumpToIndex(zoomAnchor)
    onMatchModeChanged: relayout(0)
    onDayBreaksChanged: relayout(-1)
    Component.onCompleted: relayout(0)

    Connections {
        target: archiveModel
        function onModelReset() { Qt.callLater(roll.relayout, -1) }
        function onRowsInserted() { Qt.callLater(roll.relayout, -1) }
        function onRowsRemoved() { Qt.callLater(roll.relayout, -1) }
    }
    Timer { id: zoomHold; interval: Theme.medium + 80; onTriggered: roll.zooming = false }

    ListView {
        id: grid
        objectName: "rollGrid"
        anchors.fill: parent
        model: roll.rows
        clip: true
        cacheBuffer: 1200
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: false
        activeFocusOnTab: true
        focus: true
        topMargin: band.height + 6
        bottomMargin: roll.bottomInset
        flickDeceleration: 3200
        maximumFlickVelocity: 9000

        Accessible.role: Accessible.List
        Accessible.name: "Your photos, newest first. Use the arrow keys to move, Enter to open, Space to select."

        onContentYChanged: {
            if (!roll.internalMove)
                roll.pinnedMonth = ""
            roll.refreshHeading()
            settle.restart()
        }
        Keys.onReturnPressed: roll.openCurrent()
        Keys.onEnterPressed: roll.openCurrent()
        Keys.onPressed: function (event) {
            var shift = (event.modifiers & Qt.ShiftModifier) !== 0
            var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
            var cur = roll.currentPhoto
            var page = Math.max(1, Math.floor(grid.height / Math.max(1, roll.cellW)) - 1)
            var ok = true
            switch (event.key) {
            case Qt.Key_Left: roll.moveTo(cur - 1, shift); break
            case Qt.Key_Right: roll.moveTo(cur + 1, shift); break
            case Qt.Key_Up: roll.moveTo(roll.verticalStep(cur, -1, 1), shift); break
            case Qt.Key_Down: roll.moveTo(roll.verticalStep(cur, 1, 1), shift); break
            case Qt.Key_PageUp: roll.moveTo(roll.verticalStep(cur, -1, page), shift); break
            case Qt.Key_PageDown: roll.moveTo(roll.verticalStep(cur, 1, page), shift); break
            case Qt.Key_Home: roll.moveTo(0, shift); break
            case Qt.Key_End: roll.moveTo(roll.photoCount - 1, shift); break
            case Qt.Key_Space: roll.toggleSelect(cur); roll.selAnchor = cur; break
            case Qt.Key_A:
                if (ctrl) roll.selectAll(); else ok = false
                break
            case Qt.Key_Escape:
                if (roll.selCount > 0) roll.clearSelection(); else ok = false
                break
            case Qt.Key_Plus:
            case Qt.Key_Equal: roll.zoomBy(1.25); break
            case Qt.Key_Minus: roll.zoomBy(0.8); break
            default: ok = false
            }
            event.accepted = ok
        }

        delegate: Item {
            id: rowItem
            required property var modelData
            width: grid.width
            height: modelData.kind === "photos" ? roll.cellW
                  : (modelData.kind === "month" ? roll.monthH : roll.dayH)

            // Month divider.
            Item {
                objectName: "monthRow"
                visible: rowItem.modelData.kind === "month"
                anchors.fill: parent
                Rectangle {
                    x: Theme.gutter / 2
                    width: parent.width - Theme.gutter
                    y: 20
                    height: 1
                    color: Theme.amberEdge
                }
                Text {
                    x: Theme.gutter / 2
                    y: 28
                    text: String(rowItem.modelData.title || "").toUpperCase() + "   \u00b7   "
                          + rowItem.modelData.count + (rowItem.modelData.count === 1 ? " photo" : " photos")
                    font.family: Theme.ui
                    font.pixelSize: Theme.small
                    font.weight: Font.Bold
                    font.letterSpacing: 1.8
                    color: Theme.amber
                }
            }

            // Day divider in contact-sheet frame-number style.
            Item {
                objectName: "dayRow"
                visible: rowItem.modelData.kind === "day"
                anchors.fill: parent
                Text {
                    id: dayTag
                    x: Theme.gutter / 2
                    anchors.verticalCenter: parent.verticalCenter
                    text: rowItem.modelData.tag || ""
                    font.family: Theme.ui
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    font.letterSpacing: 1.6
                    color: Theme.text
                }
                Text {
                    id: dayCount
                    anchors.left: dayTag.right
                    anchors.leftMargin: 10
                    anchors.verticalCenter: parent.verticalCenter
                    text: rowItem.modelData.count + (rowItem.modelData.count === 1 ? " photo" : " photos")
                    font.family: Theme.ui
                    font.pixelSize: 11
                    font.letterSpacing: 0.6
                    color: Theme.muted
                }
                Rectangle {
                    anchors.left: dayCount.right
                    anchors.leftMargin: 12
                    anchors.right: parent.right
                    anchors.rightMargin: Theme.gutter / 2
                    anchors.verticalCenter: parent.verticalCenter
                    height: 1
                    color: Theme.line
                }
            }

            // A row of prints.
            Repeater {
                model: rowItem.modelData.kind === "photos" ? rowItem.modelData.n : 0
                delegate: Item {
                    id: cell
                    required property int index
                    readonly property int photo: rowItem.modelData.first + index
                    readonly property var info: shell.cellInfo(photo)
                    readonly property bool current: roll.currentPhoto === photo
                    readonly property bool chosen: roll.selected[photo] === true
                    readonly property bool hot: hover.containsMouse
                    x: index * roll.cellW
                    width: roll.cellW
                    height: roll.cellW
                    onHotChanged: rowItem.z = hot ? 2 : 0

                    Accessible.role: Accessible.Button
                    Accessible.name: (info.name || "Photo") + (info.when ? ", " + info.when : "")
                                     + (chosen ? ", selected" : "")

                    Rectangle {
                        id: frame
                        objectName: "printFrame"
                        anchors.fill: parent
                        anchors.margins: Theme.gutter / 2
                        color: Theme.surface
                        clip: true
                        scale: cell.hot || (cell.current && grid.activeFocus) ? 1.03 : 1
                        Behavior on scale { NumberAnimation { duration: Theme.fast } }

                        Image {
                            id: pic
                            objectName: "printImage"
                            anchors.fill: parent
                            source: cell.info.mediaId === "" ? ""
                                  : (roll.cellSize < 110 ? "image://archive/s/" : "image://archive/t/") + cell.info.mediaId
                            fillMode: Image.PreserveAspectCrop
                            readonly property bool cropped: fillMode === Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            sourceSize.width: 400
                            sourceSize.height: 400
                            opacity: status === Image.Ready ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Theme.slow; easing.type: Theme.easing } }
                        }
                        // Develop-in: a safelight wash that clears as the print arrives.
                        Rectangle {
                            anchors.fill: parent
                            color: Theme.amber
                            opacity: pic.status === Image.Ready ? 0 : 0.10
                            Behavior on opacity { NumberAnimation { duration: Theme.slow * 2; easing.type: Theme.easing } }
                        }
                        Rectangle {
                            anchors.fill: parent
                            color: Theme.amber
                            opacity: cell.chosen ? 0.18 : 0
                        }
                        Rectangle {
                            visible: roll.matchMode && !roll.farOut
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.margins: 6
                            radius: Theme.pill
                            color: Theme.amber
                            width: badge.implicitWidth + 16
                            height: badge.implicitHeight + 6
                            Text {
                                id: badge
                                anchors.centerIn: parent
                                text: cell.photo + 1
                                font.family: Theme.display
                                font.pixelSize: Theme.body
                                font.weight: Font.DemiBold
                                color: Theme.onAmber
                            }
                        }
                        // Date and time, on hover or keyboard focus.
                        Rectangle {
                            objectName: "printWhen"
                            visible: !roll.farOut && (cell.hot || (cell.current && grid.activeFocus)) && cell.info.when !== ""
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: whenText.implicitHeight + 10
                            color: Theme.scrim
                            Text {
                                id: whenText
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.margins: 8
                                anchors.verticalCenter: parent.verticalCenter
                                elide: Text.ElideRight
                                text: cell.info.when
                                font.family: Theme.ui
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                font.letterSpacing: 0.6
                                color: Theme.text
                            }
                        }
                        Rectangle {
                            objectName: "printCheck"
                            visible: cell.chosen
                            anchors.right: parent.right
                            anchors.top: parent.top
                            anchors.margins: 6
                            width: 22
                            height: 22
                            radius: 11
                            color: Theme.amber
                            Text {
                                anchors.centerIn: parent
                                text: "\u2713"
                                font.pixelSize: 14
                                font.weight: Font.Bold
                                color: Theme.onAmber
                            }
                        }
                        Rectangle {
                            anchors.fill: parent
                            color: "transparent"
                            border.width: cell.current && grid.activeFocus ? 3 : (cell.chosen ? 3 : (cell.hot ? 1 : 0))
                            border.color: Theme.amber
                        }
                    }
                    MouseArea {
                        id: hover
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: function (mouse) {
                            var p = cell.mapToItem(roll, 0, 0)
                            roll.clickPhoto(cell.photo, mouse.modifiers, Qt.rect(p.x, p.y, cell.width, cell.height))
                        }
                    }
                }
            }
        }

        // Ctrl + wheel zooms. A plain wheel scrolls.
        WheelHandler {
            acceptedModifiers: Qt.ControlModifier
            onWheel: function (event) {
                roll.zoomBy(Math.exp(event.angleDelta.y / 500))
            }
        }
        PinchHandler {
            id: pinch
            target: null
            property real startTarget: 168
            onActiveChanged: if (active) startTarget = roll.cellTarget
            onScaleChanged: if (active) roll.zoomTo(startTarget * scale)
        }
    }

    // The month you are looking at gets its own band. Pictures slide under a soft fade.
    // Add a folder and Settings sit in this band too, so they never float over a picture.
    Item {
        id: band
        objectName: "rollHeader"
        visible: roll.count > 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: Math.max(88, place.implicitHeight + Theme.pad * 2)
        z: 2
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: parent.height + 30
            gradient: Gradient {
                GradientStop { position: 0; color: Theme.bg }
                GradientStop { position: 0.74; color: Theme.bg }
                GradientStop { position: 1; color: Theme.bgClear }
            }
        }
        Column {
            id: place
            x: Theme.pad * 1.5
            y: Theme.pad
            spacing: 4
            Text {
                objectName: "rollTitle"
                width: Math.max(200, roll.width - Theme.pad * 3 - 270)
                elide: Text.ElideRight
                text: roll.heading
                font.family: Theme.display
                font.pixelSize: 38
                minimumPixelSize: 24
                fontSizeMode: Text.Fit
                font.weight: Font.Light
                color: Theme.text
            }
            Text {
                objectName: "rollCount"
                text: roll.selCount > 0
                      ? roll.selCount + (roll.selCount === 1 ? " photo selected" : " photos selected") + ". Esc clears."
                      : (roll.matchMode
                         ? roll.count + (roll.count === 1 ? " match, best first" : " matches, best first")
                         : (roll.headingCount + (roll.headingCount === 1 ? " photo" : " photos")))
                font.family: Theme.ui
                font.pixelSize: Theme.small
                color: roll.selCount > 0 ? Theme.amber : Theme.muted
            }
        }
    }

    Timer { id: settle; interval: 700 }

    // First run. One sentence, one action. The whole canvas takes a dropped folder,
    // and the edge of the window lights up while one is over it.
    Item {
        id: arrival
        objectName: "emptyState"
        anchors.fill: parent
        visible: shell.empty && !shell.jobActive
        opacity: visible ? 1 : 0

        Rectangle {
            anchors.fill: parent
            color: Theme.amber
            opacity: roll.lit ? 0.07 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.medium } }
        }
        Shape {
            id: dashedEdge
            objectName: "dropEdge"
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                strokeColor: roll.lit ? Theme.amber : Theme.amberEdge
                strokeWidth: roll.lit ? 3 : 2
                strokeStyle: ShapePath.DashLine
                dashPattern: [5, 5]
                fillColor: "transparent"
                startX: 12; startY: 12
                PathLine { x: dashedEdge.width - 12; y: 12 }
                PathLine { x: dashedEdge.width - 12; y: dashedEdge.height - 12 }
                PathLine { x: 12; y: dashedEdge.height - 12 }
                PathLine { x: 12; y: 12 }
            }
        }
        Column {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -40
            width: Math.min(parent.width - 120, 600)
            spacing: Theme.pad
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: roll.lit ? "Let go to add this folder." : "Your photos, right where you left them."
                font.family: Theme.display
                font.pixelSize: Theme.hero * 0.8
                font.weight: Font.Light
                color: Theme.text
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: "Drop a folder anywhere on this window, or choose one. Semblon only looks. Nothing is moved, changed or sent anywhere."
                font.family: Theme.ui
                font.pixelSize: Theme.lead
                color: Theme.muted
            }
            Text {
                objectName: "emptyStatus"
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                visible: shell.jobLabel !== "" || shell.canResume
                text: shell.jobLabel === "Last add failed"
                      ? "The last add didn't finish. Your photos were not changed. Try again, or choose another folder."
                      : (shell.canResume ? "The last add was stopped. Pick up where it left off, or choose another folder." : shell.jobLabel)
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.muted
            }
            Tool {
                objectName: "emptyResume"
                anchors.horizontalCenter: parent.horizontalCenter
                label: shell.jobLabel === "Last add failed" ? "Try again" : "Pick up where it left off"
                visible: shell.canResume && !shell.jobActive
                onActivated: shell.resumeJob()
            }
            Tool {
                objectName: "chooseFolder"
                anchors.horizontalCenter: parent.horizontalCenter
                label: "Choose a folder"
                primary: true
                pixel: Theme.body
                implicitHeight: 46
                onActivated: shell.addFolder()
                Component.onCompleted: forceActiveFocus()
            }
        }
    }

    // Folder being added: prints develop in as they are read.
    Item {
        id: tray
        anchors.fill: parent
        visible: shell.jobActive && roll.count < 12
        Flow {
            anchors.centerIn: parent
            width: Math.min(parent.width - 60, 720)
            spacing: 10
            Repeater {
                model: 18
                Rectangle {
                    width: 104
                    height: 104
                    color: Theme.surface
                    border.width: 1
                    border.color: Theme.line
                    SequentialAnimation on opacity {
                        running: tray.visible && !Theme.reducedMotion
                        loops: Animation.Infinite
                        PauseAnimation { duration: index * 90 }
                        NumberAnimation { to: 0.35; duration: 700 }
                        NumberAnimation { to: 1; duration: 700 }
                    }
                    Rectangle { anchors.fill: parent; color: Theme.amber; opacity: 0.08 }
                }
            }
        }
    }

    DropArea {
        id: dropArea
        anchors.fill: parent
        onDropped: function (drop) {
            if (drop.hasUrls && drop.urls.length > 0)
                shell.addFolderPath(drop.urls[0].toString())
        }
    }
}
