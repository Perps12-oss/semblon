import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtMultimedia

ApplicationWindow {
    id: window
    width: 1440
    height: 900
    visible: true
    title: "Semblon"
    color: "#141A22"

    readonly property int motion: shell.reducedMotion ? 0 : 180

    Shortcut {
        sequences: [StandardKey.Cancel, "Escape"]
        onActivated: shell.escape()
    }
    Shortcut {
        sequence: "Right"
        enabled: shell.focusId !== ""
        onActivated: shell.focusNext()
    }
    Shortcut {
        sequence: "Left"
        enabled: shell.focusId !== ""
        onActivated: shell.focusPrev()
    }
    Shortcut {
        sequence: "Return"
        enabled: shell.focusId === "" && !shell.empty
        onActivated: shell.openIndex(grid.currentIndex)
    }

    header: Rectangle {
        color: "#141A22"
        height: 72
        width: window.width

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: "#243140"
        }

        Column {
            id: brand
            anchors.left: parent.left
            anchors.leftMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            Text {
                id: wordmark
                text: "Semblon"
                color: "#E7EEF5"
                font.family: "Segoe UI Variable"
                font.pixelSize: 20
                font.weight: Font.DemiBold
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shell.wordmark()
                }
            }
            Text {
                id: lensLine
                objectName: "lensLine"
                text: shell.lensLabel
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                font.letterSpacing: 0.4
            }
            Text {
                objectName: "peopleButton"
                text: "People"
                color: peopleArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                MouseArea {
                    id: peopleArea
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shell.openPeople()
                }
            }
        }

        Rectangle {
            id: command
            width: 320
            height: 36
            visible: false
            radius: 8
            color: "#1C2430"
            border.color: commandField.activeFocus ? "#2DD4BF" : "#243140"
            border.width: 1
            anchors.left: brand.right
            anchors.leftMargin: 36
            anchors.verticalCenter: parent.verticalCenter

            TextField {
                id: commandField
                objectName: "commandField"
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: TextInput.AlignVCenter
                placeholderText: "Find"
                placeholderTextColor: "#6E8294"
                color: "#E7EEF5"
                font.family: "Segoe UI"
                font.pixelSize: 14
                background: Item {}
                selectByMouse: true
                onAccepted: shell.submitCommand(text)
            }
        }

        Row {
            anchors.right: parent.right
            anchors.rightMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            visible: shell.jobActive
            objectName: "processingMark"

            Item {
                width: 16
                height: 16
                anchors.verticalCenter: parent.verticalCenter
                RotationAnimation on rotation {
                    running: shell.jobActive && !shell.reducedMotion
                    loops: Animation.Infinite
                    duration: 1100
                    from: 0
                    to: 360
                }
                Canvas {
                    anchors.fill: parent
                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        ctx.strokeStyle = "#2DD4BF"
                        ctx.lineWidth = 1.5
                        ctx.beginPath()
                        ctx.arc(width / 2, height / 2, 6, 0, Math.PI * 1.35)
                        ctx.stroke()
                    }
                    Component.onCompleted: requestPaint()
                }
            }
            Text {
                text: shell.jobLabel
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                objectName: "pauseJob"
                text: shell.jobState === "paused" ? "Resume" : "Pause"
                visible: shell.jobActive
                color: pauseArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    id: pauseArea
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shell.jobState === "paused" ? shell.resumeJob() : shell.pauseJob()
                }
            }
            Text {
                objectName: "cancelJob"
                text: "Cancel"
                color: cancelArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    id: cancelArea
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shell.cancelJob()
                }
            }
        }

        Text {
            objectName: "resumeJob"
            text: "Resume"
            visible: shell.canResume && !shell.jobActive
            anchors.right: parent.right
            anchors.rightMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            color: resumeArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
            font.family: "Segoe UI"
            font.pixelSize: 13
            MouseArea {
                id: resumeArea
                anchors.fill: parent
                anchors.margins: -6
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: shell.resumeJob()
            }
        }
    }

    Item {
        id: stage
        anchors.fill: parent

        Rectangle {
            objectName: "peopleDesk"
            anchors.fill: parent
            visible: shell.peopleOpen && shell.focusId === ""
            color: "#10161C"
            Column {
                anchors.fill: parent
                anchors.margins: 28
                spacing: 12
                Text {
                    text: "People"
                    color: "#E7EEF5"
                    font.pixelSize: 22
                }
                Text {
                    objectName: "peopleEmpty"
                    visible: shell.peopleEmpty
                    text: "No groups yet."
                    color: "#8AA0B2"
                }
                ListView {
                    objectName: "peopleList"
                    width: 280
                    height: 220
                    model: peopleModel
                    delegate: Text {
                        text: title + " · " + faceCount
                        color: shell.selectedSubject === subject ? "#5EEAD4" : "#E7EEF5"
                        MouseArea {
                            anchors.fill: parent
                            onClicked: shell.selectGroup(subject)
                        }
                    }
                }
                Text {
                    objectName: "peopleEvidence"
                    visible: shell.evidenceId !== ""
                    text: "Evidence"
                    color: "#8AA0B2"
                    MouseArea {
                        anchors.fill: parent
                        onClicked: shell.openEvidence(shell.evidenceId)
                    }
                }
                TextField {
                    id: decisionText
                    objectName: "decisionText"
                    width: 240
                    placeholderText: "Name or note"
                }
                Row {
                    spacing: 12
                    Text { text: "Name"; color: "#5EEAD4"; MouseArea { anchors.fill: parent; onClicked: shell.decide("name", shell.selectedSubject, decisionText.text) } }
                    Text { text: "Merge"; color: "#5EEAD4"; MouseArea { anchors.fill: parent; onClicked: shell.decide("merge", shell.selectedSubject, decisionText.text) } }
                    Text { text: "Split"; color: "#5EEAD4"; MouseArea { anchors.fill: parent; onClicked: shell.decide("split", shell.selectedSubject, decisionText.text) } }
                    Text { text: "Ignore"; color: "#5EEAD4"; MouseArea { anchors.fill: parent; onClicked: shell.decide("ignore", shell.selectedSubject, "") } }
                    Text { text: "Note"; color: "#5EEAD4"; MouseArea { anchors.fill: parent; onClicked: shell.decide("note", shell.selectedSubject, decisionText.text) } }
                }
                Text {
                    objectName: "peopleNote"
                    text: shell.peopleNote
                    color: "#8AA0B2"
                }
                Text {
                    objectName: "peopleBack"
                    text: "Back"
                    color: "#8AA0B2"
                    MouseArea { anchors.fill: parent; onClicked: shell.closePeople() }
                }
            }
        }

        GridView {
            id: grid
            objectName: "fieldGrid"
            anchors.fill: parent
            anchors.margins: 22
            visible: !shell.empty
            opacity: shell.focusId === "" ? 1 : 0
            cellWidth: 196
            cellHeight: 196
            cacheBuffer: 400
            boundsBehavior: Flickable.StopAtBounds
            model: archiveModel
            currentIndex: 0
            enabled: shell.focusId === ""
            keyNavigationEnabled: shell.focusId === ""
            highlightFollowsCurrentItem: false
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            delegate: Item {
                width: grid.cellWidth
                height: grid.cellHeight

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 6
                    color: "#1C2430"
                    radius: 2

                    Image {
                        anchors.fill: parent
                        anchors.margins: 1
                        visible: kind !== "video"
                        source: kind !== "video" ? ("image://archive/t/" + mediaId) : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Text {
                        visible: false
                        text: ""
                    }

                    Rectangle {
                        anchors.fill: parent
                        color: "transparent"
                        border.width: tile.containsMouse || grid.currentIndex === index ? 1 : 0
                        border.color: grid.currentIndex === index ? "#2DD4BF" : "#3D4C5C"
                        radius: 2
                    }

                    MouseArea {
                        id: tile
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            grid.currentIndex = index
                            shell.setScroll(grid.contentY)
                            shell.openFocus(mediaId)
                        }
                    }
                }
            }

            onContentYChanged: {
                if (shell.focusId === "")
                    shell.setScroll(contentY)
            }

            Connections {
                target: shell
                function onFocusChanged() {
                    if (shell.focusId === "")
                        grid.contentY = shell.scrollY
                }
            }
        }

        Column {
            objectName: "emptyState"
            visible: shell.empty
            anchors.centerIn: parent
            spacing: 14
            width: 420

            Text {
                width: parent.width
                text: "Your archive is empty"
                color: "#E7EEF5"
                font.family: "Segoe UI Variable"
                font.pixelSize: 28
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
            }
            Text {
                width: parent.width
                text: shell.jobActive
                      ? "Adding the folder. The archive will appear here."
                      : "Add a folder of photos. The files stay where they are."
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 15
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
            }
            Item { width: 1; height: 8 }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: addLabel.implicitWidth + 36
                height: 40
                radius: 8
                color: addArea.containsMouse ? "#12343A" : "#1C2430"
                border.color: "#2DD4BF"
                border.width: 1
                visible: !shell.jobActive
                Text {
                    id: addLabel
                    anchors.centerIn: parent
                    text: "Add a folder"
                    color: "#5EEAD4"
                    font.family: "Segoe UI"
                    font.pixelSize: 14
                }
                MouseArea {
                    id: addArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shell.addFolder()
                }
            }
        }

        Item {
            id: focusLayer
            objectName: "focusLayer"
            anchors.fill: parent
            visible: shell.focusId !== ""
            opacity: shell.focusId !== "" ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            Rectangle {
                anchors.fill: parent
                color: "#10161C"
            }

            Image {
                id: photo
                anchors.fill: parent
                anchors.margins: 48
                visible: shell.focusKind !== "video"
                source: (shell.focusId !== "" && shell.focusKind !== "video")
                        ? ("image://archive/f/" + shell.focusId) : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
            }

            MouseArea {
                id: regionDrag
                objectName: "regionDrag"
                anchors.fill: photo
                enabled: shell.focusKind !== "video" && photo.paintedWidth > 0
                property real rx: 0
                property real ry: 0
                property real rw: 0
                property real rh: 0
                property bool hasRect: false
                property real x0: 0
                property real y0: 0

                function contentOrigin() {
                    return Qt.point(
                        (width - photo.paintedWidth) / 2,
                        (height - photo.paintedHeight) / 2
                    )
                }

                function insidePainted(px, py) {
                    var origin = contentOrigin()
                    return photo.paintedWidth > 1 && photo.paintedHeight > 1
                            && px >= origin.x && py >= origin.y
                            && px < origin.x + photo.paintedWidth
                            && py < origin.y + photo.paintedHeight
                }

                onPressed: function(mouse) {
                    shell.clearDrawnQuery()
                    x0 = mouse.x
                    y0 = mouse.y
                    rx = mouse.x
                    ry = mouse.y
                    rw = 0
                    rh = 0
                    hasRect = true
                }
                onPositionChanged: function(mouse) {
                    if (!pressed)
                        return
                    rx = Math.min(x0, mouse.x)
                    ry = Math.min(y0, mouse.y)
                    rw = Math.abs(mouse.x - x0)
                    rh = Math.abs(mouse.y - y0)
                }
                onReleased: function(mouse) {
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    if (pw <= 1 || ph <= 1) {
                        hasRect = false
                        shell.clearDrawnQuery()
                        return
                    }
                    if (rw < 4 || rh < 4) {
                        if (!insidePainted(mouse.x, mouse.y)) {
                            hasRect = false
                            shell.clearDrawnQuery()
                            return
                        }
                        var spec = shell.pointAt(
                            Math.max(0, Math.min(0.999999, (mouse.x - origin.x) / pw)),
                            Math.max(0, Math.min(0.999999, (mouse.y - origin.y) / ph))
                        )
                        if (!spec) {
                            hasRect = false
                            return
                        }
                        var parts = spec.split(",")
                        if (parts.length !== 4) {
                            hasRect = false
                            return
                        }
                        rx = origin.x + parseFloat(parts[0]) * pw
                        ry = origin.y + parseFloat(parts[1]) * ph
                        rw = Math.max(1, parseFloat(parts[2]) * pw)
                        rh = Math.max(1, parseFloat(parts[3]) * ph)
                        hasRect = true
                        return
                    }
                    var nx = (rx - origin.x) / pw
                    var ny = (ry - origin.y) / ph
                    var nw = rw / pw
                    var nh = rh / ph
                    shell.setRegion(
                        Math.max(0, Math.min(1, nx)),
                        Math.max(0, Math.min(1, ny)),
                        Math.max(0, Math.min(1, nw)),
                        Math.max(0, Math.min(1, nh))
                    )
                    shell.findSimilar()
                }
            }

            Rectangle {
                visible: regionDrag.hasRect && shell.focusKind !== "video"
                x: photo.x + regionDrag.rx
                y: photo.y + regionDrag.ry
                width: regionDrag.rw
                height: regionDrag.rh
                color: "#332DD4BF"
                border.color: "#2DD4BF"
                border.width: 1
            }

            VideoOutput {
                id: videoOut
                anchors.fill: parent
                anchors.margins: 48
                visible: false
            }

            MediaPlayer {
                id: player
                videoOutput: videoOut
                audioOutput: AudioOutput {}
                onMediaStatusChanged: {
                }
            }

            Text {
                objectName: "videoMissing"
                visible: false
                text: ""
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 15
            }

            Text {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 22
                text: "Back"
                color: backArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 14
                MouseArea {
                    id: backArea
                    anchors.fill: parent
                    anchors.margins: -8
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: shell.escape()
                }
            }

            Text {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 22
                anchors.bottomMargin: similarStrip.visible ? 108 : 22
                text: shell.focusName
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Column {
                objectName: "focusInspector"
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 22
                spacing: 8
                width: 220

                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 6
                    color: askArea.containsMouse ? "#12343A" : "#1C2430"
                    border.color: "#2DD4BF"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Ask about this photo"
                        color: "#5EEAD4"
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                    }
                    MouseArea {
                        id: askArea
                        objectName: "askPhoto"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: shell.askPhoto()
                    }
                }
                Text {
                    objectName: "resultText"
                    width: parent.width
                    text: shell.resultText
                    color: "#8AA0B2"
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                objectName: "similarNote"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 28
                visible: shell.similarState === "empty" || shell.similarState === "unavailable"
                text: shell.similarNote
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Flickable {
                id: similarStrip
                objectName: "similarStrip"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 22
                width: Math.min(Math.max(shell.similarCount * 80 - 8, 0), parent.width - 96)
                height: shell.similarState === "ready" && shell.similarCount > 0 ? 76 : 0
                contentWidth: stripRow.width
                contentHeight: 76
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                visible: height > 0

                Row {
                    id: stripRow
                    spacing: 8
                    Repeater {
                        model: similarModel
                        delegate: Item {
                            width: 72
                            height: 72
                            objectName: "similarThumb"

                            Rectangle {
                                anchors.fill: parent
                                color: "#1C2430"
                                radius: 2
                                border.width: thumbArea.containsMouse ? 1 : 0
                                border.color: "#2DD4BF"

                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    source: shell.thumbFor(mediaId)
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                }

                                MouseArea {
                                    id: thumbArea
                                    objectName: "similarThumbHit"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: shell.openFocus(mediaId)
                                }
                            }
                        }
                    }
                }
            }

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 18
                text: "‹"
                color: "#E7EEF5"
                font.pixelSize: 28
                opacity: prevArea.containsMouse ? 1 : 0.35
                MouseArea {
                    id: prevArea
                    anchors.fill: parent
                    anchors.margins: -12
                    hoverEnabled: true
                    onClicked: shell.focusPrev()
                }
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 18
                text: "›"
                color: "#E7EEF5"
                font.pixelSize: 28
                opacity: nextArea.containsMouse ? 1 : 0.35
                MouseArea {
                    id: nextArea
                    anchors.fill: parent
                    anchors.margins: -12
                    hoverEnabled: true
                    onClicked: shell.focusNext()
                }
            }

            Connections {
                target: shell
                function onFocusChanged() {
                    regionDrag.hasRect = false
                    player.stop()
                    if (shell.focusKind === "video" && shell.focusUrl !== "")
                        player.source = shell.focusUrl
                    else
                        player.source = ""
                }
            }
        }
    }
}
