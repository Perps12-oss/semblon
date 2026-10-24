import QtQuick

// One picture, large. Drag a loupe over any detail to find it again elsewhere.
Item {
    id: viewer
    objectName: "viewer"
    property bool active: shell.focusId !== ""
    property bool loupeOn: false
    property real lx: 0
    property real ly: 0
    property real lw: 0
    property real lh: 0
    property bool drawing: false
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    signal closed()

    visible: opacity > 0.01
    opacity: active ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    focus: active
    Accessible.role: Accessible.Pane
    Accessible.name: "Photo " + shell.focusName

    function resetZoom() { zoom = 1; panX = 0; panY = 0 }
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
    onShownIdChanged: resetZoom()
    function reset() { lx = 0; ly = 0; lw = 0; lh = 0; loupeOn = false; shell.clearDrawnQuery() }
    function search() {
        if (lw < 8 || lh < 8 || photo.paintedWidth <= 0)
            return
        shell.setRegion(lx / photo.paintedWidth, ly / photo.paintedHeight,
                        lw / photo.paintedWidth, lh / photo.paintedHeight)
        shell.findSimilar()
    }
    onActiveChanged: if (!active) reset()

    Rectangle { anchors.fill: parent; color: Theme.bg; opacity: 0.97 }

    Keys.onEscapePressed: { shell.escape(); viewer.closed() }
    Keys.onLeftPressed: shell.focusPrev()
    Keys.onRightPressed: shell.focusNext()
    Keys.onPressed: function (e) {
        if (e.key === Qt.Key_L) { loupeOn = !loupeOn; e.accepted = true }
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
            source: shell.focusId === "" ? "" : "image://archive/f/" + shell.focusId
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
                        visible: !viewer.loupeOn
                        Accessible.role: Accessible.Button
                        Accessible.name: "Pick " + (modelData.tag || "this area")
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: shell.selectObservation(modelData.id) }
                    }
                }
                Rectangle {
                    visible: viewer.lw > 0
                    x: viewer.lx; y: viewer.ly; width: viewer.lw; height: viewer.lh
                    radius: Math.min(width, height) / 2
                    color: "transparent"
                    border.width: 3
                    border.color: Theme.amber
                    Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.amber; opacity: 0.12 }
                }
                MouseArea {
                    anchors.fill: parent
                    enabled: viewer.loupeOn
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
            enabled: !viewer.loupeOn
            onDoubleTapped: viewer.zoom > 1 ? viewer.resetZoom() : viewer.zoomAt(point.position.x, point.position.y, 2.5)
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

    Row {
        x: Theme.pad
        y: Theme.pad
        spacing: Theme.gap
        Tool { label: "Back to photos"; onActivated: { shell.escape(); viewer.closed() } }
        Tool { label: "Previous"; onActivated: shell.focusPrev() }
        Tool { label: "Next"; onActivated: shell.focusNext() }
        Tool {
            label: viewer.loupeOn ? "Loupe on: drag over a detail" : "Find a detail"
            hint: "Draw around anything in the photo to find it in other photos"
            primary: viewer.loupeOn
            onActivated: { viewer.loupeOn = !viewer.loupeOn; if (!viewer.loupeOn) viewer.reset() }
        }
    }
    Flow {
        id: actions
        x: Theme.pad
        y: 56
        width: parent.width - Theme.pad * 2
        spacing: Theme.gap
        Tool { objectName: "similarAction"; label: "Find similar"; primary: true; visible: shell.selectionOnFocus; onActivated: shell.findSimilar() }
        Tool { objectName: "wholePhoto"; label: "Find more like this photo"; hint: "Shortcut W"; onActivated: shell.findSimilarWhole() }
        Tool { objectName: "sameFaceDoor"; label: "Find faces like these"; hint: "Shortcut F"; onActivated: shell.findSimilarFaces() }
        Tool { objectName: "duplicatesDoor"; label: "Find duplicates"; hint: "Ctrl+D"; onActivated: shell.scanDuplicates() }
        Tool { objectName: "nameThisArea"; label: "Describe this area"; visible: shell.selectionOnFocus && !shell.identifyBusy; onActivated: shell.nameSelection() }
        Tool { objectName: "askPhoto"; label: "Ask about this photo"; onActivated: shell.askPhoto() }
        Tool { objectName: "screenQueryAction"; label: "Pick on screen"; hint: "Ctrl+Shift+S"; visible: shell.screenQueryAvailable && !shell.screenQueryInProgress; onActivated: shell.startScreenQuery() }
        Tool { objectName: "screenQueryModeAction"; label: shell.screenQueryModeLabel; visible: shell.screenQueryAvailable; onActivated: shell.toggleScreenQueryMode() }
        Tool { objectName: "installSuggestedModel"; label: "Add the helper this search needs"; visible: shell.installSuggestionVisible && !shell.searchBusy; onActivated: shell.installSuggestedModel() }
        Tool { label: "Who is this?"; visible: shell.selectedObservationId !== ""; onActivated: shell.reviewFaceGroup(shell.selectedObservationId) }
        Tool { label: "More like this"; visible: shell.similarState === "ready"; onActivated: shell.setSearchQuality("max") }
        Tool { label: "Fewer, closer"; visible: shell.similarState === "ready"; onActivated: shell.setSearchQuality("fast") }
    }
    Row {
        id: refine
        x: Theme.pad
        y: actions.y + actions.height + 6
        spacing: Theme.gap
        visible: shell.selectionOnFocus
        Text { text: "Match on"; anchors.verticalCenter: parent.verticalCenter; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted }
        Tool { objectName: "refineSameLook"; label: "Same look"; primary: shell.refineMode !== "kind"; onActivated: shell.setRefineMode("same") }
        Tool { objectName: "refineSameKind"; label: "Same kind"; primary: shell.refineMode === "kind"; onActivated: shell.setRefineMode("kind") }
        Rectangle {
            width: 190; height: 34; radius: 3
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
    Row {
        x: Theme.pad
        anchors.bottom: strip.top
        anchors.bottomMargin: 48
        spacing: Theme.gap
        Text { objectName: "searchDoorLabel"; text: shell.searchDoorLabel; visible: text !== ""; font.family: Theme.ui; font.pixelSize: Theme.small; font.weight: Font.DemiBold; color: Theme.amber }
        Text { objectName: "searchQualityFocus"; text: "Search: " + shell.searchQualityLabel; visible: shell.similarState !== "idle"; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.faint }
        Text { objectName: "searchPhaseBadge"; text: shell.similarPhaseLabel; visible: text !== ""; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted }
        Text { objectName: "searchTiming"; text: shell.searchTimingLabel; visible: text !== ""; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.faint }
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
        text: shell.focusName
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
            anchors.rightMargin: Theme.pad
            y: 8
            width: parent.width * 0.45
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
                Accessible.name: "Open match " + (index + 1)
                Keys.onReturnPressed: shell.openFocus(mediaId)
                Image { anchors.fill: parent; source: "image://archive/t/" + mediaId; fillMode: Image.PreserveAspectCrop; asynchronous: true }
                Rectangle { anchors.fill: parent; color: "transparent"; border.width: parent.activeFocus ? 3 : 0; border.color: Theme.amber }
                MouseArea { anchors.fill: parent; onClicked: shell.openFocus(mediaId) }
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
