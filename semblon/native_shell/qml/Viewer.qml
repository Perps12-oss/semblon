import QtQuick

// One picture, large. Drag a loupe over any detail to find it again elsewhere.
Item {
    id: viewer
    property bool active: shell.focusId !== ""
    property bool loupeOn: false
    property real lx: 0
    property real ly: 0
    property real lw: 0
    property real lh: 0
    property bool drawing: false
    signal closed()

    visible: opacity > 0.01
    opacity: active ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    focus: active
    Accessible.role: Accessible.Pane
    Accessible.name: "Photo " + shell.focusName

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

        Image {
            id: photo
            anchors.fill: parent
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            cache: false
            source: shell.focusId === "" ? "" : "image://archive/f/" + shell.focusId
            sourceSize.width: Math.max(1, Math.round(stage.width * Screen.devicePixelRatio))
            sourceSize.height: Math.max(1, Math.round(stage.height * Screen.devicePixelRatio))
            scale: viewer.active ? 1 : 0.94
            Behavior on scale { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
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
        Tool { label: "Find more like this photo"; onActivated: shell.findSimilarWhole() }
        Tool { label: "Find faces like these"; onActivated: shell.findSimilarFaces() }
        Tool { objectName: "nameThisArea"; label: "Describe this area"; visible: shell.selectionOnFocus && !shell.identifyBusy; onActivated: shell.nameSelection() }
        Tool { objectName: "askPhoto"; label: "Ask about this photo"; onActivated: shell.askPhoto() }
        Tool { label: "Pick on screen"; visible: shell.screenQueryAvailable; onActivated: shell.startScreenQuery() }
        Tool { label: "Who is this?"; visible: shell.selectedObservationId !== ""; onActivated: shell.reviewFaceGroup(shell.selectedObservationId) }
        Tool { label: "More like this"; visible: shell.similarState === "ready"; onActivated: shell.setSearchQuality("max") }
        Tool { label: "Fewer, closer"; visible: shell.similarState === "ready"; onActivated: shell.setSearchQuality("fast") }
    }
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
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 130
        visible: viewer.loupeOn || shell.similarState !== "idle"
        Rectangle { anchors.fill: parent; color: Theme.surface; Rectangle { width: parent.width; height: 1; color: Theme.line } }
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
