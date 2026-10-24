import QtQuick
import QtQuick.Controls

Item {
    id: root
    objectName: "memoryCalendar"
    Accessible.name: "Memory calendar"
    clip: true

    property var shellApi: null
    property bool shellReady: false
    property var cells: []
    property string title: ""
    property string scopeKind: ""
    property string scopeLabel: ""
    property string revealedDay: ""
    property bool numbersOnly: false
    property int undatedCount: 0
    property color tokenBg: "#0b0c0e"
    property color tokenBg1: "#131417"
    property color tokenBg2: "#1b1d21"
    property color tokenBg3: "#2c303a"
    property color tokenAccent: "#4f8cff"
    property color tokenAccentDim: "#2b4d8f"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2d33"
    property int motion: 180

    signal dayClicked(string day)
    signal dayDoubleClicked(string day)
    signal thumbClicked(string mediaId, string day)
    signal rangeChosen(string startDay, string endDay)
    signal jumpRequested(string text)
    signal undatedClicked()
    signal prevMonth()
    signal nextMonth()
    signal goHome()

    property int focusIndex: -1
    property string hoverDay: ""
    property int hoverCount: 0
    property var hoverPreviewIds: []
    property real hoverX: 0
    property real hoverY: 0
    property bool popoverVisible: false
    property string dragAnchor: ""
    property string dragTip: ""
    property bool dragMoved: false
    property string pendingClick: ""
    property bool suppressClick: false

    readonly property int cellCount: cells && cells.length ? cells.length : 0
    readonly property int monthMediaCount: {
        var n = 0
        if (!cells) return 0
        for (var i = 0; i < cells.length; i++) {
            if (cells[i] && cells[i].inMonth)
                n += Number(cells[i].count || 0)
        }
        return n
    }
    readonly property real chromeHeight: 36 + 8 + 18 + 8
        + (undatedCount > 0 ? 22 : 0)
        + (cellCount > 0 && monthMediaCount === 0 ? 20 + 8 : 0)
    readonly property real cellW: Math.max(48, (width - 14) / 7)
    readonly property real cellH: numbersOnly
        ? Math.max(36, Math.min(64, (height - chromeHeight) / Math.max(1, Math.ceil(cellCount / 7))))
        : Math.max(72, Math.min(168, (height - chromeHeight) / Math.max(1, Math.ceil(cellCount / 7))))

    readonly property var weekdayLabels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    Timer {
        id: hoverTimer
        interval: 150
        repeat: false
        property string pendingDay: ""
        onTriggered: {
            if (!root.shellReady || pendingDay === "" || pendingDay !== root.hoverDay || !root.shellApi)
                return
            root.hoverPreviewIds = root.shellApi.timelinePreviewIds(root.hoverDay)
            root.popoverVisible = true
        }
    }

    Timer {
        id: clickTimer
        interval: 350
        repeat: false
        onTriggered: {
            if (root.pendingClick !== "")
                root.dayClicked(root.pendingClick)
            root.pendingClick = ""
        }
    }

    function cancelHover() {
        hoverTimer.stop()
        hoverTimer.pendingDay = ""
        popoverVisible = false
        hoverDay = ""
        hoverCount = 0
        hoverPreviewIds = []
    }

    function armHover(day, count, x, y) {
        hoverDay = day
        hoverCount = count
        hoverX = x
        hoverY = y
        popoverVisible = false
        hoverPreviewIds = []
        hoverTimer.pendingDay = day
        hoverTimer.restart()
    }

    function isSelected(day) {
        if (scopeKind === "day" && scopeLabel === day)
            return true
        if (scopeKind === "range" && scopeLabel.indexOf(":") > 0) {
            var parts = scopeLabel.split(":")
            return day >= parts[0] && day <= parts[1]
        }
        if (scopeKind === "month" && day.length >= 7 && day.slice(0, 7) === scopeLabel)
            return true
        return false
    }

    function marked(day) {
        if (dragMoved && dragAnchor !== "" && dragTip !== "") {
            var a = dragAnchor < dragTip ? dragAnchor : dragTip
            var b = dragAnchor < dragTip ? dragTip : dragAnchor
            if (day >= a && day <= b)
                return true
        }
        return isSelected(day)
    }

    function cancelDrag() {
        dragAnchor = ""
        dragTip = ""
        dragMoved = false
        pendingClick = ""
        clickTimer.stop()
    }

    function cellAt(x, y) {
        var local = dayGrid.mapFromItem(root, x, y)
        for (var i = 0; i < dayGrid.children.length; i++) {
            var child = dayGrid.children[i]
            if (!child || !child.dayKey)
                continue
            if (local.x >= child.x && local.x < child.x + child.width
                    && local.y >= child.y && local.y < child.y + child.height)
                return String(child.dayKey)
        }
        return ""
    }

    function beginDrag(day) {
        cancelHover()
        dragAnchor = day
        dragTip = day
        dragMoved = false
    }

    function moveDrag(x, y) {
        if (dragAnchor === "")
            return
        dragMoved = true
        var hit = cellAt(x, y)
        if (hit !== "")
            dragTip = hit
    }

    function endDrag(day) {
        if (suppressClick) {
            suppressClick = false
            cancelDrag()
            return
        }
        if (dragMoved && dragAnchor !== "" && dragTip !== "" && dragAnchor !== dragTip) {
            rangeChosen(dragAnchor, dragTip)
            cancelDrag()
            return
        }
        pendingClick = day
        clickTimer.restart()
        dragAnchor = ""
        dragTip = ""
        dragMoved = false
    }

    function moveFocus(delta) {
        if (cellCount <= 0)
            return
        if (focusIndex < 0) {
            focusIndex = 0
            return
        }
        var next = focusIndex + delta
        if (next < 0) {
            root.prevMonth()
            focusIndex = Math.max(0, cellCount + next)
            return
        }
        if (next >= cellCount) {
            root.nextMonth()
            focusIndex = Math.min(cellCount - 1, next - cellCount)
            return
        }
        focusIndex = next
    }

    Connections {
        target: shellReady ? shellApi : null
        function onEditorialChanged() { root.cancelHover() }
    }

    Column {
        anchors.fill: parent
        spacing: 8

        Row {
            width: parent.width
            spacing: 8
            height: 36

            Text {
                id: titleText
                objectName: "calendarTitle"
                text: root.title || ""
                color: tokenText
                font.family: "Noto Serif"
                font.pixelSize: 28
                font.weight: Font.DemiBold
                verticalAlignment: Text.AlignVCenter
                height: 36
            }

            TextField {
                id: jumpField
                objectName: "calendarJump"
                placeholderText: "Example: 2026-10-24"
                color: tokenText
                placeholderTextColor: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 12
                implicitWidth: 112
                implicitHeight: 28
                verticalAlignment: Text.AlignVCenter
                selectByMouse: true
                background: Rectangle {
                    radius: 6
                    color: tokenBg
                    border.color: jumpField.activeFocus ? tokenAccent : tokenBorder
                    border.width: 1
                }
                onAccepted: {
                    root.jumpRequested(text)
                    text = ""
                }
                Keys.onEscapePressed: {
                    text = ""
                    root.forceActiveFocus()
                }
            }

            Text {
                objectName: "calendarGoHome"
                text: "Today"
                color: homeArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 12
                height: 36
                verticalAlignment: Text.AlignVCenter
                Accessible.name: "Go to current archive month"
                MouseArea {
                    id: homeArea
                    anchors.fill: parent
                    anchors.margins: -4
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.goHome()
                }
            }

            Item { width: Math.max(0, parent.width - titleText.width - jumpField.width - 210); height: 1 }

            Text {
                objectName: "calendarPrev"
                text: "‹"
                color: prevArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 22
                width: 28
                height: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                Accessible.name: "Previous month"
                MouseArea {
                    id: prevArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.prevMonth()
                }
            }
            Text {
                objectName: "calendarNext"
                text: "›"
                color: nextArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 22
                width: 28
                height: 36
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                Accessible.name: "Next month"
                MouseArea {
                    id: nextArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.nextMonth()
                }
            }
        }

        Text {
            objectName: "calendarUndated"
            visible: root.undatedCount > 0
            width: parent.width
            height: visible ? 18 : 0
            text: "No date (" + root.undatedCount + ")"
            color: undatedArea.containsMouse ? tokenText : tokenMuted
            font.family: "Segoe UI"
            font.pixelSize: 12
            MouseArea {
                id: undatedArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.undatedClicked()
            }
        }

        Row {
            id: weekdayRow
            objectName: "calendarWeekdays"
            width: parent.width
            height: 18
            z: 5
            Repeater {
                model: root.weekdayLabels
                delegate: Text {
                    width: root.cellW
                    text: modelData
                    color: tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        Text {
            visible: root.cellCount > 0 && root.monthMediaCount === 0
            width: parent.width
            text: "No media in this month."
            color: tokenFaint
            font.family: "Segoe UI"
            font.pixelSize: 12
        }

        Grid {
            id: dayGrid
            objectName: "calendarDayGrid"
            columns: 7
            columnSpacing: 3
            rowSpacing: 3
            width: parent.width

            Repeater {
                model: root.cells
                delegate: DayCell {
                    id: dayCell
                    width: root.cellW
                    height: root.cellH
                    cell: modelData
                    showThumbs: !root.numbersOnly
                    marked: root.marked(dayKey)
                    revealed: root.revealedDay === dayKey && !marked
                    focused: root.focusIndex === index
                    tokenBg2: root.tokenBg2
                    tokenBg3: root.tokenBg3
                    tokenAccent: root.tokenAccent
                    tokenAccentDim: root.tokenAccentDim
                    tokenText: root.tokenText
                    tokenMuted: root.tokenMuted
                    tokenFaint: root.tokenFaint
                    tokenBorder: root.tokenBorder
                    onDayPressed: function(day) { root.beginDrag(day) }
                    onDayDragged: function(x, y) {
                        var mapped = dayCell.mapToItem(root, x, y)
                        root.moveDrag(mapped.x, mapped.y)
                    }
                    onDayReleased: function(day) { root.endDrag(day) }
                    onDayDouble: function(day) {
                        root.suppressClick = true
                        root.clickTimer.stop()
                        root.pendingClick = ""
                        root.dayDoubleClicked(day)
                    }
                    onThumbActivated: function(mediaId) { root.thumbClicked(mediaId, dayCell.dayKey) }
                    onEnteredDay: function(day, count) {
                        root.focusIndex = index
                        var mapped = dayCell.mapToItem(root, dayCell.width / 2, 0)
                        root.armHover(day, count, mapped.x, mapped.y)
                    }
                    onExitedDay: root.cancelHover()
                }
            }
        }
    }

    Rectangle {
        objectName: "calendarPopover"
        visible: popoverVisible && hoverDay !== ""
        width: 176
        height: previewRow.visible ? 96 : 48
        x: Math.max(4, Math.min(root.width - width - 4, hoverX - width / 2))
        y: Math.min(root.height - height - 4, Math.max(weekdayRow.y + weekdayRow.height + 4, hoverY + 6))
        radius: 8
        color: tokenBg1
        border.color: tokenBorder
        border.width: 1
        z: 20

        Column {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6
            Text {
                width: parent.width
                text: hoverDay + (hoverCount > 0
                      ? (" · " + (shellReady ? shellApi.formatCountExact(hoverCount) : hoverCount) + " photos")
                      : "")
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 12
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Row {
                id: previewRow
                spacing: 4
                visible: hoverPreviewIds && hoverPreviewIds.length > 0
                Repeater {
                    model: hoverPreviewIds
                    delegate: Image {
                        width: 48
                        height: 48
                        source: "image://archive/t/" + modelData
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }
                }
            }
        }
    }

    Keys.onPressed: (event) => {
        if (dragAnchor !== "") {
            if (event.key === Qt.Key_Escape) {
                cancelDrag()
                event.accepted = true
            }
            return
        }
        if (cellCount <= 0)
            return
        if (event.key === Qt.Key_Left) {
            moveFocus(-1); event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            moveFocus(1); event.accepted = true
        } else if (event.key === Qt.Key_Up) {
            moveFocus(-7); event.accepted = true
        } else if (event.key === Qt.Key_Down) {
            moveFocus(7); event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space) {
            if (focusIndex >= 0 && focusIndex < cellCount)
                dayClicked(String(cells[focusIndex].day))
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            cancelHover()
            if (shellReady && shellApi)
                shellApi.clearScope()
            event.accepted = true
        }
    }

    activeFocusOnTab: true
}
