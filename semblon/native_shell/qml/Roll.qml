import QtQuick
import QtQuick.Shapes

// The Roll: the whole archive as one canvas. Zoom runs from far-out contact sheet to one picture.
Item {
    id: roll

    property real cellTarget: 168
    property real cellSize: cellTarget
    readonly property real minCell: 44
    readonly property real maxCell: 560
    readonly property int count: grid.count
    readonly property alias view: grid
    property int anchorIndex: 0
    property string heading: ""
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

    function zoomBy(factor) {
        anchorIndex = topIndex()
        cellTarget = Math.max(minCell, Math.min(maxCell, cellTarget * factor))
    }
    function zoomTo(size) {
        anchorIndex = topIndex()
        cellTarget = Math.max(minCell, Math.min(maxCell, size))
    }
    function topIndex() {
        var idx = grid.indexAt(grid.cellWidth / 2, grid.contentY + grid.topMargin + 8)
        return idx < 0 ? 0 : idx
    }
    function jumpToIndex(index) {
        var n = Math.max(0, Math.min(grid.count - 1, index))
        grid.positionViewAtIndex(n, GridView.Beginning)
        grid.currentIndex = n
        refreshHeading()
    }
    function jumpToFraction(f) {
        jumpToIndex(Math.round(f * Math.max(0, grid.count - 1)))
    }
    function frameTag(day) {
        if (!day || day.length < 10 || !/^\d{4}-\d{2}-\d{2}$/.test(day))
            return ""
        var abbr = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        var days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        var y = parseInt(day.substring(0, 4)), m = parseInt(day.substring(5, 7)), d = parseInt(day.substring(8, 10))
        if (isNaN(m) || m < 1 || m > 12)
            return ""
        return days[new Date(y, m - 1, d).getDay()] + " " + d + " " + abbr[m - 1]
    }
    function formatDay(day) {
        if (!day || day.length < 4)
            return ""
        var months = ["January", "February", "March", "April", "May", "June", "July",
                      "August", "September", "October", "November", "December"]
        var year = day.substring(0, 4)
        if (!/^\d{4}$/.test(year))
            return "Undated"
        if (farOut)
            return year
        var m = parseInt(day.substring(5, 7))
        if (isNaN(m) || m < 1 || m > 12)
            return year
        if (cellSize < 220 || day.length < 10)
            return months[m - 1] + " " + year
        return parseInt(day.substring(8, 10)) + " " + months[m - 1] + " " + year
    }
    function refreshHeading() {
        if (grid.count <= 0) {
            heading = ""
            return
        }
        heading = formatDay(shell.dayAt(topIndex()))
    }
    function openCurrent() {
        if (grid.currentItem)
            grid.currentItem.activate()
    }

    onCellSizeChanged: {
        if (grid.count > 0)
            grid.positionViewAtIndex(Math.min(anchorIndex, grid.count - 1), GridView.Beginning)
        refreshHeading()
    }

    GridView {
        id: grid
        objectName: "rollGrid"
        anchors.fill: parent
        model: archiveModel
        clip: true
        cacheBuffer: 1200
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        activeFocusOnTab: true
        readonly property int columns: Math.max(1, Math.floor(width / roll.cellSize))
        cellWidth: width / columns
        cellHeight: cellWidth
        topMargin: band.height + 6
        bottomMargin: roll.bottomInset
        flickDeceleration: 3200
        maximumFlickVelocity: 9000

        Accessible.role: Accessible.List
        Accessible.name: "Your photos, newest first. Use the arrow keys to move and Enter to open."

        onContentYChanged: { roll.refreshHeading(); settle.restart() }
        onCountChanged: roll.refreshHeading()
        Keys.onReturnPressed: roll.openCurrent()
        Keys.onEnterPressed: roll.openCurrent()
        Keys.onPressed: function (event) {
            if (event.key === Qt.Key_Plus || event.key === Qt.Key_Equal) {
                roll.zoomBy(1.25); event.accepted = true
            } else if (event.key === Qt.Key_Minus) {
                roll.zoomBy(0.8); event.accepted = true
            }
        }

        delegate: Item {
            id: cell
            width: grid.cellWidth
            height: grid.cellHeight
            readonly property bool current: GridView.isCurrentItem
            readonly property string dayKey: day || ""
            readonly property bool startsDay: roll.dayBreaks && dayKey !== ""
                                              && (index === 0 || shell.dayAt(index - 1) !== dayKey)
            function activate() {
                var p = cell.mapToItem(roll, 0, 0)
                roll.opened(mediaId, Qt.rect(p.x, p.y, width, height))
            }

            Rectangle {
                id: frame
                anchors.fill: parent
                anchors.margins: roll.farOut ? 0.5 : 3
                color: Theme.surface
                clip: true

                Image {
                    id: pic
                    anchors.fill: parent
                    source: mediaId === "" ? ""
                          : (roll.cellSize < 110 ? "image://archive/s/" : "image://archive/t/") + mediaId
                    fillMode: Image.PreserveAspectCrop
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
                        text: index + 1
                        font.family: Theme.display
                        font.pixelSize: Theme.body
                        font.weight: Font.DemiBold
                        color: Theme.onAmber
                    }
                }
                // Day break: a thin amber rule and a frame-number tag on the first picture of a day.
                Rectangle {
                    visible: cell.startsDay
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: 2
                    color: Theme.amber
                }
                Rectangle {
                    visible: cell.startsDay
                    anchors.left: parent.left
                    anchors.bottom: parent.bottom
                    anchors.leftMargin: 2
                    color: Theme.scrim
                    width: tag.implicitWidth + 12
                    height: tag.implicitHeight + 6
                    Text {
                        id: tag
                        anchors.centerIn: parent
                        text: roll.frameTag(cell.dayKey)
                        font.family: Theme.ui
                        font.pixelSize: 10
                        font.weight: Font.Bold
                        font.letterSpacing: 1.4
                        color: Theme.text
                    }
                }
                Rectangle {
                    anchors.fill: parent
                    color: "transparent"
                    border.width: cell.current && grid.activeFocus ? 3 : 0
                    border.color: Theme.amber
                }
                scale: hover.containsMouse ? 1.025 : 1
                Behavior on scale { NumberAnimation { duration: Theme.fast } }
            }
            MouseArea {
                id: hover
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    grid.currentIndex = index
                    grid.forceActiveFocus()
                    cell.activate()
                }
            }
            Accessible.role: Accessible.Button
            Accessible.name: (name || "Photo") + (day ? ", " + day : "")
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

    // The date you are looking at gets its own band. Pictures slide under a soft fade.
    Item {
        id: band
        objectName: "rollHeader"
        visible: grid.count > 0
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: place.implicitHeight + Theme.pad * 2.2
        z: 2
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: parent.height + 30
            gradient: Gradient {
                GradientStop { position: 0; color: Theme.bg }
                GradientStop { position: 0.72; color: Theme.bg }
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
                font.pixelSize: Theme.hero
                minimumPixelSize: 28
                fontSizeMode: Text.Fit
                font.weight: Font.Light
                color: Theme.text
            }
            Text {
                objectName: "rollCount"
                text: roll.matchMode
                      ? grid.count + (grid.count === 1 ? " match, best first" : " matches, best first")
                      : (grid.count + (grid.count === 1 ? " photo" : " photos"))
                font.family: Theme.ui
                font.pixelSize: Theme.small
                color: Theme.muted
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
        visible: shell.jobActive && grid.count < 12
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
