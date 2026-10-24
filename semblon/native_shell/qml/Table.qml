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

    function jumpToDate(prefix) {
        var lo = 0, hi = archiveModel.count - 1, found = -1
        // Newest first: find the first photo on or before the end of the requested period.
        while (lo <= hi) {
            var mid = (lo + hi) >> 1
            var d = shell.dayAt(mid)
            if (d.substring(0, prefix.length) > prefix) lo = mid + 1
            else { found = mid; hi = mid - 1 }
        }
        if (found >= 0) roll.jumpToIndex(found)
    }
    function run(id) {
        if (id === "add") shell.addFolder()
        else if (id === "people") shell.openPeople()
        else if (id === "moment") table.focusEntry("moment")
        else if (id === "detail") table.focusEntry("detail")
        else if (id === "tidy") { table.mode = "tidy"; shell.scanDuplicates() }
        else if (id === "settings") settingsOpen = true
        else if (id === "zoomin") roll.zoomBy(1.4)
        else if (id === "zoomout") roll.zoomBy(0.7)
        else if (id === "dark") shell.setAtmosphere("mica_dark")
        else if (id === "light") shell.setAtmosphere("light")
    }

    Roll {
        id: roll
        objectName: "roll"
        anchors.fill: parent
        onOpened: function (id) { shell.openFocus(id) }
        focus: true
    }
    Scrubber {
        id: scrub
        roll: roll
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        visible: archiveModel.count > 0
    }
    LightTable {
        id: table
        objectName: "lightTable"
        anchors.left: parent.left
        anchors.right: scrub.left
        anchors.bottom: parent.bottom
        visible: !viewer.active && !people.active
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
        visible: !viewer.active && !people.active
        Tool {
            objectName: "addFolder"
            label: "Add a folder"
            primary: shell.empty
            onActivated: shell.addFolder()
        }
        Tool { label: "Settings"; onActivated: win.settingsOpen = true }
    }

    // Progress while a folder is read. Pictures appear behind it as they are ready.
    Rectangle {
        id: progress
        objectName: "jobBand"
        visible: shell.jobActive
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
                text: (shell.jobTotal > 0 ? shell.jobCurrent + " of " + shell.jobTotal + " photos. " : "") + shell.jobTiming
                font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted
            }
            Row {
                spacing: Theme.gap
                Tool { objectName: "pauseJob"; label: shell.jobState === "paused" ? "Keep going" : "Pause"; onActivated: shell.jobState === "paused" ? shell.resumeJob() : shell.pauseJob() }
                Tool { objectName: "cancelJob"; label: "Stop"; onActivated: shell.cancelJob() }
            }
        }
    }

    // Something went wrong or needs saying: plain words, and the originals are safe.
    Rectangle {
        id: note
        objectName: "notice"
        visible: shell.noticeText !== "" && !viewer.active
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top
        anchors.topMargin: shell.jobActive ? 190 : 70
        width: Math.min(parent.width - 120, 560)
        height: ncol.implicitHeight + Theme.pad * 1.4
        radius: Theme.radius * 1.4
        color: Theme.amberSoft
        border.width: 1
        border.color: Theme.amber
        Accessible.role: Accessible.AlertMessage
        Accessible.name: shell.noticeText
        Column {
            id: ncol
            anchors.centerIn: parent
            width: parent.width - Theme.pad * 2
            Text {
                width: parent.width; wrapMode: Text.WordWrap
                text: shell.noticeText + " Your original photos were not changed."
                font.family: Theme.ui; font.pixelSize: Theme.body; color: Theme.text
            }
        }
    }

    Viewer { id: viewer; anchors.fill: parent; onClosed: roll.forceActiveFocus() }
    People { id: people; anchors.fill: parent; onClosed: roll.forceActiveFocus() }

    Sheet {
        id: settings
        heading: "Settings"
        open: win.settingsOpen
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 560)
        height: Math.min(parent.height - 60, 680)
        onDismissed: { win.settingsOpen = false; roll.forceActiveFocus() }
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
        onDismissed: { shell.closeActivity(); roll.forceActiveFocus() }
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

    CommandPalette {
        id: palette
        anchors.fill: parent
        actions: [
            { id: "add", label: "Add a folder" },
            { id: "moment", label: "Find a moment" },
            { id: "people", label: "Find a person" },
            { id: "detail", label: "Find a detail" },
            { id: "tidy", label: "Tidy up" },
            { id: "zoomin", label: "Bigger pictures" },
            { id: "zoomout", label: "Smaller pictures" },
            { id: "dark", label: "Use Darkroom look" },
            { id: "light", label: "Use Daylight look" },
            { id: "settings", label: "Settings" }
        ]
        onChosen: function (id) { win.run(id) }
    }

    Shortcut { sequence: "Ctrl+K"; onActivated: palette.open = !palette.open }
    Shortcut { sequence: "Ctrl+F"; onActivated: table.focusEntry("moment") }
    Shortcut { sequence: "Ctrl+O"; onActivated: shell.addFolder() }
    Shortcut { sequence: "Ctrl+="; onActivated: roll.zoomBy(1.25) }
    Shortcut { sequence: "Ctrl+-"; onActivated: roll.zoomBy(0.8) }
    Shortcut { sequence: "Ctrl+0"; onActivated: roll.zoomTo(168) }
}
