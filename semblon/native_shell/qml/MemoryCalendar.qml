import QtQuick

Item {
    id: root
    objectName: "memoryCalendar"
    Accessible.name: "Memory calendar"

    property var shellApi: null
    property bool shellReady: false
    property var cells: []
    property string title: ""
    property string scopeKind: ""
    property string scopeLabel: ""
    property color tokenBg: "#0b0c0e"
    property color tokenBg1: "#131417"
    property color tokenBg2: "#1b1d21"
    property color tokenAccent: "#4f8cff"
    property color tokenAccentDim: "#2b4d8f"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2d33"
    property int motion: 180

    signal dayClicked(string day)
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
    property string hoverGeneration: ""

    readonly property int cellCount: cells && cells.length ? cells.length : 0
    readonly property real cellW: Math.max(48, (width - 14) / 7)
    readonly property real cellH: Math.max(56, Math.min(108, (height - 64) / Math.max(1, Math.ceil(cellCount / 7))))
    readonly property int monthMediaCount: {
        var n = 0
        if (!cells) return 0
        for (var i = 0; i < cells.length; i++) {
            if (cells[i] && cells[i].inMonth)
                n += Number(cells[i].count || 0)
        }
        return n
    }

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

    function countText(cell) {
        if (!cell || !cell.count)
            return ""
        if (cell.countLabel)
            return String(cell.countLabel)
        return shellReady ? shellApi.formatCount(Number(cell.count)) : String(cell.count)
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
            spacing: 10
            height: 32

            Text {
                id: titleText
                objectName: "calendarTitle"
                text: root.title || ""
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 22
                font.weight: Font.DemiBold
                verticalAlignment: Text.AlignVCenter
                height: 32
            }

            Text {
                objectName: "calendarGoHome"
                text: "Today"
                color: homeArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 12
                height: 32
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

            Item { width: Math.max(0, parent.width - titleText.width - 160); height: 1 }

            Text {
                objectName: "calendarPrev"
                text: "‹"
                color: prevArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 22
                width: 28
                height: 32
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
                height: 32
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
                delegate: Item {
                    id: dayCell
                    property var cell: modelData
                    property string dayKey: cell ? String(cell.day) : ""
                    property bool inMonth: cell ? !!cell.inMonth : false
                    property int count: cell ? Number(cell.count || 0) : 0
                    property string thumbId: cell ? String(cell.thumbId || "") : ""
                    property bool selected: root.isSelected(dayKey)
                    property bool focused: root.focusIndex === index
                    property bool isToday: cell ? !!cell.isToday : false
                    width: root.cellW
                    height: root.cellH
                    objectName: "calendarDay_" + dayKey
                    opacity: inMonth ? 1 : 0.38
                    Accessible.name: cell && cell.accessibleName ? cell.accessibleName : dayKey

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: 8
                        color: tokenBg2
                        border.width: selected || focused || isToday ? 2 : 1
                        border.color: selected ? tokenAccent : (focused ? tokenText : (isToday ? tokenMuted : tokenBorder))
                        clip: true

                        Image {
                            anchors.fill: parent
                            visible: thumbId !== ""
                            source: thumbId !== "" ? ("image://archive/t/" + thumbId) : ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            opacity: 0.88
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.top: parent.top
                            height: 26
                            visible: thumbId !== ""
                            color: "#99000000"
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.margins: 6
                            text: cell ? String(cell.dayNum) : ""
                            color: thumbId !== "" ? "#ffffff" : (inMonth ? tokenText : tokenFaint)
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            z: 2
                        }

                        Rectangle {
                            visible: count > 0
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 5
                            width: Math.max(22, countLabel.implicitWidth + 10)
                            height: 18
                            radius: 4
                            color: tokenAccentDim
                            z: 2
                            Text {
                                id: countLabel
                                anchors.centerIn: parent
                                text: root.countText(cell)
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 10
                                font.weight: Font.DemiBold
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onEntered: {
                                root.focusIndex = index
                                root.armHover(
                                    dayKey,
                                    count,
                                    mapToItem(root, width / 2, 0).x,
                                    mapToItem(root, height, 0).y
                                )
                            }
                            onExited: root.cancelHover()
                            onClicked: {
                                root.cancelHover()
                                root.focusIndex = index
                                root.dayClicked(dayKey)
                            }
                        }
                    }
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
        // Prefer below the cell so weekday headers stay clear.
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
