import QtQuick

Item {
    id: root
    objectName: "timelineHero"
    height: 96
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
    property string hoverLabel: ""
    property var hoverPreviewIds: []
    property real hoverX: 0
    property bool popoverVisible: false
    property string dragStartDay: ""
    property bool dragging: false

    // Flat yearRows for the Repeater; nested density used only after mount.
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

    Timer {
        id: hoverTimer
        interval: 150
        repeat: false
        onTriggered: {
            if (!root.shellReady || root.hoverLabel === "" || root.dragging || !root.shellApi)
                return
            root.hoverPreviewIds = root.shellApi.timelinePreviewIds(root.hoverLabel)
            root.popoverVisible = true
        }
    }

    function cancelHover() {
        hoverTimer.stop()
        popoverVisible = false
        hoverLabel = ""
        hoverPreviewIds = []
    }

    function armHover(label, x) {
        if (dragging)
            return
        hoverLabel = label
        hoverX = x
        popoverVisible = false
        hoverPreviewIds = []
        hoverTimer.restart()
    }

    function isYearSelected(label) {
        return scopeKind === "year" && scopeLabel === label
    }

    function isMonthSelected(label) {
        return scopeKind === "month" && scopeLabel === label
    }

    function monthToDay(monthLabel) {
        return monthLabel + "-01"
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
                    width: Math.max(48, (yearRow.width - Math.max(0, root.yearCount - 1) * yearRow.spacing) * share)
                    height: 76
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
                        color: root.isYearSelected(yearLabel) || root.focusYear === yearLabel ? tokenAccentDim : "transparent"
                        border.color: root.isYearSelected(yearLabel) ? tokenAccent : tokenBorder
                        border.width: root.focusYear === yearLabel || root.isYearSelected(yearLabel) ? 1 : 0

                        Column {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 4

                            Text {
                                text: yearLabel
                                color: root.isYearSelected(yearLabel) ? tokenAccent : tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }

                            Row {
                                id: monthBars
                                width: parent.width
                                height: 44
                                spacing: 2

                                Repeater {
                                    model: yearBlock.monthList
                                    delegate: Item {
                                        property var monthData: modelData
                                        property string monthLabel: monthData ? String(monthData.label) : String(index)
                                        property real mShare: Math.max(0.04, Number((monthData && monthData.share) || 0))
                                        width: Math.max(3, (monthBars.width - Math.max(0, yearBlock.monthList.length - 1) * monthBars.spacing) * mShare)
                                        height: parent.height
                                        objectName: "timelineMonth_" + monthLabel
                                        Accessible.name: (monthData && monthData.accessibleName) || monthLabel

                                        Rectangle {
                                            anchors.bottom: parent.bottom
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            width: Math.max(2, parent.width - 1)
                                            height: Math.max(4, parent.height * Math.max(0.12, Number((monthData && monthData.share) || 0)))
                                            radius: 2
                                            color: root.isMonthSelected(monthLabel) ? tokenAccent : tokenMuted
                                            opacity: root.isMonthSelected(monthLabel) ? 1 : 0.75
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            preventStealing: true
                                            onEntered: root.armHover(monthLabel, mapToItem(root, width / 2, 0).x)
                                            onExited: root.cancelHover()
                                            onPressed: {
                                                root.cancelHover()
                                                root.dragging = true
                                                root.dragStartDay = root.monthToDay(monthLabel)
                                            }
                                            onReleased: {
                                                var endDay = root.monthToDay(monthLabel)
                                                if (root.dragging && root.dragStartDay !== "" && root.dragStartDay !== endDay)
                                                    root.rangeSelected(root.dragStartDay, endDay)
                                                else
                                                    root.monthClicked(monthLabel)
                                                root.dragging = false
                                                root.dragStartDay = ""
                                            }
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
                                root.armHover(yearLabel, mapToItem(root, width / 2, 0).x)
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
    }

    Rectangle {
        objectName: "timelinePopover"
        visible: popoverVisible && hoverLabel !== ""
        width: 168
        height: previewRow.visible ? 88 : 48
        y: -height - 6
        x: Math.max(4, Math.min(root.width - width - 4, hoverX - width / 2))
        radius: 8
        color: tokenBg2
        border.color: tokenBorder
        border.width: 1
        z: 10
        opacity: visible ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Math.min(150, root.motion) } }

        Column {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 6
            Text {
                text: hoverLabel
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 12
                font.weight: Font.DemiBold
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
            event.accepted = true
        } else if (event.key === Qt.Key_Right) {
            idx = Math.min(yearCount - 1, (idx < 0 ? 0 : idx) + 1)
            focusYear = String(densitySource[idx].label)
            event.accepted = true
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
            if (focusYear !== "")
                yearClicked(focusYear)
            event.accepted = true
        } else if (event.key === Qt.Key_Escape) {
            if (shellReady && shellApi)
                shellApi.clearScope()
            event.accepted = true
        }
    }

    activeFocusOnTab: true
}
