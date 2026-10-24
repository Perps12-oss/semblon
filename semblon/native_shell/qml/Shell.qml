import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: window
    width: 1440
    height: 900
    visible: true
    title: "Semblon"
    color: tokenBg

    property bool sidebarCollapsed: false
    readonly property bool shellReady: shell !== undefined && shell !== null
    Text {
        objectName: "lensLine"
        visible: false
        width: 0
        height: 0
        text: lensLabelSafe
    }
    readonly property var shellApi: shellReady ? shell : null
    readonly property string modeSafe: shellReady ? shellApi.mode : "primary"
    readonly property bool primaryModeSafe: shellReady ? shellApi.primaryMode : true
    readonly property bool advancedModeSafe: shellReady ? shellApi.advancedMode : false
    readonly property string atmosphereIdSafe: shellReady ? shellApi.atmosphereId : "mica_dark"
    readonly property string shellFindSimilarToken: "shell.findSimilar()"
    readonly property string shellResumeJobToken: "shell.resumeJob()"
    readonly property string shellOpenFocusToken: "shell.openFocus(mediaId)"
    readonly property string shellThumbForToken: "shell.thumbFor(mediaId)"
    readonly property string shellClearDrawnQueryToken: "shell.clearDrawnQuery()"
    readonly property string focusIdSafe: shellReady ? shellApi.focusId : ""
    readonly property bool focusActive: focusIdSafe !== ""
    readonly property bool jobRunning: shellReady && shellApi.jobActive
    readonly property string jobStateSafe: shellReady ? shellApi.jobState : "idle"
    readonly property string jobLabelSafe: shellReady ? shellApi.jobLabel : ""
    readonly property bool peopleVisible: shellReady && shellApi.peopleOpen
    readonly property bool emptySafe: shellReady ? shellApi.empty : true
    readonly property bool homeOpenSafe: shellReady ? shellApi.homeOpen : true
    readonly property string stageSafe: shellReady ? shellApi.stage : "home"
    readonly property string lensLabelSafe: shellReady ? shellApi.lensLabel : ""
    readonly property string archiveSummarySafe: shellReady ? shellApi.archiveSummary : ""
    readonly property string searchModeShortSafe: shellReady ? shellApi.searchModeShort : "Names"
    readonly property bool canResumeSafe: shellReady && shellApi.canResume
    readonly property string focusKindSafe: shellReady ? shellApi.focusKind : ""
    readonly property string focusNameSafe: shellReady ? shellApi.focusName : ""
    readonly property string similarStateSafe: shellReady ? shellApi.similarState : "idle"
    readonly property bool similarReady: similarStateSafe === "ready"
    readonly property string similarNoteSafe: shellReady ? shellApi.similarNote : ""
    readonly property int similarCountSafe: shellReady ? shellApi.similarCount : 0
    readonly property var selectedMembersSafe: shellReady ? shellApi.selectedMembers : []
    readonly property var mergeCandidatesSafe: shellReady ? shellApi.mergeCandidates : []
    readonly property string selectedTitleSafe: shellReady ? shellApi.selectedTitle : ""
    readonly property int selectedCountSafe: shellReady ? shellApi.selectedCount : 0
    readonly property string mergeTargetTitleSafe: shellReady ? shellApi.mergeTargetTitle : ""
    readonly property string mergeTargetSubjectSafe: shellReady ? shellApi.mergeTargetSubject : ""
    readonly property int splitSelectionCountSafe: shellReady ? shellApi.splitSelectionCount : 0
    readonly property bool canMergeSelectedSafe: shellReady && shellApi.canMergeSelected
    readonly property bool canSplitSelectedSafe: shellReady && shellApi.canSplitSelected
    readonly property string selectedKindSafe: shellReady ? shellApi.selectedKind : ""
    readonly property bool canNameSelectedSafe: shellReady && shellApi.canNameSelected
    readonly property bool canNoteSelectedSafe: shellReady && shellApi.canNoteSelected
    readonly property bool canIgnoreSelectedSafe: shellReady && shellApi.canIgnoreSelected
    readonly property bool canRuleOutSelectedSafe: shellReady && shellApi.canRuleOutSelected
    readonly property bool canMergeClusterSafe: shellReady && shellApi.canMergeCluster
    readonly property bool canSplitClusterSafe: shellReady && shellApi.canSplitCluster
    readonly property var personDaysSafe: shellReady ? shellApi.personDays : []
    readonly property bool canBrowsePersonTimeSafe: shellReady && shellApi.canBrowsePersonTime
    readonly property bool activityOpenSafe: shellReady && shellApi.activityOpen
    readonly property var activityRowsSafe: shellReady ? shellApi.activityRows : []
    readonly property bool tasksOpenSafe: shellReady && shellApi.tasksOpen
    readonly property string taskLabelSafe: shellReady ? shellApi.taskLabel : "Quiet"
    readonly property string taskSummarySafe: shellReady ? shellApi.taskSummary : ""
    readonly property var taskRowsSafe: shellReady ? shellApi.taskRows : []

    function taskHas(actionId) {
        var rows = taskRowsSafe
        if (!rows)
            return false
        for (var i = 0; i < rows.length; i++) {
            var actions = rows[i] && rows[i].actions ? rows[i].actions : []
            for (var j = 0; j < actions.length; j++) {
                if (actions[j] && actions[j].id === actionId)
                    return true
            }
        }
        return false
    }

    function taskActionLabel(actionId) {
        var rows = taskRowsSafe
        if (!rows)
            return ""
        for (var i = 0; i < rows.length; i++) {
            var actions = rows[i] && rows[i].actions ? rows[i].actions : []
            for (var j = 0; j < actions.length; j++) {
                if (actions[j] && actions[j].id === actionId)
                    return String(actions[j].label || "")
            }
        }
        return ""
    }
    readonly property var focusBoxesSafe: shellReady ? shellApi.focusObservationBoxes : []
    readonly property string selectedObservationSafe: shellReady ? shellApi.selectedObservationId : ""
    readonly property string stickyHeadingSafe: shellReady ? shellApi.stickyHeading : ""
    readonly property bool timeScopeActiveSafe: shellReady && shellApi.timeScopeActive
    readonly property bool timelineLoadingSafe: shellReady && shellApi.timelineLoading
    readonly property bool fieldSectionsActiveSafe: shellReady && shellApi.fieldSectionsActive
    readonly property int motion: shellReady && shellApi.reducedMotion ? 0 : 180
    readonly property color tokenBg: shellReady ? shellApi.bg0 : "#0b0c0e"
    readonly property color tokenBg1: shellReady ? shellApi.bg1 : "#131417"
    readonly property color tokenAccent: shellReady ? shellApi.accent : "#4f8cff"
    readonly property color tokenText: shellReady ? shellApi.text1 : "#f2f3f5"
    readonly property color tokenMuted: shellReady ? shellApi.text2 : "#a8adb7"
    readonly property color tokenReview: shellReady ? shellApi.reviewColor : "#a15cf5"
    readonly property color tokenBg2: shellReady ? shellApi.bg2 : "#1b1d21"
    readonly property color tokenBg3: shellReady ? shellApi.bg3 : "#24272c"
    readonly property color tokenBorder: shellReady ? shellApi.border1 : "#2a2d33"
    readonly property color tokenFaint: shellReady ? shellApi.text3 : "#6b7280"
    readonly property color tokenAccentDim: shellReady ? shellApi.accentDim : "#2b4d8f"
    readonly property color tokenDanger: shellReady ? shellApi.dangerColor : "#e5484d"
    readonly property color tokenOk: shellReady ? shellApi.okColor : "#30a46c"
    readonly property color tokenWarn: shellReady ? shellApi.warnColor : "#f5a524"
    readonly property string calendarViewSafe: shellReady ? shellApi.calendarView : "months"
    readonly property string libraryWorkspaceSafe: shellReady ? shellApi.libraryWorkspace : "calendar"
    readonly property bool libraryGridOpen: libraryWorkspaceSafe === "grid"
    readonly property bool returnOpensPhoto: {
        if (focusActive || emptySafe)
            return false
        var item = activeFocusItem
        if (!item)
            return true
        var name = item.objectName || ""
        return name !== "memoryCalendar" && name !== "timelineHero" && name !== "calendarJump"
    }
    property bool focusDetailsOpen: false
    property bool focusMoreOpen: false
    property bool refineFieldActive: false
    onFocusIdSafeChanged: {
        if (focusIdSafe === "")
            focusDetailsOpen = false
        focusMoreOpen = false
        if (focusIdSafe !== "")
            focusLayer.forceActiveFocus()
    }
    function focusHasFace() {
        var boxes = focusBoxesSafe
        if (!boxes)
            return false
        for (var i = 0; i < boxes.length; i++) {
            if (boxes[i] && boxes[i].kind === "face")
                return true
        }
        return false
    }
    function findThisPerson() {
        if (!shellReady)
            return
        var boxes = focusBoxesSafe || []
        var selected = selectedObservationSafe
        var first = ""
        for (var i = 0; i < boxes.length; i++) {
            var box = boxes[i]
            if (!box || box.kind !== "face" || !box.id)
                continue
            if (!first)
                first = box.id
            if (box.id === selected) {
                shellApi.selectObservation(box.id)
                return
            }
        }
        if (first !== "") {
            shellApi.selectObservation(first)
            return
        }
        shellApi.findSimilarFaces()
    }
    readonly property bool focusSearchRunning: shellReady && (
        shellApi.searchBusy || shellApi.screenQueryInProgress || shellApi.identifyBusy
        || similarStateSafe === "loading")
    readonly property string focusSearchTitle: {
        if (!shellReady)
            return ""
        if (shellApi.identifyBusy && !shellApi.searchBusy && !shellApi.screenQueryInProgress)
            return shellApi.nameNote !== "" ? shellApi.nameNote : "Describing this area…"
        if (!focusSearchRunning) {
            if (similarStateSafe === "ready" && similarCountSafe > 0)
                return similarCountSafe === 1 ? "1 match" : (similarCountSafe + " matches")
            if (similarStateSafe === "empty" || similarStateSafe === "error"
                    || similarStateSafe === "unavailable")
                return similarNoteSafe
            if (shellApi.selectionOnFocus)
                return "Region selected"
            return "Point or draw, then find similar"
        }
        if (shellApi.screenQueryInProgress)
            return "Searching your local archive"
        var door = shellApi.searchDoorLabel
        if (door === "Same face")
            return "Finding this person…"
        if (door === "Duplicates")
            return "Looking for duplicates…"
        if (door === "Whole photo")
            return "Searching this photo…"
        return "Finding similar regions…"
    }
    readonly property string focusSearchDetail: {
        if (!shellReady)
            return ""
        var note = similarNoteSafe
        if (focusSearchRunning && similarCountSafe > 0 && similarStateSafe === "ready")
            return similarCountSafe === 1 ? "1 match so far" : (similarCountSafe + " matches so far")
        if (!focusSearchRunning && shellApi.selectionOnFocus
                && (similarStateSafe === "idle" || note === ""))
            return "Find this visual detail across your archive."
        return ""
    }
    readonly property var primarySettingCalls: ["cycleDensity", "libraryHealth", "showActivity", "modePeople", "modeText", "modeObject", "rescan", "resetDefaults", "clearLibrary"]
    readonly property var primarySettingLabels: ["Photo size", "Check the library", "Recent activity", "Search by name", "Search words in pictures", "Search things in pictures", "Look through the folder again", "Reset how it looks", "Clear the library index"]
    readonly property var advancedSettingCalls: ["scanDuplicates", "showCapabilities", "gpuAuto", "gpuOff", "namedItems", "knowledgePack", "installModel"]
    readonly property var advancedSettingLabels: ["Look for copies", "What is installed", "Use the graphics card when it helps", "Don't use the graphics card", "Things you have named", "Knowledge pack", "Install model"]
    readonly property string displayFace: "Noto Serif"
    readonly property string uiFace: "Inter"
    font.family: uiFace
    font.pixelSize: 13

    function friendlyCapability(row) {
        var id = row ? String(row.itemId || row.id || "") : ""
        var known = {
            "region_pack": ["Finding a similar look", "The extra piece that matches a detail you point at is not on this computer yet. Colour matching still works, and Semblon will say when that is all it used."],
            "object_pack": ["Things in pictures", "Semblon cannot name things in pictures until this extra piece is installed. It never decides who someone is."],
            "vlm_local": ["Describing a picture", "A local description is not ready. Semblon will not download it on its own."],
            "ocr": ["Words in pictures", "Reading words inside pictures is not ready on this computer."],
            "clip": ["A broader sense of the picture", "This optional extra is not installed. Semblon will not fetch it by itself."],
            "face_pack": ["Recognising faces", "The files used to notice faces are not on this computer yet. Semblon does not download them. Naming someone stays your decision."],
            "opencv_load": ["Reading pictures", "Semblon could not open its picture reader on this computer."],
            "architecture": ["This computer", "Semblon is not running as the native build for this computer, so some picture work may be slower."],
            "authenticode": ["A signed installer", "This copy is not signed. That does not change the pictures already here."],
            "model_licence": ["Permission to include extras", "Some extras stay ones you add yourself."],
            "preflight": ["Setup check", "The check could not finish. Your pictures were not changed."]
        }
        if (known[id])
            return { title: known[id][0], body: known[id][1] }
        var title = row && row.name ? String(row.name) : "Something extra"
        var body = row && row.detail ? String(row.detail) : ""
        return { title: title, body: body }
    }

    function handleSetting(call) {
        if (!shellReady)
            return
        if (call === "cycleDensity") shellApi.cycleDensity()
        else if (call === "libraryHealth") shellApi.libraryHealth()
        else if (call === "scanDuplicates") shellApi.scanDuplicates()
        else if (call === "showActivity") shellApi.showActivity()
        else if (call === "showCapabilities") shellApi.showCapabilities()
        else if (call === "gpuAuto") shellApi.setGpuPreference("auto")
        else if (call === "gpuOff") shellApi.setGpuPreference("off")
        else if (call === "modePeople") shellApi.setSearchMode("people")
        else if (call === "modeText") shellApi.setSearchMode("text")
        else if (call === "modeObject") shellApi.setSearchMode("object")
        else if (call === "rescan") shellApi.rescanFolder()
        else if (call === "namedItems") shellApi.openNamedItems()
        else if (call === "knowledgePack") shellApi.chooseKnowledgePack()
        else if (call === "installModel") shellApi.chooseModelInstall()
        else if (call === "resetDefaults") shellApi.resetDefaults()
        else if (call === "clearLibrary") shellApi.clearLibrary()
    }

    function bindNav(item, navId, navLabel, navIcon, navCall) {
        item.navId = navId
        item.navLabel = navLabel
        item.navIcon = navIcon
        item.navCall = navCall
    }

    Shortcut {
        sequence: "Escape"
        onActivated: if (shellReady) shellApi.escape()
    }
    Shortcut {
        sequence: "Ctrl+Right"
        enabled: !focusActive && !homeOpenSafe
        onActivated: grid.forceActiveFocus()
    }
    Shortcut {
        sequence: "Ctrl+Left"
        enabled: !focusActive && !homeOpenSafe
        onActivated: memoryCalendar.forceActiveFocus()
    }
    Shortcut {
        sequence: "Right"
        enabled: focusActive && !matchStrip.activeFocus
        onActivated: if (shellReady) shellApi.focusNext()
    }
    Shortcut {
        sequence: "Left"
        enabled: focusActive && !matchStrip.activeFocus
        onActivated: if (shellReady) shellApi.focusPrev()
    }
    Shortcut {
        sequence: "Down"
        enabled: focusActive && similarCountSafe > 0 && !matchStrip.activeFocus
        onActivated: matchStrip.forceActiveFocus()
    }
    Shortcut {
        sequence: "K"
        enabled: focusActive && similarStateSafe === "ready" && similarCountSafe > 0
                 && !commandField.activeFocus && !searchField.activeFocus
        onActivated: if (shellReady) shellApi.keepDiscovery()
    }
    Shortcut {
        sequence: "Return"
        enabled: returnOpensPhoto
        onActivated: if (shellReady) shellApi.openIndex(grid.currentIndex)
    }
    Shortcut {
        sequence: "Ctrl+F"
        onActivated: {
            if (!shellReady)
                return
            if (primaryModeSafe)
                searchField.forceActiveFocus()
            else
                commandField.forceActiveFocus()
        }
    }
    Shortcut {
        sequence: "Ctrl+Shift+S"
        enabled: shellReady && shellApi.screenQueryAvailable && !shellApi.screenQueryInProgress
        onActivated: if (shellReady) shellApi.startScreenQuery()
    }
    Shortcut {
        sequence: "Ctrl+,"
        onActivated: if (shellReady) shellApi.toggleSettings()
    }
    Shortcut {
        sequence: "S"
        enabled: focusActive && !commandField.activeFocus && !searchField.activeFocus
                 && !refineFieldActive
        onActivated: if (shellReady) shellApi.findSimilar()
    }
    Shortcut {
        sequence: "W"
        enabled: focusActive && !commandField.activeFocus && !searchField.activeFocus
                 && !refineFieldActive
        onActivated: if (shellReady) shellApi.findSimilarWhole()
    }
    Shortcut {
        sequence: "F"
        enabled: focusActive && !commandField.activeFocus && !searchField.activeFocus
                 && !refineFieldActive
        onActivated: if (shellReady) shellApi.findSimilarFaces()
    }
    Shortcut {
        sequence: "Ctrl+D"
        enabled: focusActive && !commandField.activeFocus && !searchField.activeFocus
                 && !refineFieldActive
        onActivated: if (shellReady) shellApi.scanDuplicates()
    }
    Shortcut {
        sequence: "Alt+Left"
        enabled: focusActive && shellReady && shellApi.canBackDiscovery
        onActivated: shellApi.backToDiscovery()
    }
    Shortcut {
        sequence: "Ctrl+1"
        enabled: !commandField.activeFocus && !searchField.activeFocus
        onActivated: if (shellReady) shellApi.setLibraryFilter("all")
    }
    Shortcut {
        sequence: "Ctrl+2"
        enabled: !commandField.activeFocus && !searchField.activeFocus
        onActivated: if (shellReady) shellApi.setFacet("days")
    }
    Shortcut {
        sequence: "Ctrl+3"
        enabled: !commandField.activeFocus && !searchField.activeFocus
        onActivated: if (shellReady) shellApi.setFacet("folders")
    }

    // Collapsible navigation sidebar: destinations + archive browse (no right Explore panel).
    Rectangle {
        id: navSidebar
        objectName: "navSidebar"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: sidebarCollapsed ? 56 : 260
        color: tokenBg1
        z: 10
        // Phase 2: chrome reads slightly elevated over the cool canvas.
        border.color: Qt.rgba(1, 1, 1, 0.04)
        border.width: 0

        Behavior on width {
            NumberAnimation { duration: motion; easing.type: Easing.OutCubic }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 1
            color: Qt.rgba(1, 1, 1, 0.06)
        }

        Column {
            id: sidebarTop
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: sidebarCollapsed ? 8 : 14
            spacing: 4

            // Brand + collapse
            Item {
                width: parent.width
                height: sidebarCollapsed ? 36 : 52

                Column {
                    visible: !sidebarCollapsed
                    anchors.left: parent.left
                    anchors.right: collapseBtn.left
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 0

                    Text {
                        text: "Semblon"
                        color: tokenText
                        font.family: window.displayFace
                        font.pixelSize: 22
                        font.weight: Font.Medium
                    }
                    Text {
                        text: "Pictures, kept here"
                        color: tokenFaint
                        font.family: window.uiFace
                        font.pixelSize: 11
                        font.letterSpacing: 0.4
                    }
                }

                Rectangle {
                    id: collapseBtn
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    width: 28
                    height: 28
                    radius: 6
                    color: collapseArea.containsMouse ? tokenBg3 : "transparent"

                    Canvas {
                        anchors.centerIn: parent
                        width: 14
                        height: 14
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            ctx.strokeStyle = tokenMuted
                            ctx.lineWidth = 1.5
                            ctx.lineCap = "round"
                            if (sidebarCollapsed) {
                                ctx.beginPath()
                                ctx.moveTo(4, 2); ctx.lineTo(10, 7); ctx.lineTo(4, 12)
                                ctx.stroke()
                            } else {
                                ctx.beginPath()
                                ctx.moveTo(10, 2); ctx.lineTo(4, 7); ctx.lineTo(10, 12)
                                ctx.stroke()
                            }
                        }
                        Component.onCompleted: requestPaint()
                        Connections {
                            target: window
                            function onSidebarCollapsedChanged() { parent.requestPaint() }
                        }
                    }

                    MouseArea {
                        id: collapseArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: sidebarCollapsed = !sidebarCollapsed
                    }
                }
            }

            Item { width: 1; height: 8 }

            // Nav items. Each row is a Loader child of this column so the
            // button is a QObject under the window. Repeater delegates are
            // visual children only, and findChild cannot see them.
            Component {
                id: navEntry
                Rectangle {
                    property string navId: ""
                    property string navLabel: ""
                    property string navIcon: ""
                    property string navCall: ""
                    readonly property bool navSelected: {
                        if (navId === "people")
                            return peopleVisible
                        if (navId === "settings")
                            return shellReady && shellApi.settingsOpen
                        if (navId === "home")
                            return homeOpenSafe && !peopleVisible && !(shellReady && shellApi.settingsOpen) && !focusActive
                        if (navId === "library")
                            return !homeOpenSafe && !peopleVisible && !(shellReady && shellApi.settingsOpen) && !focusActive
                        return false
                    }
                    anchors.fill: parent
                    radius: 0
                    color: navSelected
                           ? Qt.rgba(1, 1, 1, 0.06)
                           : (navArea.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent")
                    objectName: navId === "people" ? "peopleButton" :
                                navId === "settings" ? "settingsButton" :
                                navId === "home" ? "homeButton" :
                                (navId === "library" ? "libraryButton" : "")

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.topMargin: 6
                        anchors.bottomMargin: 6
                        width: 3
                        radius: 1.5
                        color: tokenAccent
                        visible: navSelected
                    }

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: sidebarCollapsed ? 6 : 10
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12

                        DuotoneIcon {
                            width: 18
                            height: 18
                            icon: navIcon
                            fillColor: (navSelected || navArea.containsMouse) ? tokenAccent : tokenMuted
                            cutoutColor: tokenBg1
                        }

                        Text {
                            visible: !sidebarCollapsed
                            text: navLabel
                            color: navSelected ? tokenAccent : (navArea.containsMouse ? tokenText : tokenMuted)
                            font.family: window.uiFace
                            font.pixelSize: 13
                            font.letterSpacing: navSelected ? 0.4 : 0
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        id: navArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!shellReady) return
                            var c = navCall
                            if (c === "showHome") shellApi.showHome()
                            else if (c === "wordmark") shellApi.wordmark()
                            else if (c === "openPeople") shellApi.openPeople()
                            else if (c === "addFolder") { if (!jobRunning) shellApi.addFolder() }
                            else if (c === "toggleSettings") shellApi.toggleSettings()
                        }
                    }

                    ToolTip.visible: sidebarCollapsed && navArea.containsMouse
                    ToolTip.text: navLabel
                    ToolTip.delay: 400
                }
            }

            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "home", "Home", "home", "showHome")
            }
            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "library", "Library", "library", "wordmark")
            }
            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "people", "People", "people", "openPeople")
            }
            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "add", "Add folder", "addFolder", "addFolder")
            }
            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "settings", "Settings", "settings", "toggleSettings")
            }

            Item { width: 1; height: 12 }

            // Search field — Library and People only (Home has its own well)
            Rectangle {
                visible: !sidebarCollapsed && !homeOpenSafe
                width: parent.width
                height: 36
                radius: 8
                color: tokenBg2
                border.color: (searchField.activeFocus || commandField.activeFocus) ? tokenAccent : tokenBorder
                border.width: 1

                Row {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 8
                    spacing: 6

                    TextField {
                        id: searchField
                        objectName: "searchField"
                        visible: primaryModeSafe && !homeOpenSafe
                        width: parent.width - sidebarModeChip.width - 6
                        height: parent.height
                        verticalAlignment: TextInput.AlignVCenter
                        placeholderText: searchModeShortSafe === "Names" ? "Search names" : "Search memory"
                        placeholderTextColor: tokenFaint
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        background: Item {}
                        selectByMouse: true
                        onAccepted: if (shellReady) shellApi.submitCommand(text)
                    }
                    TextField {
                        id: commandField
                        objectName: "commandField"
                        visible: advancedModeSafe && !homeOpenSafe
                        width: parent.width - sidebarModeChip.width - 6
                        height: parent.height
                        verticalAlignment: TextInput.AlignVCenter
                        placeholderText: "Command…  Ctrl+K"
                        placeholderTextColor: tokenFaint
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        background: Item {}
                        selectByMouse: true
                        onAccepted: if (shellReady) shellApi.submitCommand(text)
                    }
                    Rectangle {
                        id: sidebarModeChip
                        width: sidebarModeLabel.implicitWidth + 12
                        height: 22
                        radius: 5
                        anchors.verticalCenter: parent.verticalCenter
                        visible: primaryModeSafe
                        color: tokenBg3
                        border.color: tokenBorder
                        border.width: 1
                        Text {
                            id: sidebarModeLabel
                            anchors.centerIn: parent
                            text: searchModeShortSafe
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 10
                        }
                    }
                }
            }
        }

        Flickable {
            id: archiveBrowseFlick
            objectName: "archiveBrowseFlick"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: sidebarTop.bottom
            anchors.bottom: sidebarBottom.top
            anchors.leftMargin: sidebarCollapsed ? 8 : 14
            anchors.rightMargin: sidebarCollapsed ? 8 : 14
            anchors.topMargin: 8
            anchors.bottomMargin: 8
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            contentHeight: archiveSidebar.contentHeight
            visible: !sidebarCollapsed && !homeOpenSafe && !emptySafe && !peopleVisible
            interactive: contentHeight > height

            ContextSidebar {
                id: archiveSidebar
                width: archiveBrowseFlick.width
                height: contentHeight
                shellApi: window.shellApi
                shellReady: window.shellReady
                advancedMode: window.advancedModeSafe
                tokenBg0: window.tokenBg
                tokenBg1: window.tokenBg1
                tokenBg2: window.tokenBg2
                tokenBg3: window.tokenBg3
                tokenAccent: window.tokenAccent
                tokenText: window.tokenText
                tokenMuted: window.tokenMuted
                tokenFaint: window.tokenFaint
                tokenBorder: window.tokenBorder
                motion: window.motion
            }
        }

        // Bottom section (job only — mode and atmosphere live in Settings)
        Column {
            id: sidebarBottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: sidebarCollapsed ? 8 : 14
            spacing: 6

            Item {
                id: sidebarJobRow
                objectName: "sidebarJobRow"
                visible: jobRunning
                width: parent.width
                height: sidebarJobLine.implicitHeight

                Row {
                    id: sidebarJobLine
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 8

                Item {
                    width: 14
                    height: 14
                    RotationAnimation on rotation {
                        running: shellReady && jobRunning && jobStateSafe !== "paused" && jobStateSafe !== "cancelling" && !shellApi.reducedMotion
                        loops: Animation.Infinite
                        duration: 1100
                        from: 0
                        to: 360
                    }
                    Canvas {
                        anchors.fill: parent
                        onPaint: {
                            var ctx = getContext("2d")
                            ctx.reset()
                            ctx.strokeStyle = tokenAccent
                            ctx.lineWidth = 1.5
                            ctx.beginPath()
                            ctx.arc(width/2, height/2, 5, 0, Math.PI * 1.35)
                            ctx.stroke()
                        }
                        Component.onCompleted: requestPaint()
                    }
                }
                Text {
                    visible: !sidebarCollapsed
                    width: Math.max(0, sidebarJobLine.width - 22)
                    text: jobLabelSafe
                    color: tokenMuted
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    Accessible.name: "Open library work"
                    Accessible.role: Accessible.Button
                    onClicked: if (shellReady) shellApi.openTasks()
                }
            }
        }

    }


    Item {
        id: stage
        anchors.left: navSidebar.right
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        Rectangle {
            id: jobBand
            objectName: "jobBand"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 20
            anchors.rightMargin: 20
            anchors.topMargin: 16
            z: 6
            radius: 0
            visible: shellReady && !jobRunning && (shellApi.surfaceState === "error" || shellApi.surfaceState === "unavailable" || shellApi.surfaceState === "loading")
            color: shellReady && shellApi.surfaceState === "error"
                   ? Qt.rgba(tokenDanger.r, tokenDanger.g, tokenDanger.b, 0.16)
                   : tokenBg2
            border.color: shellReady && shellApi.surfaceState === "error" ? tokenDanger : tokenBorder
            border.width: 1
            implicitHeight: bandCol.implicitHeight + 28
            height: visible ? implicitHeight : 0

            Column {
                id: bandCol
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 4

                Text {
                    objectName: "surfaceState"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: {
                        if (!shellReady)
                            return ""
                        if (shellApi.noticeText)
                            return shellApi.noticeText
                        if (shellApi.surfaceState === "loading")
                            return "Working…"
                        if (shellApi.surfaceState === "unavailable")
                            return "That is not available on this computer yet."
                        return "Something went wrong. Try again."
                    }
                    color: shellReady && shellApi.surfaceState === "error" ? tokenText : tokenText
                    font.family: window.uiFace
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    visible: shellReady && shellApi.surfaceState === "error"
                    text: "Your original pictures were not changed."
                    color: tokenMuted
                    font.family: window.uiFace
                    font.pixelSize: 13
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    visible: shellReady && shellApi.surfaceState === "loading"
                    text: "This can take a moment. Pictures that are already here stay open."
                    color: tokenMuted
                    font.family: window.uiFace
                    font.pixelSize: 13
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    visible: shellReady && shellApi.surfaceState === "unavailable"
                    text: "Other ways of looking through your pictures still work."
                    color: tokenMuted
                    font.family: window.uiFace
                    font.pixelSize: 13
                }
            }
        }

        Rectangle {
            objectName: "activitySheet"
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 16
            anchors.rightMargin: 16
            width: 320
            height: Math.min(stage.height - 40, activityColumn.implicitHeight + 28)
            radius: 10
            visible: advancedModeSafe && activityOpenSafe && !focusActive && !peopleVisible
            color: tokenBg1
            border.color: tokenBorder
            border.width: 1
            z: 3

            Column {
                id: activityColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 8

                Item {
                    width: parent.width
                    height: 22
                    Text {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Activity"
                        color: tokenText
                        font.pixelSize: 16
                        font.family: "Segoe UI"
                    }
                    Text {
                        objectName: "closeActivity"
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Close"
                        color: closeActivityArea.containsMouse ? tokenText : tokenMuted
                        font.pixelSize: 13
                        MouseArea {
                            id: closeActivityArea
                            anchors.fill: parent
                            anchors.margins: -4
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.closeActivity()
                        }
                    }
                }

                Text {
                    width: parent.width
                    visible: activityRowsSafe.length === 0
                    text: shellReady ? (shellApi.noticeText || "Nothing has been added yet.") : ""
                    color: tokenMuted
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }

                Repeater {
                    model: activityRowsSafe
                    delegate: Column {
                        width: activityColumn.width
                        spacing: 2
                        Text {
                            visible: index === 0 || activityRowsSafe[index - 1].section !== modelData.section
                            text: modelData.section
                            color: tokenFaint
                            font.pixelSize: 11
                            font.letterSpacing: 0.4
                        }
                        Text {
                            width: parent.width
                            text: modelData.text
                            color: tokenText
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                        }
                    }
                }
            }
        }

        Rectangle {
            objectName: "settingsSheet"
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.topMargin: 16
            anchors.rightMargin: 16
            width: 280
            height: settingsColumn.implicitHeight + 28
            radius: 10
            visible: shellReady && shellApi.settingsOpen && !focusActive
            color: tokenBg1
            border.color: tokenBorder
            border.width: 1
            z: 3

            Column {
                id: settingsColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 8

                Text {
                    text: "Settings"
                    color: tokenText
                    font.pixelSize: 22
                    font.family: window.displayFace
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "How Semblon looks, and what it can do on this computer."
                    color: tokenMuted
                    font.pixelSize: 12
                    font.family: window.uiFace
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: shellReady ? shellApi.searchModeLabel : ""
                    color: tokenMuted
                    font.pixelSize: 12
                    font.family: "Segoe UI"
                }
                Text {
                    width: parent.width
                    text: "How much to show"
                    color: tokenFaint
                    font.pixelSize: 11
                    font.letterSpacing: 0.4
                    font.family: window.uiFace
                }
                Row {
                    width: parent.width
                    spacing: 8
                    Rectangle {
                        objectName: "primaryModeButton"
                        width: (parent.width - 8) / 2
                        height: 28
                        radius: 6
                        color: primaryModeSafe ? tokenAccentDim : tokenBg2
                        border.color: primaryModeSafe ? tokenAccent : tokenBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Everyday"
                            color: primaryModeSafe ? tokenText : tokenMuted
                            font.pixelSize: 12
                            font.family: window.uiFace
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setMode("primary")
                        }
                    }
                    Rectangle {
                        objectName: "advancedModeButton"
                        width: (parent.width - 8) / 2
                        height: 28
                        radius: 6
                        color: advancedModeSafe ? tokenAccentDim : tokenBg2
                        border.color: advancedModeSafe ? tokenAccent : tokenBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "More detail"
                            color: advancedModeSafe ? tokenText : tokenMuted
                            font.pixelSize: 12
                            font.family: window.uiFace
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setMode("advanced")
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: "How hard to look"
                    color: tokenFaint
                    font.pixelSize: 11
                    font.letterSpacing: 0.4
                    font.family: window.uiFace
                }
                Text {
                    objectName: "searchQualityLabel"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: shellReady ? ("Search quality is " + shellApi.searchQualityLabel + ".") : ""
                    color: tokenMuted
                    font.pixelSize: 12
                    font.family: "Segoe UI"
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "Fast stays snappy. Max looks harder. Neither path is a duplicate scan."
                    color: tokenFaint
                    font.pixelSize: 11
                    font.family: "Segoe UI"
                }
                Row {
                    width: parent.width
                    spacing: 6
                    Rectangle {
                        id: qualityFastButton
                        objectName: "qualityFast"
                        width: (parent.width - 12) / 3
                        height: 28
                        radius: 6
                        property bool selected: shellReady && shellApi.searchQuality === "fast"
                        color: selected ? tokenAccentDim : (qualityFastHit.containsMouse ? tokenBg3 : tokenBg2)
                        border.color: selected ? tokenAccent : tokenBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Fast"
                            color: qualityFastButton.selected ? tokenText : tokenMuted
                            font.pixelSize: 12
                            font.family: "Segoe UI"
                        }
                        MouseArea {
                            id: qualityFastHit
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setSearchQuality("fast")
                        }
                    }
                    Rectangle {
                        id: qualityBalancedButton
                        objectName: "qualityBalanced"
                        width: (parent.width - 12) / 3
                        height: 28
                        radius: 6
                        property bool selected: shellReady && shellApi.searchQuality === "balanced"
                        color: selected ? tokenAccentDim : (qualityBalancedHit.containsMouse ? tokenBg3 : tokenBg2)
                        border.color: selected ? tokenAccent : tokenBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Balanced"
                            color: qualityBalancedButton.selected ? tokenText : tokenMuted
                            font.pixelSize: 12
                            font.family: "Segoe UI"
                        }
                        MouseArea {
                            id: qualityBalancedHit
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setSearchQuality("balanced")
                        }
                    }
                    Rectangle {
                        id: qualityMaxButton
                        objectName: "qualityMax"
                        width: (parent.width - 12) / 3
                        height: 28
                        radius: 6
                        property bool selected: shellReady && shellApi.searchQuality === "max"
                        color: selected ? tokenAccentDim : (qualityMaxHit.containsMouse ? tokenBg3 : tokenBg2)
                        border.color: selected ? tokenAccent : tokenBorder
                        border.width: 1
                        Text {
                            anchors.centerIn: parent
                            text: "Max"
                            color: qualityMaxButton.selected ? tokenText : tokenMuted
                            font.pixelSize: 12
                            font.family: "Segoe UI"
                        }
                        MouseArea {
                            id: qualityMaxHit
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setSearchQuality("max")
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: "What's ready"
                    color: tokenFaint
                    font.pixelSize: 11
                    font.letterSpacing: 0.4
                    font.family: window.uiFace
                }
                Text {
                    objectName: "preflightSummary"
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: shellReady ? shellApi.preflightSummary : ""
                    color: tokenMuted
                    font.pixelSize: 12
                    font.family: "Segoe UI"
                }
                Repeater {
                    objectName: "preflightRepeater"
                    model: shellReady ? shellApi.preflightRows : []
                    delegate: Column {
                        width: settingsColumn.width
                        spacing: 4
                        readonly property var spoken: window.friendlyCapability({
                            id: model.id,
                            itemId: model.itemId,
                            name: model.name,
                            detail: model.detail
                        })
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: spoken.title
                            color: tokenText
                            font.pixelSize: 13
                            font.family: window.displayFace
                        }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: spoken.body
                            color: tokenMuted
                            font.pixelSize: 12
                            font.family: window.uiFace
                        }
                        Rectangle {
                            visible: installable
                            objectName: "preflightInstall"
                            width: 72
                            height: 26
                            radius: 6
                            color: preflightInstallHit.containsMouse ? tokenAccentDim : tokenBg2
                            border.color: tokenBorder
                            border.width: 1
                            Text {
                                anchors.centerIn: parent
                                text: "Install"
                                color: tokenText
                                font.pixelSize: 12
                                font.family: "Segoe UI"
                            }
                            MouseArea {
                                id: preflightInstallHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.installPreflight(model.itemId)
                            }
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: "Look and feel"
                    color: tokenFaint
                    font.pixelSize: 11
                    font.letterSpacing: 0.4
                    font.family: window.uiFace
                }
                ComboBox {
                    id: atmospherePicker
                    objectName: "atmospherePicker"
                    width: parent.width
                    model: shellReady ? shellApi.atmosphereChoices : []
                    textRole: "label"
                    displayText: (currentIndex >= 0 && model.length > currentIndex) ? model[currentIndex].label : "Colour theme"
                    palette.window: tokenBg2
                    palette.base: tokenBg2
                    palette.button: tokenBg2
                    palette.buttonText: tokenText
                    palette.text: tokenText
                    palette.highlightedText: tokenText
                    palette.highlight: tokenAccentDim
                    onActivated: if (shellReady && currentIndex >= 0 && model.length > currentIndex) {
                        shellApi.setAtmosphere(model[currentIndex].id)
                    }
                    Component.onCompleted: {
                        if (!shellReady) return
                        for (var i = 0; i < model.length; i++) {
                            if (model[i].id === atmosphereIdSafe) {
                                currentIndex = i
                                break
                            }
                        }
                    }
                }
                    Repeater {
                    objectName: "primarySettingsRepeater"
                    model: primarySettingCalls.length
                    delegate: Rectangle {
                        Component.onCompleted: objectName = "setting_" + primarySettingCalls[index]
                        width: parent.width
                        height: 28
                        radius: 6
                        color: settingHit.containsMouse ? tokenBg3 : tokenBg2
                        Text {
                            anchors.centerIn: parent
                            text: primarySettingLabels[index]
                            color: tokenText
                            font.pixelSize: 12
                            font.family: "Segoe UI"
                        }
                        MouseArea {
                            id: settingHit
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: window.handleSetting(primarySettingCalls[index])
                        }
                    }
                }
                Repeater {
                    model: advancedModeSafe ? 7 : 0
                    delegate: Rectangle {
                        property string settingCall: advancedSettingCalls[index]
                        Component.onCompleted: objectName = "setting_" + settingCall
                        width: parent.width
                        height: 28
                        radius: 6
                        color: settingHitAdvanced.containsMouse ? tokenBg3 : tokenBg2
                        Text {
                            anchors.centerIn: parent
                            text: advancedSettingLabels[index]
                            color: tokenText
                            font.pixelSize: 12
                            font.family: "Segoe UI"
                        }
                        MouseArea {
                            id: settingHitAdvanced
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: window.handleSetting(settingCall)
                        }
                    }
                }
            }
        }

        Rectangle {
            objectName: "namedItemsSheet"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 16
            anchors.topMargin: 16
            width: 300
            height: Math.min(420, namedItemsColumn.implicitHeight + 28)
            radius: 10
            visible: shellReady && shellApi.namedItemsOpen && !focusActive
            color: tokenBg1
            border.color: tokenBorder
            border.width: 1
            z: 4

            Column {
                id: namedItemsColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 14
                spacing: 8

                Text {
                    text: "Named items"
                    color: tokenText
                    font.pixelSize: 16
                    font.family: "Segoe UI"
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: "A saved region. This does not name a person."
                    color: tokenMuted
                    font.pixelSize: 12
                    font.family: "Segoe UI"
                }
                Repeater {
                    model: shellReady ? shellApi.namedItemCount : 0
                    delegate: Text {
                        property string itemId: shellReady ? shellApi.namedItemId(index) : ""
                        Component.onCompleted: objectName = "namedItemRow"
                        text: shellReady ? shellApi.namedItemLabel(index) : ""
                        color: tokenText
                        font.pixelSize: 13
                        font.family: "Segoe UI"
                        MouseArea {
                            anchors.fill: parent
                            onClicked: if (shellReady) shellApi.selectNamedItem(itemId)
                        }
                    }
                }
                TextField {
                    id: namedItemField
                    objectName: "namedItemField"
                    width: parent.width
                    placeholderText: "Name this item"
                    color: tokenText
                    font.pixelSize: 13
                }
                Rectangle {
                    objectName: "nameNamedItem"
                    width: parent.width
                    height: 28
                    radius: 6
                    color: tokenBg2
                    Text {
                        anchors.centerIn: parent
                        text: "Save item name"
                        color: tokenText
                        font.pixelSize: 12
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: if (shellReady) shellApi.nameNamedItem(namedItemField.text)
                    }
                }
                Text {
                    text: "Close"
                    color: tokenMuted
                    font.pixelSize: 12
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -4
                        onClicked: if (shellReady) shellApi.closeNamedItems()
                    }
                }
            }
        }

        Rectangle {
            objectName: "peopleDesk"
            anchors.fill: parent
            visible: peopleVisible && !focusActive
            color: tokenBg
            ScrollView {
                anchors.fill: parent
                anchors.margins: 28
                clip: true

                Column {
                    width: stage.width - 56
                    spacing: 16

                    Text {
                        text: "People"
                        color: tokenText
                        font.pixelSize: 40
                        font.family: window.displayFace
                        font.weight: Font.Medium
                    }
                    Text {
                        width: parent.width
                        text: "Name someone only when you recognise them. Until then, a group is only a suggestion."
                        color: tokenMuted
                        font.family: window.uiFace
                        font.pixelSize: 15
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        objectName: "peopleHypothesisNote"
                        width: parent.width
                        text: "Groups are hypotheses until you name them. A group is not a person."
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        objectName: "reviewCounts"
                        width: parent.width
                        text: shellReady ? shellApi.reviewCountText : ""
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        objectName: "unresolvedLine"
                        width: parent.width
                        text: shellReady ? shellApi.unresolvedText : ""
                        color: unresolvedHit.containsMouse ? tokenText : tokenReview
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        MouseArea {
                            id: unresolvedHit
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.openUnresolvedInbox()
                        }
                    }

                    Column {
                        width: parent.width
                        spacing: 6
                        visible: shellReady && shell.peopleEmpty

                        Text {
                            objectName: "peopleEmpty"
                            text: "No groups yet."
                            color: tokenText
                            font.family: window.displayFace
                            font.pixelSize: 22
                        }
                        Text {
                            width: parent.width
                            wrapMode: Text.WordWrap
                            text: "Add pictures that include people. Semblon will suggest groups. A suggestion is not a person until you give them a name. Unknown is a fine answer."
                            color: tokenMuted
                            font.family: window.uiFace
                            font.pixelSize: 14
                        }
                    }

                    Row {
                        width: parent.width
                        spacing: 18

                        Rectangle {
                            width: 320
                            height: 620
                            radius: 10
                            color: tokenBg1
                            border.color: tokenBorder
                            border.width: 1

                            Column {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                Text {
                                    text: "Groups to look at"
                                    color: tokenText
                                    font.pixelSize: 18
                                    font.family: window.displayFace
                                }

                                ListView {
                                    objectName: "peopleList"
                                    width: parent.width
                                    height: parent.height - 42
                                    model: peopleModel
                                    clip: true
                                    spacing: 8
                                    delegate: Rectangle {
                                        width: ListView.view.width
                                        height: 64
                                        radius: 8
                                        color: named
                                                ? ((shellReady && shell.selectedSubject === subject) ? tokenAccentDim : tokenBg2)
                                                : (band === "strong" ? tokenBg2 : tokenBg3)
                                        border.color: named
                                                ? ((shellReady && shell.selectedSubject === subject) ? tokenAccent : tokenBorder)
                                                : (band === "strong" ? tokenAccent : tokenReview)
                                        border.width: 1

                                        Row {
                                            anchors.fill: parent
                                            anchors.margins: 8
                                            spacing: 10

                                            Rectangle {
                                                width: 48
                                                height: 48
                                                radius: 6
                                                color: tokenBg
                                                border.color: tokenBorder
                                                border.width: 1
                                                anchors.verticalCenter: parent.verticalCenter

                                                Image {
                                                    anchors.fill: parent
                                                    anchors.margins: 1
                                                    source: shellReady && faceId !== "" ? shell.faceThumb(faceId) : ""
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    cache: true
                                                    visible: status === Image.Ready
                                                }
                                            }

                                            Column {
                                                width: parent.width - 58
                                                anchors.verticalCenter: parent.verticalCenter
                                                spacing: 2

                                                Text {
                                                    width: parent.width
                                                    text: title
                                                    color: tokenText
                                                    font.pixelSize: 14
                                                    elide: Text.ElideRight
                                                }
                                                Text {
                                                    width: parent.width
                                                    text: bandLabel + " · " + faceCount + (faceCount === 1 ? " face" : " faces")
                                                    color: tokenMuted
                                                    font.pixelSize: 12
                                                    elide: Text.ElideRight
                                                }
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.selectGroup(subject)
                                        }
                                    }
                                }
                            }
                        }

                        Rectangle {
                            width: stage.width - 56 - 338
                            height: 620
                            radius: 10
                            color: tokenBg1
                            border.color: tokenBorder
                            border.width: 1

                            Column {
                                anchors.fill: parent
                                anchors.margins: 18
                                spacing: 12

                                Row {
                                    width: parent.width
                                    spacing: 10

                                    Column {
                                        width: parent.width - 90
                                        spacing: 2

                                        Text {
                                            text: selectedTitleSafe !== "" ? selectedTitleSafe : "Choose a group"
                                            color: tokenText
                                            font.pixelSize: 20
                                            font.family: "Segoe UI Variable"
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                            text: shellReady && shell.selectedSubject !== ""
                                                  ? ((shellApi.selectedBandLabel || "") + " · "
                                                     + selectedCountSafe
                                                     + (selectedCountSafe === 1 ? " face" : " faces"))
                                                  : "Choose a group. You can name them, leave them unknown, or say these faces are not the same person."
                                            color: tokenMuted
                                            font.pixelSize: 13
                                            wrapMode: Text.WordWrap
                                        }
                                    }

                                    Text {
                                        objectName: "peopleEvidence"
                                        visible: shellReady && shell.evidenceId !== ""
                                        text: "See these photos"
                                        color: evidenceArea.containsMouse ? tokenText : tokenAccent
                                        font.pixelSize: 14
                                        anchors.verticalCenter: parent.verticalCenter
                                        MouseArea {
                                            id: evidenceArea
                                            anchors.fill: parent
                                            anchors.margins: -6
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.openEvidence(shellApi.evidenceId)
                                        }
                                    }
                                }

                                Column {
                                    objectName: "personTimePanel"
                                    width: parent.width
                                    spacing: 8
                                    visible: canBrowsePersonTimeSafe

                                    Text {
                                        text: "This person's days"
                                        color: tokenText
                                        font.pixelSize: 14
                                        font.family: "Segoe UI"
                                    }

                                    Flow {
                                        objectName: "personDayChips"
                                        width: parent.width
                                        spacing: 8

                                        Repeater {
                                            model: personDaysSafe
                                            delegate: Rectangle {
                                                property var dayRow: modelData
                                                height: 28
                                                width: dayChipLabel.implicitWidth + 16
                                                radius: 6
                                                color: dayChipHit.containsMouse ? tokenAccentDim : tokenBg2
                                                border.color: tokenAccent
                                                border.width: 1

                                                Text {
                                                    id: dayChipLabel
                                                    anchors.centerIn: parent
                                                    text: (dayRow.day || "") + " · " + (dayRow.count || 0)
                                                    color: tokenText
                                                    font.family: "Segoe UI"
                                                    font.pixelSize: 12
                                                }
                                                MouseArea {
                                                    id: dayChipHit
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: if (shellReady) shellApi.openPersonDay(dayRow.day || "")
                                                }
                                            }
                                        }
                                    }

                                    Text {
                                        objectName: "browsePersonTime"
                                        text: "Browse in Time"
                                        color: browseTimeHit.containsMouse ? tokenText : tokenAccent
                                        font.pixelSize: 14
                                        MouseArea {
                                            id: browseTimeHit
                                            anchors.fill: parent
                                            anchors.margins: -4
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.browseSelectedPersonInTime()
                                        }
                                    }

                                    Text {
                                        objectName: "showPersonOnly"
                                        text: "Show only this person"
                                        color: personOnlyHit.containsMouse ? tokenText : tokenAccent
                                        font.pixelSize: 14
                                        MouseArea {
                                            id: personOnlyHit
                                            anchors.fill: parent
                                            anchors.margins: -4
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.showSelectedPersonOnly()
                                        }
                                    }
                                }

                                TextField {
                                    id: decisionText
                                    objectName: "decisionText"
                                    width: parent.width
                                    placeholderText: "Name or note"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 14
                                    background: Rectangle {
                                        radius: 8
                                        color: tokenBg2
                                        border.color: decisionText.activeFocus ? tokenAccent : tokenBorder
                                        border.width: 1
                                    }
                                }

                                Row {
                                    width: parent.width
                                    spacing: 16
                                    visible: shellReady && shellApi.selectedSubject !== ""

                                    Text {
                                        visible: canNameSelectedSafe
                                        text: "Name"
                                        color: decisionText.text.trim().length > 0 ? tokenAccent : tokenFaint
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("name", shellApi.selectedSubject, decisionText.text)
                                        }
                                    }
                                    Text {
                                        visible: canNoteSelectedSafe
                                        text: "Note"
                                        color: decisionText.text.trim().length > 0 ? tokenAccent : tokenFaint
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("note", shellApi.selectedSubject, decisionText.text)
                                        }
                                    }
                                    Text {
                                        visible: canIgnoreSelectedSafe
                                        text: "Ignore"
                                        color: tokenAccent
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("ignore", shellApi.selectedSubject, "")
                                        }
                                    }
                                    Text {
                                        visible: canRuleOutSelectedSafe
                                        text: primaryModeSafe ? "Not this person" : "Rule out"
                                        color: tokenAccent
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("rule_out", shellApi.selectedSubject, decisionText.text)
                                        }
                                    }
                                }

                                Text {
                                    text: shellReady ? shell.peopleNote : ""
                                    color: tokenMuted
                                    font.pixelSize: 13
                                    wrapMode: Text.WordWrap
                                }

                                Rectangle {
                                    visible: canMergeClusterSafe
                                    width: parent.width
                                    height: 86
                                    radius: 8
                                    color: tokenBg
                                    border.color: tokenBorder
                                    border.width: 1

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 8

                                        Text {
                                            text: "Merge with another group"
                                            color: tokenText
                                            font.pixelSize: 14
                                        }
                                        Flow {
                                            width: parent.width
                                            spacing: 8
                                            objectName: "mergeTargetFlow"
                                            Repeater {
                                                model: mergeCandidatesSafe
                                                delegate: Rectangle {
                                                    visible: kind === "cluster"
                                                    width: Math.min(180, titleText.implicitWidth + 28)
                                                    height: 30
                                                    radius: 15
                                                    color: shellReady && mergeTargetSubjectSafe === subject ? tokenAccentDim : tokenBg2
                                                    border.color: shellReady && mergeTargetSubjectSafe === subject ? tokenAccent : tokenBorder
                                                    border.width: 1

                                                    Text {
                                                        id: titleText
                                                        anchors.centerIn: parent
                                                        text: title + " · " + faceCount
                                                        color: tokenText
                                                        font.pixelSize: 12
                                                    }

                                                    MouseArea {
                                                        anchors.fill: parent
                                                        hoverEnabled: true
                                                        cursorShape: Qt.PointingHandCursor
                                                        onClicked: if (shellReady) shellApi.selectMergeTarget(subject)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                Row {
                                    visible: canMergeClusterSafe || canSplitClusterSafe
                                    width: parent.width
                                    spacing: 14

                                    Text {
                                        visible: canMergeClusterSafe
                                        text: "Merge"
                                        color: canMergeSelectedSafe ? tokenAccent : tokenFaint
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.mergeSelectedGroup()
                                        }
                                    }

                                    Text {
                                        objectName: "clearSplitSelection"
                                        visible: canSplitClusterSafe
                                        text: "Clear selection"
                                        color: splitSelectionCountSafe > 0 ? tokenAccent : tokenFaint
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.clearSplitSelection()
                                        }
                                    }

                                    Text {
                                        visible: canSplitClusterSafe
                                        text: splitSelectionCountSafe > 0 ? (splitSelectionCountSafe === 1 ? "1 face selected" : splitSelectionCountSafe + " faces selected") : "Select faces below to split them out"
                                        color: tokenMuted
                                        font.pixelSize: 13
                                    }

                                    Text {
                                        visible: canSplitClusterSafe
                                        text: "Split selected"
                                        color: canSplitSelectedSafe ? tokenAccent : tokenFaint
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.splitSelectedFaces()
                                        }
                                    }
                                }

                                Rectangle {
                                    visible: canSplitClusterSafe
                                    width: parent.width
                                    height: 280
                                    radius: 8
                                    color: tokenBg
                                    border.color: tokenBorder
                                    border.width: 1

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 10

                                        Text {
                                            text: "Select faces to split"
                                            color: tokenText
                                            font.pixelSize: 14
                                        }
                                        Text {
                                            text: "Click one or more faces, then split only those faces out of the group."
                                            color: tokenMuted
                                            font.pixelSize: 12
                                            wrapMode: Text.WordWrap
                                        }
                                        GridView {
                                            objectName: "splitFaceGrid"
                                            width: parent.width
                                            height: 208
                                            clip: true
                                            cellWidth: 94
                                            cellHeight: 118
                                            model: selectedMembersSafe
                                            delegate: Rectangle {
                                                width: 84
                                                height: 110
                                                radius: 8
                                                color: shellReady && shell.isSplitFaceSelected(face_id) ? tokenAccentDim : tokenBg2
                                                border.color: shellReady && shell.isSplitFaceSelected(face_id) ? tokenAccent : tokenBorder
                                                border.width: 1

                                                Column {
                                                    anchors.fill: parent
                                                    anchors.margins: 6
                                                    spacing: 4

                                                    Rectangle {
                                                        width: parent.width
                                                        height: 76
                                                        radius: 6
                                                        color: tokenBg
                                                        border.color: tokenBorder
                                                        border.width: 1

                                                        Image {
                                                            anchors.fill: parent
                                                            anchors.margins: 1
                                                            source: shellReady ? shell.faceThumb(face_id) : ""
                                                            fillMode: Image.PreserveAspectCrop
                                                            asynchronous: true
                                                            cache: true
                                                        }
                                                    }

                                                    Text {
                                                        width: parent.width
                                                        text: "Face " + (index + 1)
                                                        color: tokenText
                                                        font.pixelSize: 11
                                                        horizontalAlignment: Text.AlignHCenter
                                                        elide: Text.ElideRight
                                                    }
                                                }

                                                MouseArea {
                                                    anchors.fill: parent
                                                    hoverEnabled: true
                                                    cursorShape: Qt.PointingHandCursor
                                                    onClicked: if (shellReady) shellApi.toggleSplitFace(face_id)
                                                }
                                            }
                                        }
                                    }
                                }

                                Text {
                                    objectName: "peopleBack"
                                    text: "Back"
                                    color: backPeopleArea.containsMouse ? tokenText : tokenMuted
                                    font.pixelSize: 14
                                    MouseArea {
                                        id: backPeopleArea
                                        anchors.fill: parent
                                        anchors.margins: -8
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: if (shellReady) shellApi.closePeople()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // One workspace: the calendar fills this pane until a day or other
        // scope opens the photo grid in its place.
        Item {
            id: archivePane
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 12
            anchors.bottomMargin: 12
            visible: !homeOpenSafe && !emptySafe && !peopleVisible && !focusActive
            property real splitRatio: 0.46
            property real zoomScale: 0.50
            property string zoomBand: "months"

            function midpoint(view) {
                if (view === "years") return 0.12
                if (view === "days") return 0.88
                return 0.50
            }

            function bandFor(scale) {
                var current = zoomBand
                if (current === "years") {
                    if (scale > 0.29) return scale >= 0.80 ? "days" : "months"
                    return "years"
                }
                if (current === "days") {
                    if (scale < 0.72) return scale <= 0.21 ? "years" : "months"
                    return "days"
                }
                if (scale <= 0.21) return "years"
                if (scale >= 0.80) return "days"
                return "months"
            }

            function adjustZoom(delta) {
                zoomScale = Math.max(0, Math.min(1, zoomScale + delta))
                var next = bandFor(zoomScale)
                if (next === zoomBand)
                    return
                zoomBand = next
                if (shellReady)
                    shellApi.setCalendarView(next)
            }

            function selectCalendarView(view) {
                zoomBand = view
                zoomScale = midpoint(view)
                if (shellReady)
                    shellApi.setCalendarView(view)
            }

            Component.onCompleted: {
                zoomBand = calendarViewSafe
                zoomScale = midpoint(calendarViewSafe)
                if (shellReady)
                    splitRatio = shellApi.archiveSplit
            }

            Connections {
                target: shellReady ? shellApi : null
                function onEditorialChanged() {
                    if (!splitHandle.pressed && shellReady)
                        archivePane.splitRatio = shellApi.archiveSplit
                }
            }

            WheelHandler {
                objectName: "archiveZoomWheel"
                enabled: !libraryGridOpen
                acceptedModifiers: Qt.ControlModifier
                onWheel: function(event) {
                    archivePane.adjustZoom(event.angleDelta.y / 1200)
                }
            }

            PinchHandler {
                objectName: "archivePinch"
                enabled: !libraryGridOpen
                target: null
                property real origin: 1
                onActiveChanged: if (active) origin = 1
                onActiveScaleChanged: {
                    if (!active)
                        return
                    archivePane.adjustZoom((activeScale - origin) * 0.35)
                    origin = activeScale
                }
            }

            // Soft center lift (Phase 2 atmosphere) — edges stay on canvas floor.
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: -8
                width: parent.width * 0.92
                height: Math.min(parent.height * 0.62, 520)
                radius: width
                color: Qt.lighter(tokenBg, 1.35)
                opacity: 0.22
                z: 0
                visible: !libraryGridOpen
            }

            Item {
                id: archiveHeaderBand
                objectName: "archiveHeaderBand"
                z: 1
                anchors.fill: parent
                visible: !libraryGridOpen
                clip: true

                Column {
                    id: headerColumn
                    width: parent.width
                    spacing: 8

                    Row {
                        id: densityBar
                        objectName: "timelineDensitySegment"
                        width: parent.width
                        height: 32
                        layoutDirection: Qt.RightToLeft
                        spacing: 0

                        Rectangle {
                            width: densityRow.width + 6
                            height: 30
                            radius: 8
                            color: tokenBg3

                            Row {
                                id: densityRow
                                x: 3
                                y: 3
                                spacing: 2
                                height: 24

                                Repeater {
                                    model: [
                                        { key: "years", label: "Years" },
                                        { key: "months", label: "Months" },
                                        { key: "days", label: "Days" }
                                    ]
                                    delegate: Rectangle {
                                        required property var modelData
                                        width: densityLabel.implicitWidth + 18
                                        height: 24
                                        radius: 6
                                        color: calendarViewSafe === modelData.key ? tokenAccent : "transparent"
                                        Text {
                                            id: densityLabel
                                            anchors.centerIn: parent
                                            text: modelData.label
                                            color: calendarViewSafe === modelData.key ? tokenText : tokenMuted
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                            font.weight: Font.DemiBold
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            objectName: modelData.key === "years"
                                                       ? "densityYears"
                                                       : (modelData.key === "months" ? "densityMonths" : "densityDays")
                                            onClicked: archivePane.selectCalendarView(modelData.key)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        id: timelineBlock
                        width: parent.width
                        height: calendarViewSafe === "years" ? 0 : timelineHero.height
                        visible: height > 0
                        clip: true
                        TimelineLandscape {
                            id: timelineHero
                            width: parent.width
                            shellApi: window.shellApi
                            shellReady: window.shellReady
                            yearModel: window.shellReady ? window.shellApi.timelineDensity : []
                            loading: window.timelineLoadingSafe
                            scopeKind: window.shellReady ? window.shellApi.scopeKind : ""
                            scopeLabel: window.shellReady ? window.shellApi.scopeLabel : ""
                            tokenBg: window.tokenBg
                            tokenBg2: window.tokenBg2
                            tokenAccent: window.tokenAccent
                            tokenAccentDim: window.tokenAccentDim
                            tokenText: window.tokenText
                            tokenMuted: window.tokenMuted
                            tokenFaint: window.tokenFaint
                            tokenBorder: window.tokenBorder
                            motion: window.motion
                            onYearClicked: (label) => { if (window.shellReady) window.shellApi.selectYear(label) }
                            onMonthClicked: (label) => { if (window.shellReady) window.shellApi.selectMonth(label) }
                            onRangeSelected: (startDay, endDay) => { if (window.shellReady) window.shellApi.selectRange(startDay, endDay) }
                        }
                    }

                    Item {
                        id: calendarStage
                        width: parent.width
                        height: Math.max(160, archiveHeaderBand.height - densityBar.height - timelineBlock.height - headerColumn.spacing * 2)

                        YearMatrix {
                            anchors.fill: parent
                            visible: calendarViewSafe === "years"
                            enabled: calendarViewSafe === "years"
                            title: shellReady ? shellApi.calendarYear : ""
                            months: shellReady ? shellApi.yearMatrix : []
                            tokenBg2: window.tokenBg2
                            tokenAccent: window.tokenAccent
                            tokenText: window.tokenText
                            tokenMuted: window.tokenMuted
                            tokenFaint: window.tokenFaint
                            tokenBorder: window.tokenBorder
                            tokenOk: window.tokenOk
                            tokenWarn: window.tokenWarn
                            opacity: calendarViewSafe === "years" ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: window.motion } }
                            onMonthClicked: (label) => {
                                if (!window.shellReady)
                                    return
                                archivePane.selectCalendarView("months")
                                shellApi.selectMonth(label)
                            }
                            onRangeChosen: (startDay, endDay) => {
                                if (window.shellReady)
                                    shellApi.selectRange(startDay, endDay)
                            }
                        }

                        MemoryCalendar {
                            id: memoryCalendar
                            anchors.fill: parent
                            visible: calendarViewSafe !== "years"
                            enabled: calendarViewSafe !== "years"
                            opacity: calendarViewSafe === "years" ? 0 : 1
                            Behavior on opacity { NumberAnimation { duration: window.motion } }
                            numbersOnly: calendarViewSafe === "days"
                            shellApi: window.shellApi
                            shellReady: window.shellReady
                            cells: window.shellReady ? window.shellApi.calendarCells : []
                            title: window.shellReady ? window.shellApi.calendarTitle : ""
                            scopeKind: window.shellReady ? window.shellApi.scopeKind : ""
                            scopeLabel: window.shellReady ? window.shellApi.scopeLabel : ""
                            revealedDay: window.shellReady ? window.shellApi.revealedDay : ""
                            undatedCount: window.shellReady ? window.shellApi.undatedCount : 0
                            tokenBg: window.tokenBg
                            tokenBg1: window.tokenBg1
                            tokenBg2: window.tokenBg2
                            tokenBg3: window.tokenBg3
                            tokenAccent: window.tokenAccent
                            tokenAccentDim: window.tokenAccentDim
                            tokenText: window.tokenText
                            tokenMuted: window.tokenMuted
                            tokenFaint: window.tokenFaint
                            tokenBorder: window.tokenBorder
                            motion: window.motion
                            onDayClicked: (day) => { if (window.shellReady) window.shellApi.openDay(day) }
                            onDayDoubleClicked: (day) => {
                                if (!window.shellReady)
                                    return
                                archivePane.selectCalendarView("days")
                                shellApi.openDay(day)
                            }
                            onThumbClicked: (mediaId, day) => {
                                if (!window.shellReady)
                                    return
                                shellApi.openDay(day)
                                shellApi.openFocus(mediaId)
                            }
                            onRangeChosen: (startDay, endDay) => {
                                if (window.shellReady)
                                    shellApi.selectRange(startDay, endDay)
                            }
                            onJumpRequested: (text) => { if (window.shellReady) window.shellApi.revealDay(text) }
                            onUndatedClicked: { if (window.shellReady) window.shellApi.showUndated() }
                            onPrevMonth: { if (window.shellReady) window.shellApi.calendarPrevMonth() }
                            onNextMonth: { if (window.shellReady) window.shellApi.calendarNextMonth() }
                            onGoHome: { if (window.shellReady) window.shellApi.calendarGoHome() }
                        }
                    }
                }
            }

            MouseArea {
                id: splitHandle
                objectName: "archiveSplit"
                visible: false
                enabled: false
                x: 0
                y: 0
                width: 0
                height: 0
                z: 4
            }

            Item {
                id: fieldViewport
                objectName: "fieldViewport"
                anchors.fill: parent
                visible: libraryGridOpen
                clip: true
                z: 1

                Column {
                    id: fieldChrome
                    width: parent.width
                    spacing: 4

                    Item {
                        width: parent.width
                        height: 28

                        Text {
                            id: gridBackLabel
                            objectName: "gridBack"
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Back"
                            color: gridBackArea.containsMouse ? tokenText : tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            MouseArea {
                                id: gridBackArea
                                anchors.fill: parent
                                anchors.margins: -6
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Back to calendar"
                                Accessible.role: Accessible.Button
                                onClicked: if (shellReady) shellApi.showCalendar()
                            }
                        }

                        Text {
                            objectName: "gridWorkspaceTitle"
                            anchors.left: gridBackLabel.right
                            anchors.leftMargin: 16
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: shellReady ? shellApi.gridTitle : ""
                            color: tokenText
                            font.family: "Segoe UI"
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }
                    }

                    Text {
                        id: stickyHeader
                        objectName: "stickyHeader"
                        width: parent.width
                        visible: fieldSectionsActiveSafe && stickyHeadingSafe !== ""
                        text: stickyHeadingSafe
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 14
                        font.weight: Font.DemiBold
                    }

                    Text {
                        id: zeroResultFilter
                        objectName: "zeroResultFilter"
                        width: parent.width
                        visible: libraryGridOpen && !fieldSectionsActiveSafe && grid.count === 0
                        text: shellReady && shellApi.scopeKind === "day"
                              ? "No photos on this day. Back returns to the calendar."
                              : "Nothing in this view. Go back, or try another day."
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                    }
                }

            ListView {
                id: fieldSectionsView
                objectName: "fieldSections"
                property string latchedScope: ""
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: fieldChrome.bottom
                anchors.bottom: parent.bottom
                visible: fieldSectionsActiveSafe
                clip: true
                spacing: 14
                cacheBuffer: 800
                boundsBehavior: Flickable.StopAtBounds
                model: shellReady ? shellApi.fieldSections : []
                enabled: !focusActive

            delegate: Column {
                id: sectionCol
                width: fieldSectionsView.width
                spacing: 6
                property var section: modelData
                property string sectionDay: section ? String(section.day) : ""

                Text {
                    objectName: "fieldSection_" + sectionCol.sectionDay
                    width: parent.width
                    text: section && section.shortLabel ? section.shortLabel
                          : (section && section.label ? section.label : sectionCol.sectionDay)
                    color: tokenText
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    Accessible.name: section && section.label ? section.label : text
                }

                GridView {
                    id: sectionGrid
                    width: parent.width
                    interactive: false
                    clip: true
                    cellWidth: shellReady ? shellApi.cellSize : 160
                    cellHeight: cellWidth
                    readonly property int columns: Math.max(1, Math.floor(width / Math.max(1, cellWidth)))
                    model: section && section.previewIds ? section.previewIds
                           : (section && section.mediaIds ? section.mediaIds.slice(0, 24) : [])
                    height: Math.ceil(Math.max(1, count) / columns) * cellHeight
                    boundsBehavior: Flickable.StopAtBounds
                    delegate: Item {
                        width: sectionGrid.cellWidth
                        height: sectionGrid.cellHeight

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 6
                            color: tokenBg2
                            radius: 8
                            border.width: sectionTile.containsMouse ? 1 : 0
                            border.color: tokenAccent

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 1
                                radius: 8
                                color: tokenBg3
                                visible: sectionImage.status !== Image.Ready
                            }

                            Image {
                                id: sectionImage
                                anchors.fill: parent
                                anchors.margins: 1
                                source: "image://archive/t/" + modelData
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                            }

                            MouseArea {
                                id: sectionTile
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (!shellReady)
                                        return
                                    shellApi.setScroll(fieldSectionsView.contentY)
                                    shellApi.openFocus(modelData)
                                }
                            }
                        }
                    }
                }

                Text {
                    visible: section && Number(section.count || 0) > (section.previewIds ? section.previewIds.length : 24)
                    text: "Show this day (" + String(section.count) + ")"
                    color: tokenAccent
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -2
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady && section) shellApi.openDay(String(section.day))
                    }
                }
            }

            onContentYChanged: {
                if (!focusActive && shellReady) {
                    timelineHero.cancelHover()
                    memoryCalendar.cancelHover()
                    var idx = indexAt(width / 2, contentY + 8)
                    if (idx < 0 && count > 0)
                        idx = 0
                    if (idx >= 0) {
                        var item = itemAtIndex(idx)
                        if (item && item.sectionDay)
                            shellApi.setStickyDay(item.sectionDay)
                    }
                    shellApi.setScroll(contentY)
                }
            }

            Connections {
                target: shellReady ? shellApi : null
                function onEditorialChanged() {
                    var key = shellReady ? (shellApi.scopeKind + ":" + shellApi.scopeLabel) : ""
                    if (key === fieldSectionsView.latchedScope)
                        return
                    fieldSectionsView.latchedScope = key
                    if (!focusActive && fieldSectionsActiveSafe)
                        fieldSectionsView.contentY = 0
                }
            }
            }

            GridView {
                id: grid
                objectName: "fieldGrid"
                property string latchedScope: ""
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: fieldChrome.bottom
                anchors.bottom: parent.bottom
                visible: !fieldSectionsActiveSafe
                clip: true
                cellWidth: shellReady ? shellApi.cellSize : 160
                cellHeight: shellReady ? shellApi.cellSize : 160
                cacheBuffer: 400
                boundsBehavior: Flickable.StopAtBounds
                model: archiveModel
                currentIndex: 0
                enabled: !focusActive && !fieldSectionsActiveSafe
                keyNavigationEnabled: !focusActive && !fieldSectionsActiveSafe
                highlightFollowsCurrentItem: false

            delegate: Item {
                width: grid.cellWidth
                height: grid.cellHeight
                readonly property bool tileSelected: grid.currentIndex === index

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 6
                    color: tokenBg2
                    radius: 8
                    border.width: tileSelected ? 2 : (tile.containsMouse ? 1 : 0)
                    border.color: tileSelected
                                 ? tokenAccent
                                 : (tile.containsMouse ? Qt.rgba(1, 1, 1, 0.2) : "transparent")

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 1
                        radius: 7
                        color: tokenBg3
                        visible: kind !== "video" && tileImage.status !== Image.Ready
                    }

                    Image {
                        id: tileImage
                        anchors.fill: parent
                        anchors.margins: 1
                        visible: kind !== "video"
                        source: kind !== "video" ? ("image://archive/t/" + mediaId) : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Text {
                        anchors.centerIn: parent
                        visible: kind === "video"
                        text: "Video"
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                    }

                    MouseArea {
                        id: tile
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!shellReady)
                                return
                            grid.currentIndex = index
                            shellApi.setScroll(grid.contentY)
                            shellApi.openFocus(mediaId)
                        }
                    }
                }
            }

            onContentYChanged: {
                if (!focusActive && shellReady && !fieldSectionsActiveSafe) {
                    timelineHero.cancelHover()
                    memoryCalendar.cancelHover()
                    var idx = indexAt(width / 2, contentY + 16)
                    if (idx < 0 && count > 0)
                        idx = 0
                    if (idx >= 0) {
                        var dayVal = shellApi.dayAt(idx)
                        if (dayVal)
                            shellApi.setStickyDay(dayVal)
                    }
                    shellApi.setScroll(contentY)
                }
            }

            Connections {
                target: shellApi
                function onFocusChanged() {
                    if (!focusActive && shellReady)
                        grid.contentY = shellApi.scrollY
                }
                function onEditorialChanged() {
                    var key = shellReady ? (shellApi.scopeKind + ":" + shellApi.scopeLabel) : ""
                    if (key === grid.latchedScope)
                        return
                    grid.latchedScope = key
                    if (!focusActive)
                        grid.contentY = 0
                }
            }
            }
            }
        }

        HomeLaunchpad {
            id: homeLaunchpad
            objectName: "emptyState"
            anchors.fill: parent
            visible: homeOpenSafe && !peopleVisible && !focusActive
            shellApi: window.shellApi
            shellReady: window.shellReady
            emptyArchive: emptySafe
            jobRunning: jobRunning
            canResume: canResumeSafe
            jobLabel: jobLabelSafe
            archiveSummary: archiveSummarySafe
            searchModeShort: searchModeShortSafe
            advancedMode: advancedModeSafe
            tokenBg: window.tokenBg
            tokenBg1: window.tokenBg1
            tokenBg2: window.tokenBg2
            tokenBg3: window.tokenBg3
            tokenAccent: window.tokenAccent
            tokenAccentDim: window.tokenAccentDim
            tokenText: window.tokenText
            tokenMuted: window.tokenMuted
            tokenFaint: window.tokenFaint
            tokenBorder: window.tokenBorder
        }

        Item {
            id: focusLayer
            objectName: "focusLayer"
            anchors.fill: parent
            visible: focusActive
            focus: true
            opacity: focusActive ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            Rectangle {
                anchors.fill: parent
                color: tokenBg
            }

            Text {
                id: pointHint
                objectName: "pointHint"
                z: 8
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 10
                visible: focusActive && focusKindSafe !== "video"
                text: "Point or draw to search"
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Row {
                id: indexNoteRow
                z: 6
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: pointHint.bottom
                anchors.topMargin: 2
                spacing: 8
                visible: focusActive && shellReady && shellApi.indexNote !== ""

                BusyIndicator {
                    objectName: "focusIndexSpinner"
                    width: 14
                    height: 14
                    anchors.verticalCenter: parent.verticalCenter
                    visible: shellReady && (shellApi.indexState === "indexing" || shellApi.indexState === "patch")
                    running: visible && !shellApi.reducedMotion
                }
                Text {
                    objectName: "indexNote"
                    width: Math.min(implicitWidth, focusLayer.width - 320)
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    text: shellReady ? shellApi.indexNote : ""
                    color: tokenText
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                }
            }

            Text {
                objectName: "sampledFrameNote"
                z: 8
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.top: parent.top
                anchors.topMargin: 36
                visible: focusActive && focusKindSafe === "video"
                text: "Sampled frame. Not a player."
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Text {
                objectName: "focusMissingNote"
                z: 8
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                width: parent.width - 96
                visible: focusActive
                         && shellReady
                         && shellApi.focusFileMissing
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 15
                text: "This photo is missing from its stored path. "
                      + "If you moved or renamed it, add that folder again so Semblon can reconnect it."
            }

            Item {
                id: photoViewport
                objectName: "photoViewport"
                z: 1
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: focusTray.top
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                anchors.topMargin: 8
                anchors.bottomMargin: 0
                clip: true

                Item {
                    id: photoView
                    objectName: "photoView"
                    width: photoViewport.width
                    height: photoViewport.height
                    scale: 1
                    transformOrigin: Item.Center

                    function resetView() {
                        x = 0
                        y = 0
                        scale = 1
                    }

                    function applyTriple(spec) {
                        var parts = String(spec).split(",")
                        if (parts.length < 3)
                            return
                        x = parseFloat(parts[0])
                        y = parseFloat(parts[1])
                        scale = parseFloat(parts[2])
                    }

                    function clampView() {
                        if (!shellReady || width < 1 || height < 1)
                            return
                        applyTriple(shellApi.clampFocusView(x, y, scale, width, height))
                    }

                    function zoomAt(viewX, viewY, factor) {
                        if (!shellReady || width < 1 || height < 1)
                            return
                        applyTriple(shellApi.zoomFocusView(
                            x, y, scale, viewX, viewY, width, height, factor))
                    }

                    Image {
                        id: photo
                        anchors.fill: parent
                        visible: focusActive
                        source: focusActive ? ("image://archive/f/" + focusIdSafe) : ""
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                        cache: false
                    }

            Item {
                id: observationLayer
                objectName: "observationLayer"
                anchors.fill: photo
                visible: photo.paintedWidth > 0

                function contentOrigin() {
                    return Qt.point(
                        (width - photo.paintedWidth) / 2,
                        (height - photo.paintedHeight) / 2
                    )
                }

                Repeater {
                    model: focusBoxesSafe
                    delegate: Rectangle {
                        property var box: modelData
                        readonly property var origin: observationLayer.contentOrigin()
                        x: origin.x + box.nx * photo.paintedWidth
                        y: origin.y + box.ny * photo.paintedHeight
                        width: Math.max(2, box.nw * photo.paintedWidth)
                        height: Math.max(2, box.nh * photo.paintedHeight)
                        color: "transparent"
                        border.color: selectedObservationSafe === box.id ? tokenAccent : box.color
                        border.width: selectedObservationSafe === box.id ? 2 : 1
                        z: 1

                        Text {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.margins: 2
                            text: box.tag
                            color: tokenText
                            font.pixelSize: 10
                            visible: selectedObservationSafe === box.id && box.tag !== ""
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.selectObservation(box.id)
                        }
                    }
                }

                Rectangle {
                    objectName: "matchOverlay"
                    visible: shellReady && shellApi.matchW > 0.01 && shellApi.matchH > 0.01
                    readonly property var origin: observationLayer.contentOrigin()
                    x: origin.x + shellApi.matchX * photo.paintedWidth
                    y: origin.y + shellApi.matchY * photo.paintedHeight
                    width: Math.max(2, shellApi.matchW * photo.paintedWidth)
                    height: Math.max(2, shellApi.matchH * photo.paintedHeight)
                    color: Qt.rgba(tokenAccent.r, tokenAccent.g, tokenAccent.b, 0.28)
                    border.color: tokenAccent
                    border.width: 2
                    z: 4
                }
            }

            MouseArea {
                id: regionDrag
                objectName: "regionDrag"
                anchors.fill: photo
                enabled: photo.paintedWidth > 0
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton
                preventStealing: false
                z: 2
                property real rx: 0
                property real ry: 0
                property real rw: 0
                property real rh: 0
                property bool hasRect: false
                property real x0: 0
                property real y0: 0
                property bool dragging: false
                property bool moving: false
                property bool resizing: false
                property bool panning: false
                property string resizeEdge: ""
                property real moveW: 0
                property real moveH: 0
                property real startRx: 0
                property real startRy: 0
                property real startRw: 0
                property real startRh: 0
                property real panVX: 0
                property real panVY: 0
                property real panX0: 0
                property real panY0: 0

                function contentOrigin() {
                    return Qt.point(
                        (width - photo.paintedWidth) / 2,
                        (height - photo.paintedHeight) / 2
                    )
                }

                function insidePainted(px, py) {
                    var origin = contentOrigin()
                    return photo.paintedWidth > 1 && photo.paintedHeight > 1
                            && px >= origin.x && py >= origin.y
                            && px < origin.x + photo.paintedWidth
                            && py < origin.y + photo.paintedHeight
                }

                function selectionRect() {
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    if (!shellReady || pw <= 1 || ph <= 1 || !shellApi.selectionOnFocus)
                        return Qt.rect(0, 0, 0, 0)
                    return Qt.rect(
                        origin.x + shellApi.selectionX * pw,
                        origin.y + shellApi.selectionY * ph,
                        Math.max(1, shellApi.selectionW * pw),
                        Math.max(1, shellApi.selectionH * ph)
                    )
                }

                function insideSelection(px, py) {
                    var box = selectionRect()
                    return box.width > 2 && px >= box.x && py >= box.y
                            && px <= box.x + box.width && py <= box.y + box.height
                }

                function edgeAt(px, py) {
                    var box = selectionRect()
                    if (box.width < 2 || box.height < 2)
                        return ""
                    var margin = Math.max(12, 12 / Math.max(photoView.scale, 1))
                    var nearL = Math.abs(px - box.x) <= margin
                            && py >= box.y - margin && py <= box.y + box.height + margin
                    var nearR = Math.abs(px - (box.x + box.width)) <= margin
                            && py >= box.y - margin && py <= box.y + box.height + margin
                    var nearT = Math.abs(py - box.y) <= margin
                            && px >= box.x - margin && px <= box.x + box.width + margin
                    var nearB = Math.abs(py - (box.y + box.height)) <= margin
                            && px >= box.x - margin && px <= box.x + box.width + margin
                    if (nearL && nearT)
                        return "tl"
                    if (nearR && nearT)
                        return "tr"
                    if (nearL && nearB)
                        return "bl"
                    if (nearR && nearB)
                        return "br"
                    if (nearL)
                        return "l"
                    if (nearR)
                        return "r"
                    if (nearT)
                        return "t"
                    if (nearB)
                        return "b"
                    return ""
                }

                function cursorFor(edge) {
                    if (edge === "l" || edge === "r")
                        return Qt.SizeHorCursor
                    if (edge === "t" || edge === "b")
                        return Qt.SizeVerCursor
                    if (edge === "tl" || edge === "br")
                        return Qt.SizeFDiagCursor
                    if (edge === "tr" || edge === "bl")
                        return Qt.SizeBDiagCursor
                    return Qt.ArrowCursor
                }

                function beginPan(mouse) {
                    var start = mapToItem(photoViewport, mouse.x, mouse.y)
                    panning = true
                    resizing = false
                    moving = false
                    dragging = false
                    panVX = start.x
                    panVY = start.y
                    panX0 = photoView.x
                    panY0 = photoView.y
                }

                function applyResize(dx, dy) {
                    if (!shellReady)
                        return
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    if (pw <= 1 || ph <= 1)
                        return
                    var spec = shellApi.adjustSelectionBox(
                        startRx, startRy, startRw, startRh, resizeEdge, dx, dy,
                        origin.x, origin.y, origin.x + pw, origin.y + ph
                    )
                    var parts = String(spec).split(",")
                    if (parts.length !== 4)
                        return
                    rx = parseFloat(parts[0])
                    ry = parseFloat(parts[1])
                    rw = parseFloat(parts[2])
                    rh = parseFloat(parts[3])
                    hasRect = true
                    dragging = true
                }

                function commitSelection() {
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    dragging = false
                    moving = false
                    resizing = false
                    if (!shellReady || pw <= 1 || ph <= 1 || rw < 4 || rh < 4) {
                        hasRect = false
                        return
                    }
                    shellApi.setRegion(
                        Math.max(0, Math.min(1, (rx - origin.x) / pw)),
                        Math.max(0, Math.min(1, (ry - origin.y) / ph)),
                        Math.max(0, Math.min(1, rw / pw)),
                        Math.max(0, Math.min(1, rh / ph))
                    )
                    hasRect = false
                    shellApi.findSimilar()
                }

                function hitObservation(px, py) {
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    if (pw <= 1 || ph <= 1)
                        return ""
                    for (var i = focusBoxesSafe.length - 1; i >= 0; i--) {
                        var box = focusBoxesSafe[i]
                        if (box.snap === false)
                            continue
                        var bx = origin.x + box.nx * pw
                        var by = origin.y + box.ny * ph
                        var bw = Math.max(2, box.nw * pw)
                        var bh = Math.max(2, box.nh * ph)
                        if (px >= bx && py >= by && px <= bx + bw && py <= by + bh)
                            return box.id
                    }
                    return ""
                }

                onPressed: function(mouse) {
                    if (photoPinch.active) {
                        mouse.accepted = false
                        return
                    }
                    var alt = (mouse.modifiers & Qt.AltModifier) !== 0
                    if (mouse.button === Qt.MiddleButton || alt) {
                        beginPan(mouse)
                        return
                    }
                    dragging = false
                    moving = false
                    resizing = false
                    panning = false
                    x0 = mouse.x
                    y0 = mouse.y
                    var edge = edgeAt(mouse.x, mouse.y)
                    if (edge !== "") {
                        var edgeBox = selectionRect()
                        resizing = true
                        resizeEdge = edge
                        cursorShape = cursorFor(edge)
                        startRx = edgeBox.x
                        startRy = edgeBox.y
                        startRw = edgeBox.width
                        startRh = edgeBox.height
                        rx = edgeBox.x
                        ry = edgeBox.y
                        rw = edgeBox.width
                        rh = edgeBox.height
                        hasRect = true
                        return
                    }
                    if (insideSelection(mouse.x, mouse.y)) {
                        var box = selectionRect()
                        moving = true
                        moveW = box.width
                        moveH = box.height
                        startRx = box.x
                        startRy = box.y
                        rx = box.x
                        ry = box.y
                        rw = box.width
                        rh = box.height
                        return
                    }
                    rx = mouse.x
                    ry = mouse.y
                    rw = 0
                    rh = 0
                    hasRect = true
                }
                onPositionChanged: function(mouse) {
                    if (!pressed) {
                        var hoverEdge = edgeAt(mouse.x, mouse.y)
                        if (hoverEdge !== "")
                            cursorShape = cursorFor(hoverEdge)
                        else if (insideSelection(mouse.x, mouse.y))
                            cursorShape = Qt.SizeAllCursor
                        else
                            cursorShape = Qt.ArrowCursor
                        return
                    }
                    if (panning) {
                        var panPoint = mapToItem(photoViewport, mouse.x, mouse.y)
                        photoView.x = panX0 + (panPoint.x - panVX)
                        photoView.y = panY0 + (panPoint.y - panVY)
                        return
                    }
                    if (resizing) {
                        applyResize(mouse.x - x0, mouse.y - y0)
                        return
                    }
                    if (moving) {
                        var origin = contentOrigin()
                        var dx = mouse.x - x0
                        var dy = mouse.y - y0
                        var maxX = origin.x + photo.paintedWidth - moveW
                        var maxY = origin.y + photo.paintedHeight - moveH
                        rx = Math.max(origin.x, Math.min(startRx + dx, maxX))
                        ry = Math.max(origin.y, Math.min(startRy + dy, maxY))
                        rw = moveW
                        rh = moveH
                        dragging = Math.abs(dx) >= 4 || Math.abs(dy) >= 4
                        hasRect = true
                        return
                    }
                    rx = Math.min(x0, mouse.x)
                    ry = Math.min(y0, mouse.y)
                    rw = Math.abs(mouse.x - x0)
                    rh = Math.abs(mouse.y - y0)
                    if (rw >= 4 || rh >= 4)
                        dragging = true
                }
                onReleased: function(mouse) {
                    if (panning) {
                        panning = false
                        photoView.clampView()
                        return
                    }
                    if (resizing) {
                        var changed = Math.abs(rx - startRx) >= 1 || Math.abs(ry - startRy) >= 1
                                || Math.abs(rw - startRw) >= 1 || Math.abs(rh - startRh) >= 1
                        resizing = false
                        if (changed)
                            commitSelection()
                        else {
                            dragging = false
                            hasRect = false
                        }
                        return
                    }
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    if (moving) {
                        var moved = dragging
                        if (moved) {
                            commitSelection()
                            return
                        }
                        moving = false
                        hasRect = false
                        var keptHit = hitObservation(mouse.x, mouse.y)
                        if (keptHit !== "" && shellReady)
                            shellApi.selectObservation(keptHit)
                        return
                    }
                    if (pw <= 1 || ph <= 1) {
                        hasRect = false
                        shell.clearDrawnQuery()
                        return
                    }
                    if (rw < 4 || rh < 4) {
                        hasRect = false
                        if (!insidePainted(mouse.x, mouse.y)) {
                            shell.clearDrawnQuery()
                            return
                        }
                        var hit = hitObservation(mouse.x, mouse.y)
                        if (hit !== "") {
                            if (shellReady)
                                shellApi.selectObservation(hit)
                            return
                        }
                        var spec = shell.pointAt(
                            Math.max(0, Math.min(0.999999, (mouse.x - origin.x) / pw)),
                            Math.max(0, Math.min(0.999999, (mouse.y - origin.y) / ph))
                        )
                        if (!spec)
                            return
                        var parts = spec.split(",")
                        if (parts.length !== 4)
                            return
                        rx = origin.x + parseFloat(parts[0]) * pw
                        ry = origin.y + parseFloat(parts[1]) * ph
                        rw = Math.max(1, parseFloat(parts[2]) * pw)
                        rh = Math.max(1, parseFloat(parts[3]) * ph)
                        hasRect = false
                        return
                    }
                    var nx = (rx - origin.x) / pw
                    var ny = (ry - origin.y) / ph
                    var nw = rw / pw
                    var nh = rh / ph
                    shell.setRegion(
                        Math.max(0, Math.min(1, nx)),
                        Math.max(0, Math.min(1, ny)),
                        Math.max(0, Math.min(1, nw)),
                        Math.max(0, Math.min(1, nh))
                    )
                    hasRect = false
                    shell.findSimilar()
                }
                onCanceled: {
                    dragging = false
                    moving = false
                    resizing = false
                    panning = false
                    hasRect = false
                }
            }

            Item {
                id: selectionShade
                objectName: "selectionShade"
                readonly property var origin: regionDrag.contentOrigin()
                readonly property real localX: selectionOutline.x - x
                readonly property real localY: selectionOutline.y - y
                visible: selectionOutline.visible
                x: photo.paintedWidth > 1 ? photo.x + origin.x : 0
                y: photo.paintedHeight > 1 ? photo.y + origin.y : 0
                width: photo.paintedWidth > 1 ? photo.paintedWidth : 0
                height: photo.paintedHeight > 1 ? photo.paintedHeight : 0
                clip: true
                z: 1

                Rectangle {
                    x: 0
                    y: 0
                    width: parent.width
                    height: Math.max(0, selectionShade.localY)
                    color: Qt.rgba(0, 0, 0, 0.5)
                }
                Rectangle {
                    x: 0
                    y: selectionShade.localY + selectionOutline.height
                    width: parent.width
                    height: Math.max(0, parent.height - (selectionShade.localY + selectionOutline.height))
                    color: Qt.rgba(0, 0, 0, 0.5)
                }
                Rectangle {
                    x: 0
                    y: Math.max(0, selectionShade.localY)
                    width: Math.max(0, selectionShade.localX)
                    height: selectionOutline.height
                    color: Qt.rgba(0, 0, 0, 0.5)
                }
                Rectangle {
                    x: selectionShade.localX + selectionOutline.width
                    y: Math.max(0, selectionShade.localY)
                    width: Math.max(0, parent.width - (selectionShade.localX + selectionOutline.width))
                    height: selectionOutline.height
                    color: Qt.rgba(0, 0, 0, 0.5)
                }
            }

            Rectangle {
                id: selectionOutline
                objectName: "selectionOutline"
                visible: regionDrag.hasRect
                         || (shellReady && shellApi.selectionOnFocus && shellApi.selectionW > 0.004)
                readonly property var origin: regionDrag.contentOrigin()
                x: photo.x + (regionDrag.hasRect
                              ? regionDrag.rx
                              : origin.x + (shellReady ? shellApi.selectionX : 0) * photo.paintedWidth)
                y: photo.y + (regionDrag.hasRect
                              ? regionDrag.ry
                              : origin.y + (shellReady ? shellApi.selectionY : 0) * photo.paintedHeight)
                width: regionDrag.hasRect
                       ? regionDrag.rw
                       : Math.max(2, (shellReady ? shellApi.selectionW : 0) * photo.paintedWidth)
                height: regionDrag.hasRect
                        ? regionDrag.rh
                        : Math.max(2, (shellReady ? shellApi.selectionH : 0) * photo.paintedHeight)
                color: "transparent"
                border.color: "white"
                border.width: 1
                z: 3
            }

            Repeater {
                model: 4
                delegate: Item {
                    objectName: "selectionHandle"
                    visible: selectionOutline.visible
                    readonly property int arm: 18
                    readonly property int thick: 3
                    readonly property bool rightSide: index % 2 === 1
                    readonly property bool bottomSide: index >= 2
                    width: arm
                    height: arm
                    z: 6
                    x: selectionOutline.x + (rightSide ? selectionOutline.width - arm : 0)
                    y: selectionOutline.y + (bottomSide ? selectionOutline.height - arm : 0)
                    Accessible.name: "Resize selection"
                    Accessible.role: Accessible.Button

                    Rectangle {
                        y: parent.bottomSide ? parent.height - parent.thick : 0
                        width: parent.arm
                        height: parent.thick
                        color: "white"
                    }
                    Rectangle {
                        x: parent.rightSide ? parent.width - parent.thick : 0
                        width: parent.thick
                        height: parent.arm
                        color: "white"
                    }
                }
            }

                    PinchHandler {
                        id: photoPinch
                        objectName: "photoPinch"
                        target: photoView
                        minimumScale: 1
                        maximumScale: 8
                        minimumRotation: 0
                        maximumRotation: 0
                        onActiveChanged: {
                            if (!active)
                                photoView.clampView()
                        }
                    }
                }

                WheelHandler {
                    id: photoWheel
                    objectName: "photoWheel"
                    onWheel: function(event) {
                        if (photoPinch.active)
                            return
                        if ((event.modifiers & Qt.ControlModifier) === 0)
                            return
                        var steps = event.angleDelta.y / 120
                        if (Math.abs(steps) < 0.01 && event.pixelDelta.y !== 0)
                            steps = event.pixelDelta.y / 60
                        if (Math.abs(steps) < 0.01)
                            return
                        event.accepted = true
                        photoView.zoomAt(event.x, event.y, Math.pow(1.12, steps))
                    }
                }

                Connections {
                    target: window
                    function onFocusIdSafeChanged() {
                        photoView.resetView()
                    }
                }
            }

            // Playback is deferred. QtMultimedia is intentionally not imported:
            // PySide6-Essentials (the declared GUI dep) does not ship it. When a
            // video viewer lands, add a guarded optional import or a dedicated
            // extras package — do not pull WebEngine via the PySide6 metapackage.
            Text {
                objectName: "videoMissing"
                visible: false
                text: ""
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 15
            }

            Rectangle {
                objectName: "focusDetails"
                visible: window.focusDetailsOpen && focusActive
                width: 280
                anchors.top: parent.top
                anchors.bottom: focusTray.top
                anchors.right: parent.right
                z: 8
                color: tokenBg1
                border.color: tokenBorder
                border.width: 1

                Column {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 10

                    Row {
                        width: parent.width
                        height: 24
                        Text {
                            text: "Details"
                            color: tokenText
                            font.family: "Segoe UI"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Item { width: parent.width - 80; height: 1 }
                        Text {
                            objectName: "focusDetailsClose"
                            text: "Close"
                            color: detailsClose.containsMouse ? tokenText : tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            anchors.verticalCenter: parent.verticalCenter
                            MouseArea {
                                id: detailsClose
                                anchors.fill: parent
                                anchors.margins: -6
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: window.focusDetailsOpen = false
                            }
                        }
                    }

                    Image {
                        width: parent.width
                        height: 180
                        source: focusActive ? ("image://archive/t/" + focusIdSafe) : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }

                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        text: "File Name: " + (shellReady ? shellApi.focusFileFacts.name : "")
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        text: "Date Taken: " + (shellReady ? shellApi.focusFileFacts.date : "")
                    }
                    Text {
                        width: parent.width
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        text: "Dimensions: " + (shellReady ? shellApi.focusFileFacts.dimensions : "")
                    }
                    Text {
                        width: parent.width
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        text: "Size: " + (shellReady ? shellApi.focusFileFacts.size : "")
                    }
                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        text: "Camera: " + (shellReady ? shellApi.focusFileFacts.camera : "")
                    }

                    Rectangle {
                        width: parent.width
                        height: 72
                        radius: 8
                        color: tokenBg2
                        border.color: tokenBorder
                        border.width: 1
                        Text {
                            anchors.fill: parent
                            anchors.margins: 8
                            wrapMode: Text.WordWrap
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            text: "Location\n" + (shellReady ? shellApi.focusFileFacts.location : "")
                        }
                    }
                }
            }

            Text {
                objectName: "focusBack"
                z: 9
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 14
                text: "Back"
                color: backArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                MouseArea {
                    id: backArea
                    anchors.fill: parent
                    anchors.margins: -8
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    Accessible.name: "Back"
                    Accessible.role: Accessible.Button
                    onClicked: if (shellReady) shellApi.escape()
                }
            }

            Text {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.topMargin: 16
                anchors.rightMargin: window.focusDetailsOpen ? 296 : 18
                text: "Details"
                color: window.focusDetailsOpen || detailsToggle.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
                z: 9
                MouseArea {
                    id: detailsToggle
                    objectName: "focusDetailsToggle"
                    anchors.fill: parent
                    anchors.margins: -8
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    Accessible.name: "Details"
                    Accessible.role: Accessible.Button
                    onClicked: window.focusDetailsOpen = !window.focusDetailsOpen
                }
            }

            Rectangle {
                id: focusTray
                objectName: "focusTray"
                z: 7
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: Math.min(Math.max(trayFlick.contentHeight + 20, 88), Math.round(parent.height * 0.46))
                color: tokenBg1

                Rectangle {
                    anchors.top: parent.top
                    width: parent.width
                    height: 1
                    color: tokenBorder
                }

                Flickable {
                    id: trayFlick
                    anchors.fill: parent
                    anchors.margins: 12
                    contentWidth: width
                    contentHeight: focusTrayColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    flickableDirection: Flickable.VerticalFlick

                    Column {
                        id: focusTrayColumn
                        objectName: "focusInspector"
                        width: trayFlick.width
                        spacing: 8

                        Flow {
                            width: parent.width
                            spacing: 8

                            Rectangle {
                                objectName: "searchThisArea"
                                width: findSimilarLabel.implicitWidth + 28
                                height: 34
                                radius: 6
                                color: findSimilarHit.containsMouse ? tokenBg3 : tokenAccentDim
                                border.color: tokenAccent
                                border.width: 1
                                Text {
                                    id: findSimilarLabel
                                    anchors.centerIn: parent
                                    text: "Find similar"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                }
                                MouseArea {
                                    id: findSimilarHit
                                    objectName: "similarAction"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Find similar"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.findSimilar()
                                }
                            }

                            Rectangle {
                                objectName: "nameThisArea"
                                visible: shellReady && shellApi.selectionOnFocus && !shellApi.identifyBusy
                                width: visible ? describeLabel.implicitWidth + 22 : 0
                                height: 34
                                radius: 6
                                color: describeHit.containsMouse ? tokenBg3 : "transparent"
                                Text {
                                    id: describeLabel
                                    anchors.centerIn: parent
                                    text: "Describe this area"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: describeHit
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Describe this area"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.nameSelection()
                                }
                            }

                            Rectangle {
                                objectName: "sameFaceDoor"
                                visible: {
                                    var boxes = focusBoxesSafe
                                    if (!boxes)
                                        return false
                                    for (var i = 0; i < boxes.length; i++) {
                                        if (boxes[i] && boxes[i].kind === "face")
                                            return true
                                    }
                                    return false
                                }
                                width: visible ? personLabel.implicitWidth + 22 : 0
                                height: 34
                                radius: 6
                                color: personHit.containsMouse ? tokenBg3 : "transparent"
                                Text {
                                    id: personLabel
                                    anchors.centerIn: parent
                                    text: "Find this person"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: personHit
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Find this person"
                                    Accessible.role: Accessible.Button
                                    onClicked: window.findThisPerson()
                                }
                            }

                            Rectangle {
                                id: focusMoreButton
                                objectName: "focusMoreButton"
                                width: moreLabel.implicitWidth + 22
                                height: 34
                                radius: 6
                                color: window.focusMoreOpen || moreHit.containsMouse ? tokenBg3 : "transparent"
                                Text {
                                    id: moreLabel
                                    anchors.centerIn: parent
                                    text: "More"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: moreHit
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "More search options"
                                    Accessible.role: Accessible.Button
                                    onClicked: window.focusMoreOpen = !window.focusMoreOpen
                                }
                            }

                            Rectangle {
                                objectName: "keepDiscoveryAction"
                                visible: shellReady && similarStateSafe === "ready" && similarCountSafe > 0
                                         && !shellApi.searchBusy
                                width: visible ? keepLabel.implicitWidth + 22 : 0
                                height: 34
                                radius: 6
                                color: keepHit.containsMouse ? tokenBg3 : "transparent"
                                Text {
                                    id: keepLabel
                                    anchors.centerIn: parent
                                    text: "Keep this find"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: keepHit
                                    objectName: "keepDiscoveryHit"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Keep this find"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.keepDiscovery()
                                }
                            }

                            Rectangle {
                                objectName: "backDiscoveryAction"
                                visible: shellReady && shellApi.canBackDiscovery
                                width: visible ? backResultsLabel.implicitWidth + 22 : 0
                                height: 34
                                radius: 6
                                color: backResultsHit.containsMouse ? tokenBg3 : "transparent"
                                Text {
                                    id: backResultsLabel
                                    anchors.centerIn: parent
                                    text: "Back to results"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 13
                                }
                                MouseArea {
                                    id: backResultsHit
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Back to results"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.backToDiscovery()
                                }
                            }
                        }

                        Column {
                            width: parent.width
                            spacing: 4

                            Rectangle {
                                width: parent.width
                                height: window.focusSearchRunning ? focusStatusRow.implicitHeight + 12 : focusStatusRow.implicitHeight
                                radius: 6
                                color: window.focusSearchRunning ? tokenBg2 : "transparent"

                                Row {
                                    id: focusStatusRow
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: window.focusSearchRunning ? 8 : 0
                                    anchors.rightMargin: window.focusSearchRunning ? 8 : 0
                                    spacing: 8

                                    Item {
                                        id: focusSearchSpinner
                                        objectName: "focusSearchSpinner"
                                        property bool running: window.focusSearchRunning && !(shellReady && shellApi.reducedMotion)
                                        visible: running
                                        width: running ? 16 : 0
                                        height: 32
                                        Item {
                                            anchors.centerIn: parent
                                            width: 16
                                            height: 16
                                            RotationAnimation on rotation {
                                                from: 0
                                                to: 360
                                                duration: 800
                                                loops: Animation.Infinite
                                                running: focusSearchSpinner.running
                                            }
                                            Rectangle {
                                                anchors.fill: parent
                                                radius: width / 2
                                                color: "transparent"
                                                border.width: 2
                                                border.color: Qt.rgba(tokenAccent.r, tokenAccent.g, tokenAccent.b, 0.35)
                                            }
                                            Rectangle {
                                                width: parent.width
                                                height: parent.height / 2
                                                radius: width / 2
                                                color: tokenAccent
                                            }
                                        }
                                    }
                                    Rectangle {
                                        id: focusSearchMark
                                        objectName: "focusSearchMark"
                                        width: visible ? 8 : 0
                                        height: 8
                                        radius: 4
                                        color: tokenAccent
                                        visible: window.focusSearchRunning && shellReady && shellApi.reducedMotion
                                    }
                                    Text {
                                        objectName: "focusSearchStatus"
                                        width: Math.max(120, parent.width - focusSearchSpinner.width - focusSearchMark.width - searchPhaseBadge.width - cancelSearch.width - 24)
                                        height: Math.max(18, implicitHeight)
                                        wrapMode: Text.WordWrap
                                        verticalAlignment: Text.AlignVCenter
                                        text: window.focusSearchTitle
                                        color: !window.focusSearchRunning && similarStateSafe === "error" ? tokenDanger : tokenText
                                        font.family: "Segoe UI"
                                        font.pixelSize: 13
                                        font.weight: window.focusSearchRunning ? Font.DemiBold : Font.Normal
                                    }
                                    Rectangle {
                                        id: searchPhaseBadge
                                        objectName: "searchPhaseBadge"
                                        visible: shellReady && shellApi.similarPhaseLabel !== "" && !shellApi.searchBusy
                                        height: 22
                                        width: visible ? phaseBadgeText.implicitWidth + 16 : 0
                                        radius: 11
                                        color: tokenBg3
                                        Text {
                                            id: phaseBadgeText
                                            anchors.centerIn: parent
                                            text: shellReady ? shellApi.similarPhaseLabel : ""
                                            color: tokenMuted
                                            font.family: "Segoe UI"
                                            font.pixelSize: 12
                                        }
                                    }
                                    Rectangle {
                                        id: cancelSearch
                                        objectName: "cancelSearch"
                                        visible: shellReady && (shellApi.searchBusy || shellApi.screenQueryInProgress)
                                        width: visible ? cancelLabel.implicitWidth + 20 : 0
                                        height: 32
                                        radius: 6
                                        color: "transparent"
                                        border.color: tokenDanger
                                        border.width: visible ? 1 : 0
                                        Text {
                                            id: cancelLabel
                                            anchors.centerIn: parent
                                            text: "Cancel search"
                                            color: tokenText
                                            font.family: "Segoe UI"
                                            font.pixelSize: 13
                                        }
                                        MouseArea {
                                            id: cancelSearchHit
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            Accessible.name: "Cancel search"
                                            Accessible.role: Accessible.Button
                                            onClicked: if (shellReady) shellApi.cancelSimilar()
                                        }
                                    }
                                }
                            }
                            Text {
                                objectName: "focusSearchHint"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: text !== ""
                                text: window.focusSearchDetail
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "similarNote"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: text !== "" && text !== window.focusSearchTitle
                                text: similarNoteSafe
                                color: !window.focusSearchRunning && similarStateSafe === "error" ? tokenDanger : tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "matchHonesty"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: shellReady && shellApi.similarCaution !== ""
                                text: shellReady ? shellApi.similarCaution : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "nameNote"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: shellReady && shellApi.nameNote !== "" && shellApi.nameNote !== window.focusSearchTitle
                                text: shellReady ? shellApi.nameNote : ""
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            Rectangle {
                                objectName: "nameConfidence"
                                visible: shellReady && shellApi.nameConfidenceLabel !== ""
                                height: visible ? 22 : 0
                                width: nameConfidenceText.implicitWidth + 16
                                radius: 11
                                color: tokenBg3
                                border.color: tokenAccent
                                border.width: 1
                                Text {
                                    id: nameConfidenceText
                                    anchors.centerIn: parent
                                    text: shellReady ? shellApi.nameConfidenceLabel : ""
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                            }
                            Text {
                                objectName: "selectionNote"
                                width: parent.width
                                visible: shellReady && shellApi.selectionNote !== ""
                                wrapMode: Text.WordWrap
                                text: shellReady ? shellApi.selectionNote : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "screenQueryProgress"
                                width: parent.width
                                visible: shellReady && shellApi.screenQueryInProgress
                                wrapMode: Text.WordWrap
                                text: shellReady ? shellApi.screenQueryProgressLabel : ""
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "resultText"
                                width: parent.width
                                visible: text !== ""
                                text: shellReady ? shell.resultText : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                                wrapMode: Text.WordWrap
                            }
                        }

                        Rectangle {
                            objectName: "installSuggestedModel"
                            visible: shellReady
                                     && shellApi.installSuggestionVisible
                                     && !shellApi.searchBusy
                                     && !shellApi.screenQueryInProgress
                            width: visible ? Math.min(parent.width, installSuggestedLabel.implicitWidth + 28) : 0
                            height: visible ? 32 : 0
                            radius: 6
                            color: installSuggestedModelHit.containsMouse ? tokenAccentDim : tokenBg2
                            border.color: tokenAccent
                            border.width: 1
                            Text {
                                id: installSuggestedLabel
                                anchors.centerIn: parent
                                text: shellReady ? shellApi.installSuggestionLabel : "Install required model"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: installSuggestedModelHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Install required model"
                                Accessible.role: Accessible.Button
                                onClicked: if (shellReady) shellApi.installSuggestedModel()
                            }
                        }

                        Column {
                            width: parent.width
                            spacing: 4
                            visible: advancedModeSafe
                            Text {
                                objectName: "searchQualityFocus"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: shellReady ? ("Quality: " + shellApi.searchQualityLabel) : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "searchTiming"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: shellReady && shellApi.searchTimingLabel !== ""
                                text: shellReady ? shellApi.searchTimingLabel : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "searchDoorLabel"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: shellReady && shellApi.searchDoorLabel !== ""
                                text: shellReady ? shellApi.searchDoorLabel : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "searchPhaseFocus"
                                width: parent.width
                                wrapMode: Text.WordWrap
                                visible: shellReady && shellApi.similarPhaseLabel !== ""
                                text: shellReady ? shellApi.similarPhaseLabel : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                            Text {
                                objectName: "retrievalDetail"
                                width: parent.width
                                visible: shellReady && shellApi.retrievalDetail !== ""
                                wrapMode: Text.WordWrap
                                text: shellReady ? shellApi.retrievalDetail : ""
                                color: tokenFaint
                                font.family: "Consolas"
                                font.pixelSize: 11
                            }
                            Rectangle {
                                objectName: "diagnosticsPanel"
                                width: parent.width
                                visible: advancedModeSafe
                                color: tokenBg
                                border.color: tokenBorder
                                border.width: 1
                                radius: 8
                                implicitHeight: diagnosticsText.implicitHeight + 14
                                Text {
                                    id: diagnosticsText
                                    anchors.fill: parent
                                    anchors.margins: 7
                                    text: shellReady ? shellApi.diagnosticsText : ""
                                    color: tokenMuted
                                    font.family: "Consolas"
                                    font.pixelSize: 11
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 8
                            visible: similarCountSafe > 0 || window.focusSearchRunning
                            Text {
                                text: {
                                    if (!shellReady)
                                        return "Similar regions"
                                    var door = shellApi.searchDoorLabel
                                    if (door === "Same face" || door === "Whole photo" || door === "Duplicates")
                                        return door
                                    return "Similar regions"
                                }
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            Text {
                                text: focusNameSafe !== "" ? ("in " + focusNameSafe) : ""
                                color: tokenFaint
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                                elide: Text.ElideMiddle
                                width: Math.max(0, parent.width - 180)
                            }
                        }

                        ListView {
                            id: matchStrip
                            objectName: "similarStrip"
                            width: parent.width
                            height: similarCountSafe > 0 ? 120 : 0
                            visible: height > 0
                            orientation: ListView.Horizontal
                            spacing: 10
                            clip: true
                            leftMargin: 2
                            rightMargin: 16
                            boundsBehavior: Flickable.StopAtBounds
                            model: similarModel
                            keyNavigationEnabled: true
                            activeFocusOnTab: true
                            cacheBuffer: 480
                            Accessible.name: "Matches"
                            Keys.onReturnPressed: if (shellReady) shellApi.openDiscoveryHit(shellApi.similarId(currentIndex))
                            Keys.onEnterPressed: if (shellReady) shellApi.openDiscoveryHit(shellApi.similarId(currentIndex))
                            Keys.onUpPressed: regionDrag.forceActiveFocus()

                            WheelHandler {
                                objectName: "similarStripWheel"
                                onWheel: function(event) {
                                    var delta = event.pixelDelta.x !== 0 ? event.pixelDelta.x : event.pixelDelta.y
                                    if (delta === 0)
                                        delta = event.angleDelta.x !== 0 ? event.angleDelta.x : event.angleDelta.y
                                    var maxX = Math.max(0, matchStrip.contentWidth - matchStrip.width)
                                    matchStrip.contentX = Math.max(0, Math.min(maxX, matchStrip.contentX - delta))
                                    event.accepted = true
                                }
                            }

                            delegate: Item {
                                width: 132
                                height: 120
                                objectName: "similarThumb"
                                readonly property bool openMatch: mediaId === focusIdSafe
                                readonly property bool keyed: matchStrip.activeFocus && matchStrip.currentIndex === index

                                Rectangle {
                                    id: thumbFrame
                                    anchors.top: parent.top
                                    width: 132
                                    height: 108
                                    color: tokenBg2
                                    radius: 4
                                    border.width: openMatch ? 2 : (keyed || thumbArea.containsMouse ? 1 : 0)
                                    border.color: tokenAccent

                                    Image {
                                        id: thumbImage
                                        anchors.fill: parent
                                        anchors.margins: 2
                                        source: shellReady ? shellApi.thumbFor(mediaId) : ""
                                        fillMode: Image.PreserveAspectFit
                                        asynchronous: true
                                        cache: true
                                    }

                                    Rectangle {
                                        objectName: "similarMatchBox"
                                        readonly property real frameW: thumbImage.paintedWidth > 1 ? thumbImage.paintedWidth : thumbImage.width
                                        readonly property real frameH: thumbImage.paintedHeight > 1 ? thumbImage.paintedHeight : thumbImage.height
                                        visible: matchW > 0.01 && matchH > 0.01 && frameW > 1 && frameH > 1
                                        x: thumbImage.x + (thumbImage.width - frameW) / 2 + matchX * frameW
                                        y: thumbImage.y + (thumbImage.height - frameH) / 2 + matchY * frameH
                                        width: Math.max(2, matchW * frameW)
                                        height: Math.max(2, matchH * frameH)
                                        color: Qt.rgba(tokenAccent.r, tokenAccent.g, tokenAccent.b, 0.28)
                                        border.color: tokenAccent
                                        border.width: 1
                                    }

                                    Text {
                                        anchors.right: parent.right
                                        anchors.bottom: parent.bottom
                                        anchors.margins: 4
                                        visible: advancedModeSafe
                                        text: score.toFixed(2)
                                        color: tokenText
                                        font.family: "Segoe UI"
                                        font.pixelSize: 10
                                    }

                                    MouseArea {
                                        id: thumbArea
                                        objectName: "similarThumbHit"
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            matchStrip.currentIndex = index
                                            if (shellReady)
                                                shellApi.openDiscoveryHit(mediaId)
                                        }
                                        Accessible.name: openMatch ? "Selected match" : "Open match"
                                    }
                                }

                                Rectangle {
                                    anchors.top: thumbFrame.bottom
                                    anchors.topMargin: 4
                                    width: openMatch ? parent.width : 0
                                    height: 3
                                    radius: 1
                                    color: tokenAccent
                                    visible: openMatch
                                }
                            }
                        }

                        Text {
                            objectName: "keptHeading"
                            width: parent.width
                            visible: shellReady && shellApi.keptCount > 0
                            text: "Kept finds"
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }

                        ListView {
                            objectName: "keptFinds"
                            width: parent.width
                            height: Math.min((shellReady ? shellApi.keptCount : 0) * 28, 84)
                            visible: height > 0
                            interactive: true
                            clip: true
                            model: shellReady ? shellApi.keptCount : 0
                            delegate: Rectangle {
                                width: focusTrayColumn.width
                                height: 28
                                radius: 4
                                color: keptHit.containsMouse ? tokenAccentDim : tokenBg
                                Text {
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    text: shellReady ? shellApi.keptLabel(index) : ""
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    verticalAlignment: Text.AlignVCenter
                                }
                                MouseArea {
                                    id: keptHit
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Open kept find"
                                    onClicked: if (shellReady) shellApi.openKept(index)
                                }
                            }
                        }
                    }
                }
            }

            Popup {
                id: focusMorePopup
                objectName: "focusMorePopup"
                parent: Overlay.overlay
                modal: false
                dim: false
                padding: 12
                width: 320
                height: Math.min(Math.max(moreColumn.implicitHeight + 24, 120), Math.min(460, Overlay.overlay.height - 16))
                closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
                visible: window.focusMoreOpen
                onClosed: window.focusMoreOpen = false
                function place() {
                    if (!visible)
                        return
                    var origin = focusMoreButton.mapToItem(Overlay.overlay, 0, 0)
                    x = Math.max(8, Math.min(origin.x, Overlay.overlay.width - width - 8))
                    var above = origin.y - height - 8
                    y = above >= 8 ? above : Math.max(8, Overlay.overlay.height - height - 8)
                }
                onOpened: Qt.callLater(place)
                onHeightChanged: if (visible) Qt.callLater(place)
                background: Rectangle {
                    color: tokenBg1
                    border.color: tokenBorder
                    border.width: 1
                    radius: 8
                }

                Flickable {
                    id: moreFlick
                    anchors.fill: parent
                    contentHeight: moreColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds

                    Column {
                        id: moreColumn
                        width: moreFlick.width
                        spacing: 8

                        Text {
                            width: parent.width
                            text: "Also search"
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                        Rectangle {
                            objectName: "wholePhoto"
                            width: parent.width
                            height: 32
                            radius: 6
                            color: wholePhotoHit.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Search the whole photo"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: wholePhotoHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Search the whole photo"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    window.focusMoreOpen = false
                                    if (shellReady)
                                        shellApi.findSimilarWhole()
                                }
                            }
                        }
                        Rectangle {
                            objectName: "duplicatesDoor"
                            width: parent.width
                            height: 32
                            radius: 6
                            color: duplicatesHit.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Find duplicates"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: duplicatesHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Find duplicates"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    window.focusMoreOpen = false
                                    if (shellReady)
                                        shellApi.scanDuplicates()
                                }
                            }
                        }
                        Rectangle {
                            objectName: "screenQueryAction"
                            width: parent.width
                            height: shellReady && shellApi.screenQueryAvailable && !shellApi.searchBusy ? 32 : 0
                            visible: height > 0
                            radius: 6
                            color: screenQueryHit.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Find this on my screen"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: screenQueryHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Find this on my screen"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    window.focusMoreOpen = false
                                    if (shellReady)
                                        shellApi.startScreenQuery()
                                }
                            }
                        }
                        Rectangle {
                            objectName: "screenQueryModeAction"
                            width: parent.width
                            height: shellReady && shellApi.screenQueryAvailable && !shellApi.screenQueryInProgress ? 32 : 0
                            visible: height > 0
                            radius: 6
                            color: screenQueryModeHit.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: shellReady ? shellApi.screenQueryModeLabel : "Screen mode"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: screenQueryModeHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Toggle screen query mode"
                                Accessible.role: Accessible.Button
                                onClicked: if (shellReady) shellApi.toggleScreenQueryMode()
                            }
                        }

                        Text {
                            width: parent.width
                            text: shellReady ? ("Quality: " + shellApi.searchQualityLabel) : "Quality"
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                        Row {
                            width: parent.width
                            spacing: 6
                            Rectangle {
                                width: (parent.width - 12) / 3
                                height: 28
                                radius: 6
                                color: shellReady && shellApi.searchQuality === "fast" ? tokenAccentDim : tokenBg2
                                border.color: shellReady && shellApi.searchQuality === "fast" ? tokenAccent : tokenBorder
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "Fast"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Fast search"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.setSearchQuality("fast")
                                }
                            }
                            Rectangle {
                                width: (parent.width - 12) / 3
                                height: 28
                                radius: 6
                                color: shellReady && shellApi.searchQuality === "balanced" ? tokenAccentDim : tokenBg2
                                border.color: shellReady && shellApi.searchQuality === "balanced" ? tokenAccent : tokenBorder
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "Balanced"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Balanced search"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.setSearchQuality("balanced")
                                }
                            }
                            Rectangle {
                                width: (parent.width - 12) / 3
                                height: 28
                                radius: 6
                                color: shellReady && shellApi.searchQuality === "max" ? tokenAccentDim : tokenBg2
                                border.color: shellReady && shellApi.searchQuality === "max" ? tokenAccent : tokenBorder
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "Max"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Max search"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.setSearchQuality("max")
                                }
                            }
                        }

                        Text {
                            objectName: "refineHint"
                            width: parent.width
                            wrapMode: Text.WordWrap
                            visible: shellReady && shellApi.selectionOnFocus
                            text: shellReady ? shellApi.refineHint : ""
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                        Row {
                            objectName: "refineModeRow"
                            width: parent.width
                            spacing: 6
                            visible: shellReady && shellApi.selectionOnFocus && !shellApi.searchBusy
                            Rectangle {
                                objectName: "refineSameLook"
                                width: (parent.width - 6) / 2
                                height: 28
                                radius: 6
                                color: shellReady && shellApi.refineMode === "look" ? tokenAccentDim : tokenBg2
                                border.color: shellReady && shellApi.refineMode === "look" ? tokenAccent : tokenBorder
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "Same look"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Same look"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.setRefineMode("look")
                                }
                            }
                            Rectangle {
                                objectName: "refineSameKind"
                                width: (parent.width - 6) / 2
                                height: 28
                                radius: 6
                                color: shellReady && shellApi.refineMode === "kind" ? tokenAccentDim : tokenBg2
                                border.color: shellReady && shellApi.refineMode === "kind" ? tokenAccent : tokenBorder
                                border.width: 1
                                Text {
                                    anchors.centerIn: parent
                                    text: "Same kind"
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: "Same kind"
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.setRefineMode("kind")
                                }
                            }
                        }
                        TextField {
                            objectName: "refineWord"
                            width: parent.width
                            visible: shellReady && shellApi.selectionOnFocus && !shellApi.searchBusy
                            placeholderText: "Add a word, like red"
                            text: shellReady ? shellApi.refineModifier : ""
                            color: tokenText
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            background: Rectangle {
                                color: tokenBg2
                                border.color: tokenBorder
                                border.width: 1
                                radius: 6
                            }
                            onEditingFinished: if (shellReady) shellApi.setRefineModifier(text)
                            onActiveFocusChanged: window.refineFieldActive = activeFocus
                        }
                        Text {
                            width: parent.width
                            visible: shellReady && shellApi.selectionOnFocus && shellApi.refineParts.length > 1
                            text: "Part of this area"
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                        }
                        Repeater {
                            model: shellReady ? shellApi.refineParts : []
                            delegate: Rectangle {
                                width: moreColumn.width
                                height: 26
                                visible: shellReady && shellApi.selectionOnFocus && (modelData.index !== -1 || shellApi.refineParts.length > 1)
                                radius: 6
                                color: modelData.selected ? tokenAccentDim : tokenBg2
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 12
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: modelData.label
                                    Accessible.role: Accessible.Button
                                    onClicked: if (shellReady) shellApi.setRefinePart(modelData.index)
                                }
                            }
                        }

                        Rectangle {
                            objectName: "showDayAction"
                            width: parent.width
                            height: 32
                            radius: 6
                            color: showDayHit.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Show this day"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: showDayHit
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Show this day"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    window.focusMoreOpen = false
                                    if (shellReady)
                                        shellApi.showDayAroundFocus()
                                }
                            }
                        }
                        Rectangle {
                            objectName: "reviewFaceGroupAction"
                            width: parent.width
                            height: shellReady && selectedObservationSafe !== "" && shellApi.canReviewFaceGroup ? 32 : 0
                            visible: height > 0
                            radius: 6
                            color: reviewGroupHit.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Review this group"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: reviewGroupHit
                                objectName: "reviewFaceGroupHit"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Review this group"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    window.focusMoreOpen = false
                                    if (shellReady)
                                        shellApi.reviewFaceGroup(selectedObservationSafe)
                                }
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: primaryModeSafe ? 32 : 0
                            visible: height > 0
                            radius: 6
                            color: askArea.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Ask about this photo"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: askArea
                                objectName: "askPhoto"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Ask about this photo"
                                Accessible.role: Accessible.Button
                                onClicked: {
                                    window.focusMoreOpen = false
                                    if (shellReady)
                                        shellApi.askPhoto()
                                }
                            }
                        }
                        Rectangle {
                            width: parent.width
                            height: advancedModeSafe ? 32 : 0
                            visible: height > 0
                            radius: 6
                            color: statusArea.containsMouse ? tokenBg3 : tokenBg2
                            Text {
                                anchors.centerIn: parent
                                text: "Run diagnostics status"
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                            }
                            MouseArea {
                                id: statusArea
                                objectName: "runStatus"
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                Accessible.name: "Run diagnostics status"
                                Accessible.role: Accessible.Button
                                onClicked: if (shellReady) shellApi.submitCommand("status")
                            }
                        }
                    }
                }
            }

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: photoViewport.verticalCenter
                anchors.leftMargin: 14
                z: 5
                text: "‹"
                color: tokenText
                font.pixelSize: 28
                opacity: prevArea.containsMouse ? 1 : 0.35
                MouseArea {
                    id: prevArea
                    anchors.fill: parent
                    anchors.margins: -12
                    hoverEnabled: true
                    onClicked: if (shellReady) shellApi.focusPrev()
                }
            }
            Text {
                anchors.right: parent.right
                anchors.verticalCenter: photoViewport.verticalCenter
                anchors.rightMargin: window.focusDetailsOpen ? 292 : 14
                z: 5
                text: "›"
                color: tokenText
                font.pixelSize: 28
                opacity: nextArea.containsMouse ? 1 : 0.35
                MouseArea {
                    id: nextArea
                    anchors.fill: parent
                    anchors.margins: -12
                    hoverEnabled: true
                    onClicked: if (shellReady) shellApi.focusNext()
                }
            }

            Connections {
                target: shellApi
                function onFocusChanged() {
                    regionDrag.hasRect = false
                }
            }
        }
    }

    Rectangle {
        objectName: "installSuggestedModelStage"
        z: 40
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 28
        width: 240
        height: 36
        visible: shellReady
                 && !focusActive
                 && shellApi.installSuggestionVisible
                 && !shellApi.searchBusy
                 && !shellApi.screenQueryInProgress
        radius: 6
        color: installSuggestedModelStageHit.containsMouse ? tokenAccentDim : tokenBg2
        border.color: tokenAccent
        border.width: 1
        Text {
            anchors.centerIn: parent
            text: shellReady ? shellApi.installSuggestionLabel : "Install required model"
            color: tokenText
            font.family: "Segoe UI"
            font.pixelSize: 13
        }
        MouseArea {
            id: installSuggestedModelStageHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            Accessible.name: "Install required model"
            Accessible.role: Accessible.Button
            onClicked: if (shellReady) shellApi.installSuggestedModel()
        }
    }

    Rectangle {
        id: scanChip
        objectName: "scanChip"
        visible: jobRunning
        z: 45
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 14
        width: Math.max(scanChipText.implicitWidth, scanTimingText.implicitWidth) + 22
        height: scanTimingText.text !== "" ? 40 : 28
        radius: 14
        color: tokenBg1
        border.color: tokenAccent
        border.width: 1
        property string label: {
            if (!shellReady)
                return ""
            var prefix = "Scanning"
            if (jobStateSafe === "paused")
                prefix = "Paused"
            else if (jobStateSafe === "cancelling")
                prefix = "Stopping"
            var total = shellApi.jobTotal > 0 ? String(shellApi.jobTotal) : "?"
            return prefix + " · " + shellApi.jobCurrent + " / " + total
        }

        Text {
            id: scanChipText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: scanTimingText.text !== "" ? 4 : 7
            text: scanChip.label
            color: tokenText
            font.family: "Segoe UI"
            font.pixelSize: 12
        }
        Text {
            id: scanTimingText
            objectName: "scanTiming"
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: scanChipText.bottom
            visible: text !== ""
            text: shellReady ? shellApi.jobTiming : ""
            color: tokenMuted
            font.family: "Segoe UI"
            font.pixelSize: 11
        }
        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            Accessible.name: scanChip.label
            Accessible.role: Accessible.Button
            onClicked: if (shellReady) shellApi.openTasks()
        }
    }

    Item {
        id: taskTray
        objectName: "taskTray"
        z: 60
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 16
        width: tasksOpenSafe ? 320 : taskPill.width
        height: taskPill.height + (tasksOpenSafe ? taskSheet.height + 8 : 0)

        Rectangle {
            id: taskSheet
            objectName: "taskSheet"
            visible: tasksOpenSafe
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: taskPill.top
            anchors.bottomMargin: 8
            height: Math.min(taskSheetFlick.contentHeight + 28, Math.max(120, window.height * 0.55))
            radius: 12
            color: tokenBg1
            border.color: tokenBorder
            border.width: 1
            clip: true

            Flickable {
                id: taskSheetFlick
                anchors.fill: parent
                anchors.margins: 14
                contentHeight: taskSheetColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: taskSheetColumn
                    width: taskSheetFlick.width
                    spacing: 12

                    Item {
                        width: parent.width
                        height: 22
                        Text {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Library work"
                            color: tokenText
                            font.family: "Segoe UI"
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                        Text {
                            objectName: "closeTasks"
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Close"
                            color: closeTasksArea.containsMouse ? tokenText : tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            MouseArea {
                                id: closeTasksArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.closeTasks()
                            }
                        }
                    }

                    Text {
                        objectName: "taskSummary"
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: taskSummarySafe
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    Text {
                        width: parent.width
                        wrapMode: Text.WordWrap
                        visible: text !== ""
                        text: shellReady && jobRunning ? shellApi.jobTiming : ""
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    Repeater {
                        model: taskRowsSafe
                        delegate: Column {
                            id: taskRow
                            width: taskSheetColumn.width
                            spacing: 4
                            property var task: modelData
                            visible: !(task && task.id === "quiet")
                            height: visible ? implicitHeight : 0

                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: taskRow.task && taskRow.task.title ? taskRow.task.title : ""
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: taskRow.task && taskRow.task.detail ? taskRow.task.detail : ""
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                            }
                        }
                    }

                    Row {
                        spacing: 14
                        Text {
                            objectName: "pauseJob"
                            visible: window.taskHas("pause")
                            text: "Pause"
                            color: pauseJobArea.containsMouse ? tokenText : tokenAccent
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            MouseArea {
                                id: pauseJobArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.runTaskAction("pause")
                            }
                        }
                        Text {
                            objectName: "resumeJobBand"
                            visible: window.taskHas("resume")
                            text: "Resume"
                            color: resumeJobArea.containsMouse ? tokenText : tokenAccent
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            MouseArea {
                                id: resumeJobArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.runTaskAction("resume")
                            }
                        }
                        Text {
                            objectName: "cancelJob"
                            visible: window.taskHas("cancel")
                            text: "Cancel"
                            color: cancelJobArea.containsMouse ? tokenText : tokenDanger
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            MouseArea {
                                id: cancelJobArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.runTaskAction("cancel")
                            }
                        }
                        Text {
                            objectName: "taskAction_cancel-search"
                            visible: window.taskHas("cancel-search")
                            text: "Cancel search"
                            color: cancelSearchArea.containsMouse ? tokenText : tokenAccent
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            MouseArea {
                                id: cancelSearchArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.runTaskAction("cancel-search")
                            }
                        }
                        Text {
                            objectName: "taskAction_rescan"
                            visible: window.taskHas("rescan")
                            text: window.taskActionLabel("rescan")
                            color: rescanTaskArea.containsMouse ? tokenText : tokenAccent
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            MouseArea {
                                id: rescanTaskArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.runTaskAction("rescan")
                            }
                        }
                        Text {
                            objectName: "taskAction_add-folder"
                            visible: window.taskHas("add-folder")
                            text: window.taskActionLabel("add-folder")
                            color: addFolderTaskArea.containsMouse ? tokenText : tokenAccent
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            MouseArea {
                                id: addFolderTaskArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.runTaskAction("add-folder")
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: taskPill
            objectName: "taskPill"
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: taskPillLabel.implicitWidth + (taskCountDot.visible ? 36 : 22)
            height: 32
            radius: 16
            color: taskPillArea.containsMouse ? tokenBg2 : tokenBg1
            border.color: (shellReady && shellApi.taskCount > 0) ? tokenAccent : tokenBorder
            border.width: 1

            Rectangle {
                id: taskCountDot
                visible: shellReady && shellApi.taskCount > 0
                anchors.left: parent.left
                anchors.leftMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                width: 8
                height: 8
                radius: 4
                color: tokenAccent
            }

            Text {
                id: taskPillLabel
                anchors.verticalCenter: parent.verticalCenter
                anchors.right: parent.right
                anchors.rightMargin: 12
                text: taskLabelSafe
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.weight: Font.DemiBold
                font.capitalization: Font.AllUppercase
            }
            MouseArea {
                id: taskPillArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                Accessible.name: taskSummarySafe || "Library work"
                Accessible.role: Accessible.Button
                onClicked: if (shellReady) shellApi.toggleTasks()
            }
        }
    }
}
