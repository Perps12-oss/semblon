import QtQuick

Item {
    id: matrix
    objectName: "yearMatrix"
    Accessible.name: "Year calendar"

    property string title: ""
    property var months: []
    property color tokenBg2: "#1b1d21"
    property color tokenAccent: "#4f8cff"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2d33"
    property color tokenOk: "#30a46c"
    property color tokenWarn: "#f5a524"

    signal monthClicked(string label)
    signal rangeChosen(string startDay, string endDay)

    property string dragLabel: ""
    property string dragTip: ""
    property bool dragMoved: false

    function cardAt(x, y) {
        var local = monthGrid.mapFromItem(matrix, x, y)
        for (var i = 0; i < monthGrid.children.length; i++) {
            var card = monthGrid.children[i]
            if (!card || !card.monthLabel)
                continue
            if (local.x >= card.x && local.x < card.x + card.width
                    && local.y >= card.y && local.y < card.y + card.height)
                return String(card.monthLabel)
        }
        return ""
    }

    function monthStart(label) { return String(label) + "-01" }
    function monthEnd(label) {
        var parts = String(label || "").split("-")
        if (parts.length < 2)
            return String(label) + "-28"
        var year = Number(parts[0])
        var month = Number(parts[1])
        var last = new Date(year, month, 0).getDate()
        return String(label) + "-" + (last < 10 ? "0" : "") + last
    }

    Text {
        id: yearTitle
        text: matrix.title || ""
        color: tokenText
        font.family: "Segoe UI Variable"
        font.pixelSize: 24
        font.weight: Font.DemiBold
        anchors.left: parent.left
        anchors.top: parent.top
    }

    Flickable {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: yearTitle.bottom
        anchors.bottom: parent.bottom
        anchors.topMargin: 8
        contentWidth: width
        contentHeight: monthGrid.height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Grid {
            id: monthGrid
            width: parent.width
            columns: 3
            columnSpacing: 8
            rowSpacing: 8

            Repeater {
                model: matrix.months
                delegate: Rectangle {
                    id: monthCard
                    required property var modelData
                    required property int index
                    property var month: modelData
                    property string monthLabel: month ? String(month.label) : ""
                    width: Math.floor((monthGrid.width - 16) / 3)
                    height: 118
                    radius: 12
                    color: tokenBg2
                    border.width: monthHit.containsMouse || (matrix.dragMoved && (matrix.dragLabel === monthLabel || matrix.dragTip === monthLabel)) ? 1 : 0
                    border.color: tokenAccent
                    objectName: "yearMonth_" + monthLabel

                    Text {
                        id: monthName
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.margins: 8
                        text: month ? String(month.title) : ""
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    Grid {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: monthName.bottom
                        anchors.bottom: parent.bottom
                        anchors.margins: 8
                        anchors.topMargin: 4
                        columns: 7
                        columnSpacing: 1
                        rowSpacing: 1

                        Repeater {
                            model: month && month.cells ? month.cells : []
                            delegate: Text {
                                required property var modelData
                                property var dot: modelData
                                width: Math.floor((parent.width - 6) / 7)
                                height: 11
                                text: dot && dot.inMonth ? String(dot.dayNum) : ""
                                color: dot && dot.emphasized
                                       ? tokenAccent
                                       : (dot && Number(dot.heat) === 2
                                          ? tokenWarn
                                          : (dot && Number(dot.heat) === 1 ? tokenOk : tokenFaint))
                                font.family: "Segoe UI"
                                font.pixelSize: 8
                                font.weight: dot && Number(dot.count) > 0 ? Font.DemiBold : Font.Normal
                                horizontalAlignment: Text.AlignHCenter
                            }
                        }
                    }

                    MouseArea {
                        id: monthHit
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        property real pressX: 0
                        property real pressY: 0
                        onPressed: function(mouse) {
                            pressX = mouse.x
                            pressY = mouse.y
                            matrix.dragLabel = monthLabel
                            matrix.dragTip = monthLabel
                            matrix.dragMoved = false
                        }
                        onPositionChanged: function(mouse) {
                            if (!pressed)
                                return
                            if (Math.abs(mouse.x - pressX) + Math.abs(mouse.y - pressY) > 8)
                                matrix.dragMoved = true
                            var mapped = mapToItem(matrix, mouse.x, mouse.y)
                            var hit = matrix.cardAt(mapped.x, mapped.y)
                            if (hit !== "")
                                matrix.dragTip = hit
                        }
                        onReleased: {
                            if (matrix.dragMoved && matrix.dragLabel !== "" && matrix.dragTip !== ""
                                    && matrix.dragLabel !== matrix.dragTip) {
                                matrix.rangeChosen(
                                    matrix.monthStart(matrix.dragLabel),
                                    matrix.monthEnd(matrix.dragTip))
                            } else if (!matrix.dragMoved) {
                                matrix.monthClicked(monthLabel)
                            }
                            matrix.dragLabel = ""
                            matrix.dragTip = ""
                            matrix.dragMoved = false
                        }
                    }
                }
            }
        }
    }
}
