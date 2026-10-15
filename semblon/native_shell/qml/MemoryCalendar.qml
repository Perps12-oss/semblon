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

    property int focusIndex: -1
    property string hoverDay: ""
    property int hoverCount: 0
    property var hoverPreviewIds: []
    property real hoverX: 0
    property real hoverY: 0
    property bool popoverVisible: false

    readonly property int cellCount: cells && cells.length ? cells.length : 0
    readonly property real cellW: Math.max(44, (width - 12) / 7)
    readonly property real cellH: Math.max(52, Math.min(110, (height - 56) / Math.max(1, Math.ceil(cellCount / 7))))

    readonly property var weekdayLabels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    Timer {
        id: hoverTimer
        interval: 150
        repeat: false
        onTriggered: {
            if (!root.shellReady || root.hoverDay === "" || !root.shellApi)
                return
            root.hoverPreviewIds = root.shellApi.timelinePreviewIds(root.hoverDay)
            root.popoverVisible = true
        }
    }

    function cancelHover() {
        hoverTimer.stop()
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
        hoverTimer.restart()
    }

    function isSelected(day) {
        return scopeKind === "day" && scopeLabel === day
    }

    function moveFocus(delta) {
        if (cellCount <= 0)
            return
        if (focusIndex < 0)
            focusIndex = 0
        else
            focusIndex = Math.max(0, Math.min(cellCount - 1, focusIndex + delta))
    }

    Column {
        anchors.fill: parent
        spacing: 8

        Row {
            width: parent.width
            spacing: 12

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

            Item { width: Math.max(0, parent.width - titleText.width - 100); height: 1 }

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
            width: parent.width
            height: 18
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

        Grid {
            id: dayGrid
            objectName: "calendarDayGrid"
            columns: 7
            columnSpacing: 2
            rowSpacing: 2
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
                    width: root.cellW
                    height: root.cellH
                    objectName: "calendarDay_" + dayKey
                    opacity: inMonth ? 1 : 0.42
                    Accessible.name: cell && cell.accessibleName ? cell.accessibleName : dayKey

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: 8
                        color: tokenBg2
                        border.width: selected || focused ? 2 : 1
                        border.color: selected ? tokenAccent : (focused ? tokenText : tokenBorder)
                        clip: true

                        Image {
                            anchors.fill: parent
                            visible: thumbId !== ""
                            source: thumbId !== "" ? ("image://archive/t/" + thumbId) : ""
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                            opacity: 0.92
                        }

                        Rectangle {
                            anchors.fill: parent
                            visible: thumbId !== ""
                            gradient: Gradient {
                                GradientStop { position: 0.0; color: "#66000000" }
                                GradientStop { position: 0.45; color: "#00000000" }
                                GradientStop { position: 1.0; color: "#55000000" }
                            }
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
                            style: Text.Outline
                            styleColor: thumbId !== "" ? "#66000000" : "transparent"
                        }

                        Rectangle {
                            visible: count > 0
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 5
                            width: countLabel.implicitWidth + 10
                            height: 18
                            radius: 9
                            color: tokenAccentDim
                            Text {
                                id: countLabel
                                anchors.centerIn: parent
                                text: count > 1 ? ("+" + String(count)) : "1"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 10
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
                                    mapToItem(root, 0, 0).y
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
        y: Math.max(4, hoverY - height - 8)
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
                text: hoverDay + (hoverCount > 0 ? (" · " + hoverCount) : "")
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
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
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
