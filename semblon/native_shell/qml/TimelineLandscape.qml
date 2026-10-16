import QtQuick

Item {
    id: root
    objectName: "timelineHero"
    height: 112
    Accessible.name: "Memory timeline"

    property var shellApi: null
    property bool shellReady: false
    property var yearModel: []
    property bool loading: false
    property string scopeKind: ""
    property string scopeLabel: ""
    property color tokenBg: "#0b0c0e"
    property color tokenBg2: "#1b1d21"
    property color tokenAccent: "#4f8cff"
    property color tokenAccentDim: "#2b4d8f"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2d33"
    property int motion: 180

    signal yearClicked(string label)
    signal monthClicked(string label)
    signal rangeSelected(string startDay, string endDay)

    property string focusYear: ""
    property string focusMonth: ""
    property string hoverLabel: ""
    property int hoverCount: 0
    property var hoverPreviewIds: []
    property real hoverX: 0
    property bool popoverVisible: false
    property string dragStartDay: ""
    property string dragEndDay: ""
    property bool dragging: false

    readonly property var densitySource: shellReady && shellApi ? shellApi.yearRows : []
    readonly property var densityMeta: shellReady && shellApi ? shellApi.timelineDensity : []
    readonly property int yearCount: densitySource && densitySource.length ? densitySource.length : 0

    function metaFor(label) {
        for (var i = 0; i < densityMeta.length; i++) {
            if (String(densityMeta[i].label) === String(label))
                return densityMeta[i]
        }
        return null
    }

    function monthsFor(label) {
        var meta = metaFor(label)
        return meta && meta.months ? meta.months : []
    }

    function monthStart(monthLabel) {
        return String(monthLabel) + "-01"
    }

    function monthEnd(monthLabel) {
        if (shellReady && shellApi)
            return shellApi.monthEndDay(monthLabel) || (String(monthLabel) + "-28")
        return String(monthLabel) + "-28"
    }

    function monthTick(monthLabel) {
        var m = Number(String(monthLabel || "").slice(5, 7))
        var names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return (m >= 1 && m <= 12) ? names[m] : ""
    }

    function cancelDrag() {
        dragging = false
        dragStartDay = ""
        dragEndDay = ""
    }

    Timer {
        id: hoverTimer
        interval: 150
        repeat: false
        property string pendingLabel: ""
        onTriggered: {
            if (!root.shellReady || pendingLabel === "" || pendingLabel !== root.hoverLabel || root.dragging || !root.shellApi)
                return
            root.hoverPreviewIds = root.shellApi.timelinePreviewIds(root.hoverLabel)
            root.popoverVisible = true
        }
    }

    function cancelHover() {
        hoverTimer.stop()
        hoverTimer.pendingLabel = ""
        popoverVisible = false
        hoverLabel = ""
        hoverCount = 0
        hoverPreviewIds = []
    }

    function armHover(label, count, x) {
        if (dragging)
            return
        hoverLabel = label
        hoverCount = Number(count || 0)
        hoverX = x
        popoverVisible = false
        hoverPreviewIds = []
        hoverTimer.pendingLabel = label
        hoverTimer.restart()
    }

    function isYearSelected(label) {
        return scopeKind === "year" && scopeLabel === label
    }

    function isMonthSelected(label) {
        return scopeKind === "month" && scopeLabel === label
    }

    Connections {
        target: shellReady ? shellApi : null
        function onEditorialChanged() {
            root.cancelHover()
            if (!root.dragging)
                root.cancelDrag()
        }
    }

    Rectangle {
        anchors.fill: parent
        color: tokenBg
        border.color: tokenBorder
        border.width: 1
        radius: 8

        Rectangle {
            objectName: "timelineLoadingTrack"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.margins: 16
            height: 6
            radius: 3
            color: tokenBg2
            visible: loading
            Accessible.name: "Loading timeline density"
            SequentialAnimation on opacity {
                running: loading
                loops: Animation.Infinite
                NumberAnimation { from: 0.35; to: 1; duration: 700 }
                NumberAnimation { from: 1; to: 0.35; duration: 700 }
            }
        }

        Row {
            id: yearRow
            objectName: "timelineYearRow"
            anchors.fill: parent
            anchors.margins: 10
            spacing: 4
            visible: !loading && yearCount > 0

            Repeater {
                id: yearRepeater
                objectName: "timelineYearRepeater"
                model: root.densitySource

                delegate: Item {
                    id: yearBlock
                    property var yearData: modelData
                    property string yearLabel: yearData ? String(yearData.label) : String(index)
                    property real share: yearCount > 0 ? Math.max(0.08, 1.0 / yearCount) : 0.5
                    property var monthList: []
                    width: Math.max(56, (yearRow.width - Math.max(0, root.yearCount - 1) * yearRow.spacing) * share)
                    height: 92
                    objectName: "timelineYear_" + yearLabel
                    Accessible.name: "Year " + yearLabel + ", " + String(yearData.count) + " photos"

                    Component.onCompleted: {
                        var meta = root.metaFor(yearLabel)
                        if (meta && meta.share)
                            share = Math.max(0.08, Number(meta.share))
                        monthList = root.monthsFor(yearLabel)
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: root.isYearSelected(yearLabel) || root.focusYear === yearLabel
                               ? Qt.rgba(tokenAccent.r, tokenAccent.g, tokenAccent.b, 0.14)
                               : "transparent"
                        border.color: root.focusYear === yearLabel ? tokenText : (root.isYearSelected(yearLabel) ? tokenAccent : tokenBorder)
                        border.width: root.focusYear === yearLabel || root.isYearSelected(yearLabel) ? 1 : 0

                        Column {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 3

                            Text {
                                text: yearLabel
                                color: root.isYearSelected(yearLabel) ? tokenAccent : tokenText
                                font.family: "Segoe UI Variable"
                                font.pixelSize: 12
                                font.weight: Font.DemiBold
                            }

                            Row {
                                id: monthBars
                                width: parent.width
                                height: 48
                                spacing: 2

                                Repeater {
                                    model: yearBlock.monthList
                                    delegate: Item {
                                        property var monthData: modelData
                                        property string monthLabel: monthData ? String(monthData.label) : String(index)
                                        property real mShare: Math.max(0.04, Number((monthData && monthData.share) || 0))
                                        property real fill: Math.max(0.08, Number((monthData && monthData.share) || 0))
                                        property bool activeMonth: root.isMonthSelected(monthLabel) || root.focusMonth === monthLabel
                                        width: Math.max(4, (monthBars.width - Math.max(0, yearBlock.monthList.length - 1) * monthBars.spacing) * mShare)
                                        height: parent.height
                                        objectName: "timelineMonth_" + monthLabel
                                        Accessible.name: (monthData && monthData.accessibleName) || monthLabel

                                        // Recessed track
                                        Rectangle {
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.bottom: tickLabel.top
                                            anchors.bottomMargin: 2
                                            height: 28
                                            radius: 3
                                            color: "#14151a"
                                            border.color: Qt.rgba(1, 1, 1, 0.04)
                                            border.width: 1

                                            Rectangle {
                                                anchors.bottom: parent.bottom
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                width: Math.max(2, parent.width - 2)
                                                height: Math.max(3, (parent.height - 2) * fill)
                                                radius: 2
                                                color: activeMonth ? tokenAccent : Qt.lighter(tokenAccent, 1.05)
                                                opacity: activeMonth ? 1 : 0.72
                                            }
                                        }

                                        Text {
                                            id: tickLabel
                                            anchors.bottom: parent.bottom
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            width: parent.width
                                            horizontalAlignment: Text.AlignHCenter
                                            text: width >= 18 ? root.monthTick(monthLabel) : root.monthTick(monthLabel).charAt(0)
                                            color: activeMonth ? tokenAccent : tokenFaint
                                            font.family: "Segoe UI"
                                            font.pixelSize: 8
                                            elide: Text.ElideRight
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            preventStealing: true
                                            onEntered: {
                                                root.focusMonth = monthLabel
                                                root.armHover(monthLabel, monthData ? monthData.count : 0, mapToItem(root, width / 2, 0).x)
                                            }
                                            onExited: {
                                                if (root.focusMonth === monthLabel)
                                                    root.focusMonth = ""
                                                root.cancelHover()
                                            }
                                            onPressed: {
                                                root.cancelHover()
                                                root.dragging = true
                                                root.dragStartDay = root.monthStart(monthLabel)
                                                root.dragEndDay = root.monthEnd(monthLabel)
                                            }
                                            onPositionChanged: {
                                                if (!root.dragging)
                                                    return
                                                root.dragEndDay = root.monthEnd(monthLabel)
                                            }
                                            onReleased: {
                                                if (!root.dragging) {
                                                    root.monthClicked(monthLabel)
                                                    return
                                                }
                                                var a = root.dragStartDay
                                                var b = root.monthEnd(monthLabel)
                                                if (a.slice(0, 7) === monthLabel)
                                                    root.monthClicked(monthLabel)
                                                else
                                                    root.rangeSelected(a, b)
                                                root.cancelDrag()
                                            }
                                            onCanceled: root.cancelDrag()
                                        }
                                    }
                                }
                            }

                            Text {
                                text: String(yearData.count) + " photos"
                                color: tokenFaint
                                font.family: "Segoe UI"
                                font.pixelSize: 10
                                elide: Text.ElideRight
                                width: parent.width
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            z: -1
                            hoverEnabled: true
                            onEntered: {
                                root.focusYear = yearLabel
                                root.armHover(yearLabel, yearData ? yearData.count : 0, mapToItem(root, width / 2, 0).x)
                            }
                            onExited: {
                                if (root.focusYear === yearLabel)
                                    root.focusYear = ""
                                root.cancelHover()
                            }
                            onClicked: root.yearClicked(yearLabel)
                        }
                    }
                }
            }
        }

        Text {
            anchors.centerIn: parent
            visible: !loading && yearCount === 0
            text: "No dated media yet"
            color: tokenFaint
            font.family: "Segoe UI"
            font.pixelSize: 12
        }

        Text {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 8
            visible: root.dragging && root.dragStartDay !== ""
            text: "Range: " + root.dragStartDay + " → …"
            color: tokenAccent
            font.family: "Segoe UI"
            font.pixelSize: 10
            z: 3
        }
    }

    Rectangle {
        objectName: "timelinePopover"
        visible: popoverVisible && hoverLabel !== ""
        width: 180
        height: previewRow.visible ? 100 : 52
        y: parent.height + 4
        x: Math.max(4, Math.min(root.width - width - 4, hoverX - width / 2))
        radius: 8
        color: tokenBg2
        border.color: tokenBorder
        border.width: 1
        z: 10

        Column {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: hoverLabel + (hoverCount > 0 ? (" · " + hoverCount + " photos") : "")
                      + "\nBar height shows share of that year."
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 11
            }
            Row {
                id: previewRow
                spacing: 4
                visible: hoverPreviewIds && hoverPreviewIds.length > 0
                Repeater {
                    model: hoverPreviewIds
                    delegate: Image {
                        width: 44
                        height: 44
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
        if (!shellReady || yearCount === 0)
            return
        if (event.key === Qt.Key_Escape) {
            if (dragging) {
                cancelDrag()
                cancelHover()
                event.accepted = true
                return
            }
            cancelHover()
            if (shellApi)
                shellApi.clearScope()
            event.accepted = true
            return
        }
        var idx = -1
        for (var i = 0; i < yearCount; i++) {
            if (String(densitySource[i].label) === focusYear || String(densitySource[i].label) === scopeLabel) {
                idx = i
                break
            }
        }
        if (event.key === Qt.Key_Left) {
            idx = Math.max(0, (idx < 0 ? 0 : idx) - 1)
            focusYear = String(densitySource[idx].label)
            focusMonth = ""
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            idx = Math.min(yearCount - 1, (idx < 0 ? 0 : idx) + 1)
            focusYear = String(densitySource[idx].label)
            focusMonth = ""
            event.accepted = true
        } else if (event.key === Qt.Key_Down) {
            var months = monthsFor(focusYear || (idx >= 0 ? String(densitySource[idx].label) : ""))
            if (months && months.length) {
                var mi = 0
                for (var m = 0; m < months.length; m++) {
                    if (String(months[m].label) === focusMonth) {
                        mi = Math.min(months.length - 1, m + 1)
                        break
                    }
                }
                focusMonth = String(months[mi].label)
                focusYear = focusMonth.slice(0, 4)
            }
            event.accepted = true
        } else if (event.key === Qt.Key_Up) {
            var monthsUp = monthsFor(focusYear || "")
            if (monthsUp && monthsUp.length && focusMonth !== "") {
                var ui = 0
                for (var u = 0; u < monthsUp.length; u++) {
                    if (String(monthsUp[u].label) === focusMonth) {
                        ui = Math.max(0, u - 1)
                        break
                    }
                }
                focusMonth = String(monthsUp[ui].label)
            } else if (focusYear !== "") {
                focusMonth = ""
            }
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (focusMonth !== "")
                monthClicked(focusMonth)
            else if (focusYear !== "")
                yearClicked(focusYear)
            event.accepted = true
        }
    }

    activeFocusOnTab: true
}
