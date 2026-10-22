import QtQuick

Item {
    id: cellRoot
    objectName: "calendarDay_" + dayKey
    Accessible.name: cell && cell.accessibleName ? cell.accessibleName : dayKey

    property var cell: null
    property bool marked: false
    property bool revealed: false
    property bool focused: false
    property bool showThumbs: true
    property color tokenBg2: "#1b1d21"
    property color tokenBg3: "#2c303a"
    property color tokenAccent: "#4f8cff"
    property color tokenAccentDim: "#2b4d8f"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2d33"

    signal dayPressed(string day)
    signal dayDragged(real x, real y)
    signal dayReleased(string day)
    signal dayDouble(string day)
    signal thumbActivated(string mediaId)
    signal enteredDay(string day, int count)
    signal exitedDay()

    readonly property string dayKey: cell ? String(cell.day) : ""
    readonly property bool inMonth: cell ? !!cell.inMonth : false
    readonly property int count: cell ? Number(cell.count || 0) : 0
    readonly property bool hasMedia: count > 0
    readonly property var preview: cell && cell.previewIds ? cell.previewIds : []
    readonly property int thumbCols: preview.length <= 1 ? 1 : (preview.length <= 4 ? 2 : 3)
    readonly property real tile: Math.max(8, Math.floor((width - 16 - (thumbCols - 1) * 2) / Math.max(1, thumbCols)))

    function swatch(mediaId) {
        var text = String(mediaId || "")
        var hash = 0
        for (var i = 0; i < text.length; i++)
            hash = (hash * 33 + text.charCodeAt(i)) >>> 0
        if ((hash % 3) === 0)
            return tokenBg3
        if ((hash % 3) === 1)
            return tokenAccentDim
        return tokenBg2
    }

    opacity: inMonth ? 1 : 0.55

    Rectangle {
        anchors.fill: parent
        anchors.margins: 1
        radius: 12
        clip: true
        color: cellRoot.inMonth ? tokenBg2 : Qt.darker(tokenBg2, 1.15)
        border.width: cellRoot.marked ? 2 : (cellRoot.revealed || cellRoot.focused || dayHover.containsMouse ? 1 : 0)
        border.color: cellRoot.marked || dayHover.containsMouse
                      ? tokenAccent
                      : (cellRoot.revealed ? tokenAccent : (cellRoot.focused ? tokenText : "transparent"))

        Canvas {
            id: emptyDayBorder
            anchors.fill: parent
            visible: cellRoot.inMonth && !cellRoot.hasMedia && !cellRoot.marked
            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.strokeStyle = dayHover.containsMouse ? String(tokenAccent) : "rgba(255,255,255,0.10)"
                ctx.lineWidth = 1
                ctx.setLineDash(dayHover.containsMouse ? [] : [3, 3])
                ctx.beginPath()
                var inset = 1.5
                var r = 10
                var x = inset
                var y = inset
                var w = width - inset * 2
                var h = height - inset * 2
                ctx.moveTo(x + r, y)
                ctx.lineTo(x + w - r, y)
                ctx.quadraticCurveTo(x + w, y, x + w, y + r)
                ctx.lineTo(x + w, y + h - r)
                ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h)
                ctx.lineTo(x + r, y + h)
                ctx.quadraticCurveTo(x, y + h, x, y + h - r)
                ctx.lineTo(x, y + r)
                ctx.quadraticCurveTo(x, y, x + r, y)
                ctx.stroke()
            }
            Connections {
                target: dayHover
                function onContainsMouseChanged() { emptyDayBorder.requestPaint() }
            }
        }

        Text {
            id: dayNum
            visible: cellRoot.inMonth
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 8
            anchors.topMargin: 6
            text: cell ? String(cell.dayNum) : ""
            color: cellRoot.hasMedia ? tokenText : tokenMuted
            font.family: "Segoe UI Variable"
            font.pixelSize: cellRoot.showThumbs ? 13 : 15
            font.weight: Font.DemiBold
        }

        Text {
            visible: cellRoot.inMonth && cell && !!cell.video
            anchors.left: dayNum.right
            anchors.leftMargin: 6
            anchors.verticalCenter: dayNum.verticalCenter
            text: "Video"
            color: tokenFaint
            font.family: "Segoe UI"
            font.pixelSize: 9
        }

        Rectangle {
            visible: cellRoot.inMonth && cell && !!cell.emphasized
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 8
            width: 6
            height: 6
            radius: 3
            color: tokenAccent
        }

        Item {
            z: 2
            visible: cellRoot.inMonth && cellRoot.showThumbs && cellRoot.preview.length > 0
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: dayNum.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 6
            anchors.topMargin: 4

            Repeater {
                model: cellRoot.preview
                delegate: Item {
                    x: (index % cellRoot.thumbCols) * (cellRoot.tile + 2)
                    y: Math.floor(index / cellRoot.thumbCols) * (cellRoot.tile + 2)
                    width: cellRoot.tile
                    height: cellRoot.tile

                    Rectangle {
                        anchors.fill: parent
                        radius: 4
                        color: cellRoot.swatch(modelData)
                        visible: thumbImage.status !== Image.Ready
                    }

                    Image {
                        id: thumbImage
                        anchors.fill: parent
                        source: "image://archive/t/" + modelData
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: 4
                        color: "transparent"
                        border.width: thumbHit.containsMouse ? 1 : 0
                        border.color: tokenAccent
                    }

                    MouseArea {
                        id: thumbHit
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: cellRoot.thumbActivated(String(modelData))
                    }
                }
            }
        }

        Text {
            visible: cellRoot.inMonth && cell && Number(cell.overflow || 0) > 0
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 6
            text: "+" + String(cell.overflow)
            color: tokenMuted
            font.family: "Segoe UI"
            font.pixelSize: 10
            font.weight: Font.DemiBold
        }

        MouseArea {
            id: dayHover
            z: 1
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            property real pressX: 0
            property real pressY: 0
            property bool dragged: false
            onEntered: cellRoot.enteredDay(cellRoot.dayKey, cellRoot.count)
            onExited: cellRoot.exitedDay()
            onPressed: function(mouse) {
                pressX = mouse.x
                pressY = mouse.y
                dragged = false
                cellRoot.dayPressed(cellRoot.dayKey)
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return
                if (Math.abs(mouse.x - pressX) + Math.abs(mouse.y - pressY) < 8 && !dragged)
                    return
                dragged = true
                cellRoot.dayDragged(mouse.x, mouse.y)
            }
            onReleased: {
                dragged = false
                cellRoot.dayReleased(cellRoot.dayKey)
            }
            onDoubleClicked: cellRoot.dayDouble(cellRoot.dayKey)
        }
    }
}
