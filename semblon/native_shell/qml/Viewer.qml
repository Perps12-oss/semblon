import QtQuick

// One picture, large. Drag a loupe over any detail to find it again elsewhere.
Item {
    id: viewer
    objectName: "viewer"
    property bool active: shell.focusId !== ""
    property bool loupeOn: false
    property bool dotsOn: true
    property real lx: 0
    property real ly: 0
    property real lw: 0
    property real lh: 0
    property bool drawing: false
    // A result preview is presentation-only: it never changes the bridge focus or search state.
    property string previewId: ""
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    signal closed()

    visible: opacity > 0.01
    opacity: active ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    focus: active
    Accessible.role: Accessible.Pane
    Accessible.name: viewer.previewId !== "" ? "Previewing a similar result" : "Photo " + shell.focusName

    function resetZoom() { zoom = 1; panX = 0; panY = 0 }
    function returnFromPreview() { previewId = ""; viewer.forceActiveFocus() }
    function openPreviewAsFocus() {
        if (previewId === "") return
        var target = previewId
        previewId = ""
        shell.openDiscoveryHit(target)
    }
    // Zoom toward a point in the stage so the detail under the cursor stays put.
    function zoomAt(px, py, factor) {
        var z = Math.max(1, Math.min(8, zoom * factor))
        var k = z / zoom
        var cx = stage.width / 2, cy = stage.height / 2
        panX = (px - cx) - ((px - cx) - panX) * k
        panY = (py - cy) - ((py - cy) - panY) * k
        zoom = z
        if (zoom === 1) { panX = 0; panY = 0 }
    }
    property string shownId: shell.focusId
    onShownIdChanged: { resetZoom(); spots.clearTap(); spots.shimmer() }
    onPreviewIdChanged: { resetZoom(); spots.clearTap() }
    function reset() { lx = 0; ly = 0; lw = 0; lh = 0; loupeOn = false; spots.clearTap(); shell.clearDrawnQuery() }
    function syncSelectionFromShell() {
        if (!shell || !shell.selectionOnFocus || photo.paintedWidth <= 0)
            return
        lx = shell.selectionX * photo.paintedWidth
        ly = shell.selectionY * photo.paintedHeight
        lw = shell.selectionW * photo.paintedWidth
        lh = shell.selectionH * photo.paintedHeight
    }
    function zoomToMatchIfNeeded() {
        if (!shell || photo.paintedWidth <= 0)
            return
        var nx = shell.matchX, ny = shell.matchY, nw = shell.matchW, nh = shell.matchH
        if (nw <= 0 || nh <= 0)
            return
        var z = Math.min(8, Math.max(1.8, 0.85 / Math.max(nw, nh)))
        var cx = ((photo.width - photo.paintedWidth) / 2) + (nx + nw / 2) * photo.paintedWidth
        var cy = ((photo.height - photo.paintedHeight) / 2) + (ny + nh / 2) * photo.paintedHeight
        viewer.zoomAt(cx, cy, z / Math.max(viewer.zoom, 0.001))
    }
    Connections {
        target: shell
        enabled: viewer.active
        function onSelectionChanged() { viewer.syncSelectionFromShell() }
        function onSimilarChanged() {
            if (!shell.selectionOnFocus && shell.matchW > 0)
                viewer.zoomToMatchIfNeeded()
        }
    }
    function search() {
        if (lw < 8 || lh < 8 || photo.paintedWidth <= 0)
            return
        shell.setRegion(lx / photo.paintedWidth, ly / photo.paintedHeight,
                        lw / photo.paintedWidth, lh / photo.paintedHeight)
        shell.findSimilar()
    }
    onActiveChanged: if (!active) reset()

    Rectangle { anchors.fill: parent; color: Theme.bg; opacity: 0.97 }

    Keys.onEscapePressed: {
        if (previewId !== "") returnFromPreview()
        else if (moreMenu.shown) moreMenu.shown = false
        else { shell.escape(); viewer.closed() }
    }
    // While the loupe is on, arrows steer the circle instead of changing photo.
    Keys.onLeftPressed: function (e) { if (!(loupeOn && keyRegion(e))) shell.focusPrev() }
    Keys.onRightPressed: function (e) { if (!(loupeOn && keyRegion(e))) shell.focusNext() }
    Keys.onUpPressed: function (e) { if (loupeOn) keyRegion(e); else e.accepted = false }
    Keys.onDownPressed: function (e) { if (loupeOn) keyRegion(e); else e.accepted = false }
    Keys.onReturnPressed: function (e) { if (loupeOn) keyRegion(e); else e.accepted = false }
    Keys.onEnterPressed: function (e) { if (loupeOn) keyRegion(e); else e.accepted = false }
    Keys.onPressed: function (e) {
        if (e.key === Qt.Key_Period && (e.modifiers & Qt.ControlModifier)) { moreMenu.shown = !moreMenu.shown; e.accepted = true }
        else if (e.key === Qt.Key_L) { loupeOn = !loupeOn; e.accepted = true }
        else if (e.key === Qt.Key_D && !(e.modifiers & Qt.ControlModifier)) { dotsOn = !dotsOn; e.accepted = true }
    }
    // Keyboard-only loupe: arrows move the circle, Shift+arrows resize it, Enter searches.
    function keyRegion(e) {
        var w = photo.paintedWidth, h = photo.paintedHeight
        if (w <= 0) return false
        var step = Math.max(4, Math.min(w, h) * 0.04)
        var dx = 0, dy = 0
        if (e.key === Qt.Key_Left) dx = -step
        else if (e.key === Qt.Key_Right) dx = step
        else if (e.key === Qt.Key_Up) dy = -step
        else if (e.key === Qt.Key_Down) dy = step
        else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { search(); return true }
        else return false
        if (lw < 8 || lh < 8) {
            var s = Math.min(w, h) * 0.25
            lw = s; lh = s; lx = (w - s) / 2; ly = (h - s) / 2
        }
        if (e.modifiers & Qt.ShiftModifier) {
            lw = Math.max(8, Math.min(w - lx, lw + dx)); lh = Math.max(8, Math.min(h - ly, lh + dy))
        } else {
            lx = Math.max(0, Math.min(w - lw, lx + dx)); ly = Math.max(0, Math.min(h - lh, ly + dy))
        }
        return true
    }

    Item {
        id: stage
        anchors.fill: parent
        anchors.margins: Theme.pad
        anchors.bottomMargin: 150
        anchors.topMargin: 104

        Item {
            id: zoomLayer
            objectName: "photoView"
            width: stage.width
            height: stage.height
            x: viewer.panX
            y: viewer.panY
            scale: (viewer.active ? 1 : 0.94) * viewer.zoom
            transformOrigin: Item.Center
            Behavior on scale { enabled: viewer.zoom === 1; NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
        Image {
            id: photo
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: false
            source: (viewer.previewId !== "" ? "image://archive/f/" + viewer.previewId : (shell.focusId === "" ? "" : "image://archive/f/" + shell.focusId))
            sourceSize.width: Math.max(1, Math.round(stage.width * Screen.devicePixelRatio))
            sourceSize.height: Math.max(1, Math.round(stage.height * Screen.devicePixelRatio))
            Accessible.ignored: true

            Item {
                id: canvas
                x: (photo.width - photo.paintedWidth) / 2
                y: (photo.height - photo.paintedHeight) / 2
                width: photo.paintedWidth
                height: photo.paintedHeight

                Repeater {
                    model: shell.focusObservationBoxes
                    delegate: Rectangle {
                        required property var modelData
                        x: modelData.nx * canvas.width
                        y: modelData.ny * canvas.height
                        width: Math.max(2, modelData.nw * canvas.width)
                        height: Math.max(2, modelData.nh * canvas.height)
                        color: "transparent"
                        border.width: shell.selectedObservationId === modelData.id ? 3 : 1
                        border.color: shell.selectedObservationId === modelData.id ? Theme.amber : Theme.muted
                        visible: viewer.previewId === "" && !viewer.loupeOn && shell.selectedObservationId === modelData.id
                        Accessible.role: Accessible.Button
                        Accessible.name: "Pick " + (modelData.tag || "this area")
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: shell.selectObservation(modelData.id) }
                    }
                }
                Rectangle {
                    visible: viewer.previewId === "" && viewer.lw > 0
                    x: viewer.lx; y: viewer.ly; width: viewer.lw; height: viewer.lh
                    radius: Math.min(width, height) / 2
                    color: "transparent"
                    border.width: 3
                    border.color: Theme.amber
                    Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.amber; opacity: 0.12 }
                }
                // Match box when the focused photo is a hit (not the query selection).
                Rectangle {
                    id: matchBox
                    objectName: "focusMatchBox"
                    visible: viewer.previewId === "" && canvas.width > 0 && shell.matchW > 0 && shell.matchH > 0
                             && !shell.selectionOnFocus
                    x: shell.matchX * canvas.width
                    y: shell.matchY * canvas.height
                    width: Math.max(2, shell.matchW * canvas.width)
                    height: Math.max(2, shell.matchH * canvas.height)
                    color: "transparent"
                    border.width: 3
                    border.color: Theme.amber
                    Rectangle { anchors.fill: parent; color: Theme.amber; opacity: 0.10 }
                }
                Hotspots {
                    id: spots
                    picture: canvas
                    allowed: viewer.previewId === "" && viewer.dotsOn && !viewer.loupeOn
                    onPickedDot: function (dot) {
                        clearTap()
                        if (dot.joined) {
                            shell.setRegion(dot.nx, dot.ny, dot.nw, dot.nh)
                            showTap(dot.nx + "," + dot.ny + "," + dot.nw + "," + dot.nh)
                            shell.findSimilar()
                        } else {
                            shell.selectObservation(dot.id)
                        }
                    }
                    onPickedSpot: function (nx, ny) { showTap(shell.pointAt(nx, ny)) }
                }
                TapHandler {
                    objectName: "spotTap"
                    enabled: viewer.previewId === "" && !viewer.loupeOn
                    onTapped: function (ep) { if (tapCount > 1) spots.cancelPending(); else spots.tapped(ep.position.x, ep.position.y) }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: viewer.previewId === "" && viewer.loupeOn
                    cursorShape: viewer.loupeOn ? Qt.CrossCursor : Qt.ArrowCursor
                    property real sx: 0
                    property real sy: 0
                    onPressed: function (m) { sx = m.x; sy = m.y; viewer.lx = m.x; viewer.ly = m.y; viewer.lw = 0; viewer.lh = 0 }
                    onPositionChanged: function (m) {
                        var x = Math.max(0, Math.min(width, m.x)), y = Math.max(0, Math.min(height, m.y))
                        viewer.lx = Math.min(sx, x); viewer.ly = Math.min(sy, y)
                        viewer.lw = Math.abs(x - sx); viewer.lh = Math.abs(y - sy)
                    }
                    onReleased: viewer.search()
                }
            }
        }
        }
        DragHandler {
            enabled: viewer.zoom > 1 && !viewer.loupeOn
            target: null
            property real bx: 0
            property real by: 0
            onActiveChanged: if (active) { bx = viewer.panX; by = viewer.panY }
            onActiveTranslationChanged: if (active) { viewer.panX = bx + activeTranslation.x; viewer.panY = by + activeTranslation.y }
        }
        WheelHandler {
            onWheel: function (e) { viewer.zoomAt(point.position.x, point.position.y, Math.exp(e.angleDelta.y / 400)) }
        }
        PinchHandler {
            target: null
            property real start: 1
            onActiveChanged: if (active) start = viewer.zoom
            onActiveScaleChanged: if (active) viewer.zoomAt(centroid.position.x, centroid.position.y, start * activeScale / viewer.zoom)
        }
        TapHandler {
            enabled: viewer.previewId === "" && !viewer.loupeOn
            onDoubleTapped: { spots.cancelPending(); if (viewer.zoom > 1) viewer.resetZoom(); else viewer.zoomAt(point.position.x, point.position.y, 2.5) }
        }
        Text {
            anchors.centerIn: parent
            visible: photo.status === Image.Loading
            text: "Developing…"
            font.family: Theme.display
            font.pixelSize: Theme.title
            color: Theme.muted
        }
    }

    Rectangle {
        objectName: "dotHint"
        visible: viewer.dotsOn && !viewer.loupeOn && shell.hotspots.length > 0 && shell.similarState !== "ready" && !shell.searchBusy
        anchors.horizontalCenter: parent.horizontalCenter
        y: Theme.pad + 4
        width: hintText.implicitWidth + Theme.pad * 1.4
        height: 32
        radius: 16
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        Text {
            id: hintText
            anchors.centerIn: parent
            text: "Tap a dot to find more like it. Tap anywhere to look there."
            font.family: Theme.ui
            font.pixelSize: Theme.small
            color: Theme.muted
        }
        Accessible.role: Accessible.StaticText
        Accessible.name: hintText.text
    }
    // Four things stay in view. Everything else lives behind "More…" and Ctrl+K.
    Row {
        id: topBar
        x: Theme.pad
        y: Theme.pad
        spacing: Theme.gap
        Tool { label: "Back to photos"; visible: viewer.previewId === ""; onActivated: { shell.escape(); viewer.closed() } }
        Tool { objectName: "returnFromPreview"; label: "Return to original"; visible: viewer.previewId !== ""; onActivated: viewer.returnFromPreview() }
        Tool { objectName: "previewThisPhoto"; label: "Open this photo"; visible: viewer.previewId !== ""; primary: true; onActivated: viewer.openPreviewAsFocus() }
        Tool { label: "Previous"; visible: viewer.previewId === ""; onActivated: shell.focusPrev() }
        Tool { label: "Next"; visible: viewer.previewId === ""; onActivated: shell.focusNext() }
        Tool {
            objectName: "findDetail"
                visible: viewer.previewId === ""
            label: viewer.loupeOn ? "Loupe on: drag, or use arrow keys and Enter" : "Find this part again"
            hint: "Draw around anything in the photo to find it in other photos"
            primary: true
            onActivated: { viewer.loupeOn = !viewer.loupeOn; if (!viewer.loupeOn) viewer.reset() }
        }
        Tool {
            objectName: "moreButton"
            label: "More…"
            hint: "More things to do with this photo"
            selected: moreMenu.shown
            onActivated: moreMenu.shown = !moreMenu.shown
        }
    }
    Tool {
        objectName: "installSuggestedModel"
        x: Theme.pad
        y: Theme.pad + 48
        label: "Get finding-by-look ready"
        visible: shell.installSuggestionVisible && !shell.searchBusy
        onActivated: shell.installSuggestedModel()
    }
    Rectangle {
        id: moreMenu
        objectName: "moreMenu"
        property bool shown: false
        visible: shown
        x: Theme.pad
        y: Theme.pad + 48
        z: 30
        width: 340
        height: menuCol.implicitHeight + 16
        radius: Theme.radius
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        Accessible.role: Accessible.PopupMenu
        Accessible.name: "More things to do with this photo"
        Keys.onEscapePressed: { shown = false; viewer.forceActiveFocus() }
        function pick(fn) { shown = false; viewer.forceActiveFocus(); fn() }
        Column {
            id: menuCol
            x: 8; y: 8
            width: parent.width - 16
            spacing: 4
            Tool { objectName: "backDiscovery"; width: menuCol.width; label: "Back to the previous find"; visible: shell.canBackDiscovery; onActivated: moreMenu.pick(function () { viewer.previewId = ""; shell.backToDiscovery() }) }
            Tool { objectName: "keepDiscovery"; width: menuCol.width; label: "Keep this find"; visible: shell.similarState === "ready" && shell.selectionOnFocus; onActivated: moreMenu.pick(function () { shell.keepDiscovery() }) }
            Tool { objectName: "seeThisDay"; width: menuCol.width; label: "See this day"; visible: viewer.previewId === ""; onActivated: moreMenu.pick(function () { shell.showDayAroundFocus(); if (shell.scopeKind === "day") { shell.escape(); viewer.closed() } }) }
            Tool { objectName: "wholePhoto"; width: menuCol.width; label: "Find photos like this one"; hint: "Shortcut W"; onActivated: moreMenu.pick(shell.findSimilarWhole) }
            Tool { objectName: "similarAction"; width: menuCol.width; label: "Find the picked area elsewhere"; hint: "Shortcut S"; visible: shell.selectionOnFocus; onActivated: moreMenu.pick(shell.findSimilar) }
            Tool { objectName: "sameFaceDoor"; width: menuCol.width; label: "Find faces like these"; hint: "Shortcut F"; onActivated: moreMenu.pick(shell.findSimilarFaces) }
            Tool { objectName: "duplicatesDoor"; width: menuCol.width; label: "Find copies of this photo"; hint: "Ctrl+D"; onActivated: moreMenu.pick(shell.scanDuplicates) }
            Tool { objectName: "nameThisArea"; width: menuCol.width; label: "Describe this area"; visible: shell.selectionOnFocus && !shell.identifyBusy; onActivated: moreMenu.pick(shell.nameSelection) }
            Tool { objectName: "askPhoto"; width: menuCol.width; label: "Ask about this photo"; onActivated: moreMenu.pick(shell.askPhoto) }
            Tool { width: menuCol.width; label: "Who is this?"; visible: shell.selectedObservationId !== ""; onActivated: moreMenu.pick(function () { shell.reviewFaceGroup(shell.selectedObservationId) }) }
            Tool { objectName: "screenQueryAction"; width: menuCol.width; label: "Pick on screen"; hint: "Ctrl+Shift+S"; visible: shell.screenQueryAvailable && !shell.screenQueryInProgress; onActivated: moreMenu.pick(shell.startScreenQuery) }
            Tool { objectName: "screenQueryModeAction"; width: menuCol.width; label: shell.screenQueryModeLabel; visible: shell.screenQueryAvailable; onActivated: moreMenu.pick(shell.toggleScreenQueryMode) }
            Tool { objectName: "moreMatches"; width: menuCol.width; label: "Show more matches"; visible: shell.similarState === "ready"; onActivated: moreMenu.pick(function () { shell.setSearchQuality("max") }) }
            Tool { objectName: "closerMatches"; width: menuCol.width; label: "Show fewer, closer matches"; visible: shell.similarState === "ready"; onActivated: moreMenu.pick(function () { shell.setSearchQuality("fast") }) }
            Row {
                id: refine
                spacing: Theme.gap
                visible: shell.selectionOnFocus
                Text { text: "Match on"; anchors.verticalCenter: parent.verticalCenter; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted }
                Tool { objectName: "refineSameLook"; label: "Same look"; primary: shell.refineMode !== "kind"; onActivated: shell.setRefineMode("same") }
                Tool { objectName: "refineSameKind"; label: "Same kind"; primary: shell.refineMode === "kind"; onActivated: shell.setRefineMode("kind") }
            }
            Rectangle {
                width: menuCol.width; height: 34; radius: 3
                visible: shell.selectionOnFocus
                color: "transparent"
                border.width: refineWord.activeFocus ? 2 : 1
                border.color: refineWord.activeFocus ? Theme.amber : Theme.line
                TextInput {
                    id: refineWord
                    objectName: "refineWord"
                    anchors.fill: parent
                    anchors.margins: 8
                    verticalAlignment: TextInput.AlignVCenter
                    text: shell.refineModifier
                    font.family: Theme.ui
                    font.pixelSize: Theme.small
                    color: Theme.text
                    selectByMouse: true
                    clip: true
                    Accessible.name: "Add a word to narrow the search"
                    onAccepted: shell.setRefineModifier(text)
                    Text { visible: !parent.text && !parent.activeFocus; text: "Add a word, such as red"; font: parent.font; color: Theme.faint }
                }
            }
        }
    }
    Row {
        x: Theme.pad
        anchors.bottom: strip.top
        anchors.bottomMargin: 48
        spacing: Theme.gap
        Text { objectName: "searchDoorLabel"; text: shell.searchDoorLabel; visible: text !== ""; font.family: Theme.ui; font.pixelSize: Theme.small; font.weight: Font.DemiBold; color: Theme.amber }
        Text { objectName: "searchPhaseBadge"; text: shell.similarPhaseLabel; visible: text !== ""; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted }
        Text { objectName: "nameConfidence"; text: shell.nameConfidenceLabel; visible: text !== ""; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted }
        Text { objectName: "screenQueryProgress"; text: shell.screenQueryProgressLabel; visible: shell.screenQueryInProgress; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.amber }
    }
    Shortcut { sequence: "S"; enabled: viewer.active && shell.selectionOnFocus; onActivated: shell.findSimilar() }
    Shortcut { sequence: "W"; enabled: viewer.active; onActivated: shell.findSimilarWhole() }
    Shortcut { sequence: "F"; enabled: viewer.active; onActivated: shell.findSimilarFaces() }
    Shortcut { sequence: "Ctrl+D"; enabled: viewer.active; onActivated: shell.scanDuplicates() }
    Shortcut { sequence: "Ctrl+Shift+S"; enabled: shell.screenQueryAvailable && !shell.screenQueryInProgress; onActivated: shell.startScreenQuery() }
    Text {
        x: Theme.pad
        anchors.bottom: strip.top
        anchors.bottomMargin: 4
        width: parent.width - Theme.pad * 2
        text: shell.resultText
        wrapMode: Text.WordWrap
        font.family: Theme.ui
        font.pixelSize: Theme.small
        color: Theme.muted
        visible: shell.resultText !== ""
    }
    Text {
        objectName: "nameNote"
        x: Theme.pad
        anchors.bottom: strip.top
        anchors.bottomMargin: 26
        width: parent.width - Theme.pad * 2
        text: shell.nameNote
        wrapMode: Text.WordWrap
        font.family: Theme.display
        font.pixelSize: Theme.body
        color: Theme.text
        visible: shell.nameNote !== ""
    }
    Text {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.pad + 8
        text: viewer.previewId !== "" ? "Previewing a match" : shell.focusName
        font.family: Theme.display
        font.pixelSize: Theme.lead
        color: Theme.muted
        elide: Text.ElideMiddle
        width: Math.min(360, parent.width / 3)
        horizontalAlignment: Text.AlignRight
    }

    // Matches from the loupe, as a strip of small prints under the photo.
    Item {
        id: strip
        objectName: "similarStrip"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 130
        visible: viewer.loupeOn || shell.similarState !== "idle"
        Rectangle { anchors.fill: parent; color: Theme.surface; Rectangle { width: parent.width; height: 1; color: Theme.line } }
        Text {
            objectName: "matchHonesty"
            anchors.right: parent.right
            anchors.rightMargin: Theme.pad + 170
            y: 8
            width: parent.width * 0.35
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
            text: shell.similarCaution
            visible: shell.similarState === "ready" && text !== ""
            font.family: Theme.ui
            font.pixelSize: Theme.tiny
            color: Theme.faint
        }
        Text {
            objectName: "searchStatus"
            x: Theme.pad; y: 8
            text: shell.searchBusy ? "Looking through your photos…"
                : shell.similarState === "ready" ? (shell.similarCount === 0 ? "Nothing like that anywhere else yet." : shell.similarCount + " places this shows up")
                : "Drag around a detail, such as a face, a mug or a sign."
            font.family: Theme.ui
            font.pixelSize: Theme.small
            color: Theme.muted
        }
        ListView {
            anchors.fill: parent
            anchors.topMargin: 30
            anchors.leftMargin: Theme.pad
            orientation: ListView.Horizontal
            spacing: 6
            model: similarModel
            clip: true
            delegate: Item {
                width: 84; height: 84
                activeFocusOnTab: true
                Accessible.role: Accessible.Button
                Accessible.name: "Preview match " + (index + 1)
                Keys.onReturnPressed: { viewer.previewId = mediaId; viewer.forceActiveFocus() }
                Image {
                    id: thumb
                    anchors.fill: parent
                    source: "image://archive/t/" + mediaId
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                }
                // Fit (not crop) so the normalized match box stays on the pictured region.
                Item {
                    anchors.centerIn: thumb
                    width: thumb.paintedWidth
                    height: thumb.paintedHeight
                    visible: matchW > 0 && matchH > 0
                    Rectangle {
                        objectName: "stripMatchBox"
                        x: matchX * parent.width
                        y: matchY * parent.height
                        width: Math.max(2, matchW * parent.width)
                        height: Math.max(2, matchH * parent.height)
                        color: "transparent"
                        border.width: 2
                        border.color: Theme.amber
                    }
                }
                Rectangle { anchors.fill: parent; color: "transparent"; border.width: parent.activeFocus ? 3 : 0; border.color: Theme.amber }
                Rectangle { anchors.fill: parent; color: viewer.previewId === mediaId ? Theme.amber : "transparent"; opacity: viewer.previewId === mediaId ? 0.14 : 0; border.width: viewer.previewId === mediaId ? 2 : 0; border.color: Theme.amber }
                MouseArea { anchors.fill: parent; onClicked: { viewer.previewId = mediaId; viewer.forceActiveFocus() } }
            }
        }
        Row {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 6
            spacing: Theme.gap
            visible: shell.similarState === "ready"
            Tool { label: "Show on the roll"; onActivated: { shell.showMatchesOnRoll(); shell.escape(); viewer.closed() } }
        }
    }
}
