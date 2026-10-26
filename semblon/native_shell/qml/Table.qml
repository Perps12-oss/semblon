import QtQuick
import QtQuick.Window

Window {
    id: win
    objectName: "table"
    width: 1280
    height: 800
    minimumWidth: 640
    minimumHeight: 480
    visible: true
    title: "Semblon"
    color: Theme.bg

    Binding { target: Theme; property: "daylight"; value: shell.lightPalette }
    Binding { target: Theme; property: "reducedMotion"; value: shell.reducedMotion }

    property bool settingsOpen: false
    property bool jobMini: false
    Connections {
        target: shell
        function onJobChanged() { if (!shell.jobActive) win.jobMini = false }
    }

    function jumpToDate(prefix) {
        var lo = 0, hi = rollView.count - 1, found = -1
        // Newest first: find the first photo on or before the end of the requested period.
        while (lo <= hi) {
            var mid = (lo + hi) >> 1
            var d = shell.dayAt(mid)
            if (d.substring(0, prefix.length) > prefix) lo = mid + 1
            else { found = mid; hi = mid - 1 }
        }
        if (found >= 0) rollView.jumpToIndex(found)
    }
    function run(id) {
        if (id === "add") shell.addFolder()
        else if (id === "people") shell.openPeople()
        else if (id === "moment") table.focusEntry("moment")
        else if (id === "detail") table.focusEntry("detail")
        else if (id === "tidy") shell.openTidy()
        else if (id === "settings") settingsOpen = true
        else if (id === "zoomin") rollView.zoomBy(1.4)
        else if (id === "zoomout") rollView.zoomBy(0.7)
        else if (id === "dark") shell.setAtmosphere("mica_dark")
        else if (id === "light") shell.setAtmosphere("light")
        else if (id === "v-detail") { viewer.loupeOn = true }
        else if (id === "v-like") shell.findSimilarWhole()
        else if (id === "v-area") shell.findSimilar()
        else if (id === "v-faces") shell.findSimilarFaces()
        else if (id === "v-copies") shell.scanDuplicates()
        else if (id === "v-describe") shell.nameSelection()
        else if (id === "v-ask") shell.askPhoto()
        else if (id === "v-more") shell.setSearchQuality("max")
        else if (id === "v-closer") shell.setSearchQuality("fast")
    }

    Roll {
        id: rollView
        objectName: "roll"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: scrub.left
        bottomInset: table.visible ? table.implicitHeight + 28 : 28
        onOpened: function (id) { shell.openFocus(id) }
        focus: true
    }
    Scrubber {
        id: scrub
        objectName: "scrubber"
        roll: rollView
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        visible: rollView.count > 0
        width: visible ? Theme.edge : 0
        // Pictures and people use the full width; the edge comes back with the roll.
        opacity: viewer.active || people.active || tidy.active ? 0 : 1
        enabled: opacity > 0.5
        Behavior on opacity { NumberAnimation { duration: Theme.fast } }
    }
    LightTable {
        id: table
        objectName: "lightTable"
        anchors.left: parent.left
        anchors.right: scrub.left
        anchors.bottom: parent.bottom
        visible: !viewer.active && !people.active && !tidy.active
        receded: rollView.scrolling
        onPeopleRequested: shell.openPeople()
        onSettingsRequested: win.settingsOpen = true
        onPaletteRequested: palette.open = true
        onDateRequested: function (p) { win.jumpToDate(p) }
    }

    // Top-right: the two things you do before anything else.
    Row {
        anchors.right: scrub.left
        anchors.top: parent.top
        anchors.margins: Theme.pad
        spacing: Theme.gap
        visible: !viewer.active && !people.active && !tidy.active
        Tool {
            objectName: "addFolder"
            label: "Add a folder"
            visible: !shell.empty
            onActivated: shell.addFolder()
        }
        Tool { label: "Settings"; onActivated: win.settingsOpen = true }
    }

    // Progress while a folder is read. Pictures appear behind it as they are ready.
    Rectangle {
        id: progress
        objectName: "jobBand"
        visible: shell.jobActive && !win.jobMini
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: 70
        width: Math.min(parent.width - 120, 520)
        height: pcol.implicitHeight + Theme.pad * 1.6
        radius: Theme.radius * 1.6
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        Accessible.role: Accessible.ProgressBar
        Accessible.name: shell.jobLabel
        Column {
            id: pcol
            anchors.centerIn: parent
            width: parent.width - Theme.pad * 2
            spacing: 6
            Text { text: shell.jobLabel; font.family: Theme.display; font.pixelSize: Theme.lead; color: Theme.text }
            Rectangle {
                width: parent.width; height: 6; radius: 3; color: Theme.line
                Rectangle {
                    height: parent.height; radius: 3; color: Theme.amber
                    width: parent.width * (shell.jobTotal > 0 ? shell.jobFraction : 0.08)
                    Behavior on width { NumberAnimation { duration: Theme.medium } }
                }
            }
            Text {
                objectName: "scanTiming"
                text: (shell.jobTotal > 0 ? shell.jobCurrent + " of " + shell.jobTotal + " photos. " : "") + shell.jobTiming
                font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted
            }
            Row {
                spacing: Theme.gap
                Tool { objectName: "pauseJob"; label: shell.jobState === "paused" ? "Keep going" : "Pause"; onActivated: shell.jobState === "paused" ? shell.resumeJob() : shell.pauseJob() }
                Tool { objectName: "cancelJob"; label: "Stop"; onActivated: shell.cancelJob() }
                Tool { objectName: "shrinkJob"; label: "Minimise"; quiet: true; onActivated: win.jobMini = true }
            }
        }
    }

    // The same progress, shrunk to a small pill in the corner so it never blocks the pictures.
    Rectangle {
        id: pill
        objectName: "jobPill"
        visible: shell.jobActive && win.jobMini
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: Theme.pad
        width: pillRow.implicitWidth + Theme.pad * 1.6
        height: 40
        radius: Theme.pill
        color: Theme.surface
        border.width: pillArea.activeFocus ? 2 : 1
        border.color: pillArea.activeFocus ? Theme.amber : Theme.line
        Accessible.role: Accessible.Button
        Accessible.name: shell.jobLabel + ". Press to show details."
        Accessible.onPressAction: win.jobMini = false
        Row {
            id: pillRow
            anchors.centerIn: parent
            spacing: 10
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 64; height: 5; radius: 2.5; color: Theme.line
                Rectangle {
                    height: parent.height; radius: 2.5; color: Theme.amber
                    width: parent.width * (shell.jobTotal > 0 ? shell.jobFraction : 0.08)
                }
            }
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: shell.jobState === "paused" ? "Paused" : (shell.jobTotal > 0 ? "Getting photos ready " + Math.round(shell.jobFraction * 100) + "%" : "Looking for photos")
                font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.text
            }
            Text { anchors.verticalCenter: parent.verticalCenter; text: "Show"; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.amber }
        }
        MouseArea {
            id: pillArea
            anchors.fill: parent
            activeFocusOnTab: true
            cursorShape: Qt.PointingHandCursor
            onClicked: win.jobMini = false
            Keys.onReturnPressed: win.jobMini = false
            Keys.onSpacePressed: win.jobMini = false
        }
    }

    // Something went wrong or needs saying: plain words, and the originals are safe.
    Rectangle {
        id: note
        objectName: "notice"
        property string hidden: ""
        readonly property bool problem: shell.surfaceState === "error" || shell.surfaceState === "unavailable"
        visible: shell.noticeText !== "" && shell.noticeText !== hidden && !viewer.active
        onVisibleChanged: if (visible) fade.restart()
        Timer { id: fade; interval: note.problem ? 15000 : 8000; onTriggered: note.hidden = shell.noticeText }
        Connections {
            target: shell
            function onResultChanged() { note.hidden = ""; fade.restart() }
        }
        Keys.onEscapePressed: note.hidden = shell.noticeText
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: shell.jobActive && !win.jobMini ? 190 : 70
        width: Math.min(parent.width - 120, 560)
        height: ncol.implicitHeight + Theme.pad * 1.4
        radius: Theme.radius * 1.4
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        Rectangle { width: 4; height: parent.height - 2 * parent.radius; anchors.left: parent.left; anchors.leftMargin: 1; anchors.verticalCenter: parent.verticalCenter; color: Theme.amber; radius: 2 }
        Accessible.role: Accessible.AlertMessage
        Accessible.name: shell.noticeText
        Row {
            id: ncol
            anchors.centerIn: parent
            width: parent.width - Theme.pad * 2
            spacing: Theme.gap
            Text {
                width: parent.width - closeNote.width - Theme.gap; wrapMode: Text.WordWrap
                text: shell.noticeText + (note.problem && shell.noticeText.indexOf("original photos") < 0 ? " Your original photos were not changed." : "")
                font.family: Theme.ui; font.pixelSize: Theme.body; color: Theme.text
            }
            Tool { id: closeNote; objectName: "closeNotice"; label: "Dismiss"; quiet: true; onActivated: note.hidden = shell.noticeText }
        }
    }

    Viewer { id: viewer; anchors.fill: parent; onClosed: rollView.forceActiveFocus() }
    People { id: people; anchors.fill: parent; onClosed: rollView.forceActiveFocus() }

    Sheet {
        id: settings
        heading: "Settings"
        open: win.settingsOpen
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 560)
        height: Math.min(parent.height - 60, 680)
        onDismissed: { win.settingsOpen = false; rollView.forceActiveFocus() }
        SettingsBody { anchors.fill: parent }
    }

    Sheet {
        id: activity
        objectName: "activitySheet"
        heading: "Recent activity"
        open: shell.activityOpen
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 520)
        height: Math.min(parent.height - 80, 460)
        onDismissed: { shell.closeActivity(); rollView.forceActiveFocus() }
        ListView {
            anchors.fill: parent
            clip: true
            spacing: 4
            model: shell.activityRows
            section.property: "section"
            section.delegate: Text { text: section; font.family: Theme.ui; font.pixelSize: Theme.tiny; font.weight: Font.DemiBold; color: Theme.faint; topPadding: 8 }
            delegate: Text { width: ListView.view.width; wrapMode: Text.WordWrap; text: modelData.text; font.family: Theme.ui; font.pixelSize: Theme.body; color: Theme.text }
        }
    }

    Tidy { id: tidy; anchors.fill: parent; onClosed: rollView.forceActiveFocus() }

    Confirm { id: confirmSheet; anchors.fill: parent; z: 50 }

    CommandPalette {
        id: palette
        anchors.fill: parent
        // With nothing added yet, only the actions that work right now are offered.
        actions: viewer.active ? [
            { id: "v-detail", label: "Find this part again" },
            { id: "v-like", label: "Find photos like this one" },
            { id: "v-area", label: "Find the picked area elsewhere" },
            { id: "v-faces", label: "Find faces like these" },
            { id: "v-copies", label: "Find copies of this photo" },
            { id: "v-describe", label: "Describe this area" },
            { id: "v-ask", label: "Ask about this photo" },
            { id: "v-more", label: "Show more matches" },
            { id: "v-closer", label: "Show fewer, closer matches" },
            { id: "settings", label: "Settings" }
        ] : shell.empty ? [
            { id: "add", label: "Add a folder" },
            { id: "dark", label: "Use Darkroom look" },
            { id: "light", label: "Use Daylight look" },
            { id: "settings", label: "Settings" }
        ] : [
            { id: "add", label: "Add a folder" },
            { id: "moment", label: "Find by date" },
            { id: "people", label: "Find a person" },
            { id: "detail", label: "Find by description" },
            { id: "tidy", label: "Tidy up copies" },
            { id: "zoomin", label: "Bigger pictures" },
            { id: "zoomout", label: "Smaller pictures" },
            { id: "dark", label: "Use Darkroom look" },
            { id: "light", label: "Use Daylight look" },
            { id: "settings", label: "Settings" }
        ]
        onChosen: function (id) { win.run(id) }
    }

    Shortcut { sequence: "Ctrl+K"; onActivated: palette.open = !palette.open }
    Shortcut { sequence: "Ctrl+F"; enabled: !shell.empty; onActivated: table.focusEntry("moment") }
    Shortcut { sequence: "Ctrl+O"; onActivated: shell.addFolder() }
    Shortcut { sequence: "Ctrl+="; onActivated: rollView.zoomBy(1.25) }
    Shortcut { sequence: "Ctrl+-"; onActivated: rollView.zoomBy(0.8) }
    Shortcut { sequence: "Ctrl+0"; onActivated: rollView.zoomTo(168) }
}
