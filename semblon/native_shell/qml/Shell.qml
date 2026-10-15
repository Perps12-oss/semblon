import QtQuick
import QtQuick.Controls
import QtQuick.Window
import QtMultimedia

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
    readonly property string lensLabelSafe: shellReady ? shellApi.lensLabel : ""
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
    readonly property bool activityOpenSafe: shellReady && shellApi.activityOpen
    readonly property var activityRowsSafe: shellReady ? shellApi.activityRows : []
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
    readonly property var primarySettingCalls: ["cycleDensity", "libraryHealth", "showActivity", "modePeople", "modeText", "rescan", "resetDefaults"]
    readonly property var primarySettingLabels: ["Density", "Library health", "Activity", "Search people", "Search text", "Rescan", "Reset defaults"]
    readonly property var advancedSettingCalls: ["scanDuplicates", "showCapabilities", "gpuAuto", "gpuOff", "namedItems", "knowledgePack", "installModel"]
    readonly property var advancedSettingLabels: ["Duplicates", "Capabilities", "GPU auto", "GPU off", "Named items", "Knowledge pack", "Install model"]
    font.family: "Segoe UI"

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
        else if (call === "rescan") shellApi.rescanFolder()
        else if (call === "namedItems") shellApi.openNamedItems()
        else if (call === "knowledgePack") shellApi.chooseKnowledgePack()
        else if (call === "installModel") shellApi.chooseModelInstall()
        else if (call === "resetDefaults") shellApi.resetDefaults()
    }

    function bindNav(item, navId, navLabel, navIcon, navCall) {
        item.navId = navId
        item.navLabel = navLabel
        item.navIcon = navIcon
        item.navCall = navCall
    }

    Shortcut {
        sequences: [StandardKey.Cancel, "Escape"]
        onActivated: if (shellReady) shellApi.escape()
    }
    Shortcut {
        sequence: "Right"
        enabled: focusActive
        onActivated: if (shellReady) shellApi.focusNext()
    }
    Shortcut {
        sequence: "Left"
        enabled: focusActive
        onActivated: if (shellReady) shellApi.focusPrev()
    }
    Shortcut {
        sequence: "Return"
        enabled: !focusActive && !emptySafe
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
        sequence: "Ctrl+,"
        onActivated: if (shellReady) shellApi.toggleSettings()
    }
    Shortcut {
        sequence: "S"
        enabled: focusActive && !commandField.activeFocus && !searchField.activeFocus
        onActivated: if (shellReady) shellApi.findSimilarWhole()
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

    // Collapsible navigation sidebar. Replaces the former top rail.
    Rectangle {
        id: navSidebar
        objectName: "navSidebar"
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: sidebarCollapsed ? 56 : 228
        color: tokenBg1
        z: 10

        Behavior on width {
            NumberAnimation { duration: motion; easing.type: Easing.OutCubic }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 1
            color: tokenBorder
        }

        Column {
            id: sidebarColumn
            anchors.fill: parent
            anchors.margins: sidebarCollapsed ? 8 : 14
            spacing: 4

            // Brand + collapse
            Item {
                width: parent.width
                height: 36

                Text {
                    visible: !sidebarCollapsed
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Semblon"
                    color: tokenText
                    font.family: "Segoe UI Variable"
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
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
                            function onSidebarCollapsedChanged() { requestPaint() }
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
                    anchors.fill: parent
                    radius: 8
                    color: navArea.containsMouse ? tokenBg3 : "transparent"
                    objectName: navId === "people" ? "peopleButton" :
                                navId === "settings" ? "settingsButton" : ""
                    onNavIconChanged: navIconCanvas.requestPaint()

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: sidebarCollapsed ? 6 : 8
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 12

                        Canvas {
                            id: navIconCanvas
                            width: 18
                            height: 18
                            onPaint: {
                                var ctx = getContext("2d")
                                ctx.reset()
                                ctx.strokeStyle = navArea.containsMouse ? tokenText : tokenMuted
                                ctx.lineWidth = 1.4
                                ctx.lineCap = "round"
                                ctx.lineJoin = "round"
                                var ic = navIcon
                                if (ic === "grid") {
                                    ctx.strokeRect(2, 2, 6, 6)
                                    ctx.strokeRect(10, 2, 6, 6)
                                    ctx.strokeRect(2, 10, 6, 6)
                                    ctx.strokeRect(10, 10, 6, 6)
                                } else if (ic === "people") {
                                    ctx.beginPath()
                                    ctx.arc(9, 6, 3, 0, 6.28)
                                    ctx.stroke()
                                    ctx.beginPath()
                                    ctx.moveTo(3, 16)
                                    ctx.quadraticCurveTo(9, 11, 15, 16)
                                    ctx.stroke()
                                } else if (ic === "search") {
                                    ctx.beginPath()
                                    ctx.arc(8, 8, 5, 0, 6.28)
                                    ctx.stroke()
                                    ctx.beginPath()
                                    ctx.moveTo(12, 12)
                                    ctx.lineTo(16, 16)
                                    ctx.stroke()
                                } else if (ic === "plus") {
                                    ctx.beginPath()
                                    ctx.moveTo(9, 3); ctx.lineTo(9, 15)
                                    ctx.moveTo(3, 9); ctx.lineTo(15, 9)
                                    ctx.stroke()
                                } else if (ic === "gear") {
                                    ctx.beginPath()
                                    ctx.arc(9, 9, 4, 0, 6.28)
                                    ctx.stroke()
                                    ctx.beginPath()
                                    ctx.arc(9, 9, 7, 0, 6.28)
                                    ctx.stroke()
                                }
                            }
                            Component.onCompleted: requestPaint()
                        }

                        Text {
                            visible: !sidebarCollapsed
                            text: navLabel
                            color: navArea.containsMouse ? tokenText : tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 13
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
                            if (c === "wordmark") shellApi.wordmark()
                            else if (c === "openPeople") shellApi.openPeople()
                            else if (c === "focusSearch") {
                                if (primaryModeSafe) searchField.forceActiveFocus()
                                else commandField.forceActiveFocus()
                            }
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
                onLoaded: window.bindNav(item, "library", "Library", "grid", "wordmark")
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
                onLoaded: window.bindNav(item, "search", "Search", "search", "focusSearch")
            }
            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "add", "Add folder", "plus", "addFolder")
            }
            Loader {
                width: parent.width
                height: 36
                sourceComponent: navEntry
                onLoaded: window.bindNav(item, "settings", "Settings", "gear", "toggleSettings")
            }

            Item { width: 1; height: 12 }

            // Search field (expanded only)
            Rectangle {
                visible: !sidebarCollapsed
                width: parent.width
                height: 32
                radius: 8
                color: tokenBg2
                border.color: (searchField.activeFocus || commandField.activeFocus) ? tokenAccent : tokenBorder
                border.width: 1

                TextField {
                    id: searchField
                    objectName: "searchField"
                    visible: primaryModeSafe
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    placeholderText: "Search memory"
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
                    visible: advancedModeSafe
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    verticalAlignment: TextInput.AlignVCenter
                    placeholderText: "Command: people, status"
                    placeholderTextColor: tokenFaint
                    color: tokenText
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    background: Item {}
                    selectByMouse: true
                    onAccepted: if (shellReady) shellApi.submitCommand(text)
                }
            }

            Item { width: 1; height: 8; visible: !sidebarCollapsed }

            // Atmosphere (expanded)
            ComboBox {
                id: atmospherePicker
                objectName: "atmospherePicker"
                visible: !sidebarCollapsed
                width: parent.width
                model: shellReady ? shellApi.atmosphereChoices : []
                textRole: "label"
                displayText: (currentIndex >= 0 && model.length > currentIndex) ? model[currentIndex].label : "Atmosphere"
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

            Item { width: 1; height: 20 }

            // Mode + job at bottom — use a bottom-anchored column instead
        }

        // Bottom section (mode + job)
        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: sidebarCollapsed ? 8 : 14
            spacing: 6

            // Job indicator
            Row {
                visible: jobRunning
                spacing: 8
                anchors.horizontalCenter: parent.horizontalCenter

                Item {
                    width: 14
                    height: 14
                    RotationAnimation on rotation {
                        running: shellReady && jobRunning && !shellApi.reducedMotion
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
                    text: jobLabelSafe
                    color: tokenMuted
                    font.pixelSize: 11
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Primary / Advanced
            Rectangle {
                objectName: "primaryModeButton"
                width: parent.width
                height: 28
                radius: 6
                visible: !sidebarCollapsed
                color: primaryModeSafe ? tokenAccentDim : "transparent"
                border.color: primaryModeSafe ? tokenAccent : tokenBorder
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "Primary"
                    color: primaryModeSafe ? tokenText : tokenMuted
                    font.pixelSize: 12
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.setMode("primary")
                }
            }
            Rectangle {
                objectName: "advancedModeButton"
                width: parent.width
                height: 28
                radius: 6
                visible: !sidebarCollapsed
                color: advancedModeSafe ? tokenAccentDim : "transparent"
                border.color: advancedModeSafe ? tokenAccent : tokenBorder
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "Advanced"
                    color: advancedModeSafe ? tokenText : tokenMuted
                    font.pixelSize: 12
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.setMode("advanced")
                }
            }

            // Collapsed mode icons
            Item {
                visible: sidebarCollapsed
                width: parent.width
                height: 28
                Text {
                    anchors.centerIn: parent
                    text: primaryModeSafe ? "P" : "A"
                    color: tokenAccent
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.setMode(primaryModeSafe ? "advanced" : "primary")
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

        Row {
            id: jobBand
            objectName: "jobBand"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 28
            anchors.topMargin: 8
            spacing: 16
            z: 2
            visible: shellReady && (jobRunning || shellApi.surfaceState === "error" || shellApi.surfaceState === "unavailable" || shellApi.surfaceState === "loading")

            Text {
                objectName: "surfaceState"
                text: {
                    if (!shellReady)
                        return ""
                    if (jobRunning)
                        return jobLabelSafe || "Processing"
                    return shellApi.noticeText || (shellApi.surfaceState === "loading" ? "Working…" : "Something went wrong. Try again.")
                }
                color: shellReady && !jobRunning && shellApi.surfaceState === "error" ? tokenDanger : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Text {
                objectName: "pauseJob"
                visible: jobRunning && jobStateSafe !== "paused"
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
                    onClicked: if (shellReady) shellApi.pauseJob()
                }
            }

            Text {
                objectName: "resumeJobBand"
                visible: jobRunning && jobStateSafe === "paused"
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
                    onClicked: if (shellReady) shellApi.resumeJob()
                }
            }

            Text {
                objectName: "cancelJob"
                visible: jobRunning
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
                    onClicked: if (shellReady) shellApi.cancelJob()
                }
            }
        }

        Rectangle {
            objectName: "activitySheet"
            anchors.right: archiveSidebar.visible ? archiveSidebar.left : parent.right
            anchors.top: parent.top
            anchors.topMargin: 16
            anchors.rightMargin: archiveSidebar.visible ? 12 : 16
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
                    text: shellReady ? (shellApi.noticeText || "Nothing processed yet.") : ""
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
            anchors.right: archiveSidebar.visible ? archiveSidebar.left : parent.right
            anchors.top: parent.top
            anchors.topMargin: 16
            anchors.rightMargin: archiveSidebar.visible ? 12 : 16
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
                    font.pixelSize: 16
                    font.family: "Segoe UI"
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: shellReady ? shellApi.searchModeLabel : ""
                    color: tokenMuted
                    font.pixelSize: 12
                    font.family: "Segoe UI"
                }
                Repeater {
                    objectName: "primarySettingsRepeater"
                    model: 7
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
                        font.pixelSize: 22
                        font.family: "Segoe UI Variable"
                        font.weight: Font.DemiBold
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
                        color: tokenReview
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        objectName: "peopleEmpty"
                        visible: shellReady && shell.peopleEmpty
                        text: "No groups yet."
                        color: tokenMuted
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
                                    text: "Groups"
                                    color: tokenText
                                    font.pixelSize: 16
                                    font.family: "Segoe UI"
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
                                                : tokenBg3
                                        border.color: named
                                                ? ((shellReady && shell.selectedSubject === subject) ? tokenAccent : tokenBorder)
                                                : tokenReview
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
                                                    text: faceCount + (faceCount === 1 ? " face" : " faces")
                                                    color: tokenMuted
                                                    font.pixelSize: 12
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
                                            text: selectedTitleSafe !== "" ? selectedTitleSafe : "Select a group"
                                                                                        color: tokenText
                                            font.pixelSize: 20
                                            font.family: "Segoe UI Variable"
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                              text: shellReady && shell.selectedSubject !== ""
                                                  ? (selectedCountSafe + (selectedCountSafe === 1 ? " face" : " faces"))
                                                  : "Choose a group to review evidence, merge, name, note, or split faces."
                                            color: tokenMuted
                                            font.pixelSize: 13
                                            wrapMode: Text.WordWrap
                                        }
                                    }

                                    Text {
                                        objectName: "peopleEvidence"
                                        visible: shellReady && shell.evidenceId !== ""
                                        text: "Open evidence"
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

        ContextSidebar {
            id: archiveSidebar
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: 12
            anchors.rightMargin: 12
            anchors.bottomMargin: 12
            width: Math.min(280, Math.max(220, Math.floor(parent.width * 0.2)))
            visible: !emptySafe && !peopleVisible && !focusActive
            z: 2
            shellApi: window.shellApi
            shellReady: window.shellReady
            advancedMode: window.advancedModeSafe
            tokenBg1: window.tokenBg1
            tokenBg2: window.tokenBg2
            tokenAccent: window.tokenAccent
            tokenText: window.tokenText
            tokenMuted: window.tokenMuted
            tokenFaint: window.tokenFaint
            tokenBorder: window.tokenBorder
            motion: window.motion
        }

        TimelineLandscape {
            id: timelineHero
            anchors.left: parent.left
            anchors.right: archiveSidebar.visible ? archiveSidebar.left : parent.right
            anchors.top: parent.top
            anchors.leftMargin: 22
            anchors.rightMargin: archiveSidebar.visible ? 8 : 22
            anchors.topMargin: 12
            visible: !emptySafe && !peopleVisible && !focusActive
            z: 2
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

        MemoryCalendar {
            id: memoryCalendar
            anchors.left: timelineHero.left
            anchors.right: timelineHero.right
            anchors.top: timelineHero.bottom
            anchors.topMargin: 8
            height: Math.max(260, Math.min(420, Math.floor((parent.height - timelineHero.height - 120) * 0.52)))
            visible: !emptySafe && !peopleVisible && !focusActive
            z: 2
            shellApi: window.shellApi
            shellReady: window.shellReady
            cells: window.shellReady ? window.shellApi.calendarCells : []
            title: window.shellReady ? window.shellApi.calendarTitle : ""
            scopeKind: window.shellReady ? window.shellApi.scopeKind : ""
            scopeLabel: window.shellReady ? window.shellApi.scopeLabel : ""
            tokenBg: window.tokenBg
            tokenBg1: window.tokenBg1
            tokenBg2: window.tokenBg2
            tokenAccent: window.tokenAccent
            tokenAccentDim: window.tokenAccentDim
            tokenText: window.tokenText
            tokenMuted: window.tokenMuted
            tokenFaint: window.tokenFaint
            tokenBorder: window.tokenBorder
            motion: window.motion
            onDayClicked: (day) => { if (window.shellReady) window.shellApi.selectDay(day) }
            onPrevMonth: { if (window.shellReady) window.shellApi.calendarPrevMonth() }
            onNextMonth: { if (window.shellReady) window.shellApi.calendarNextMonth() }
            onGoHome: { if (window.shellReady) window.shellApi.calendarGoHome() }
        }

        Text {
            id: stickyHeader
            objectName: "stickyHeader"
            anchors.left: timelineHero.left
            anchors.right: timelineHero.right
            anchors.top: memoryCalendar.bottom
            anchors.topMargin: 8
            visible: !emptySafe && !peopleVisible && !focusActive && fieldSectionsActiveSafe && stickyHeadingSafe !== ""
            z: 2
            text: stickyHeadingSafe
            color: tokenText
            font.family: "Segoe UI"
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }

        Text {
            id: zeroResultFilter
            objectName: "zeroResultFilter"
            anchors.left: timelineHero.left
            anchors.right: timelineHero.right
            anchors.top: stickyHeader.visible ? stickyHeader.bottom : memoryCalendar.bottom
            anchors.topMargin: 12
            visible: !emptySafe && !peopleVisible && !focusActive && timeScopeActiveSafe && grid.count === 0
            z: 2
            text: "No media found for this selection. Clear Filter"
            color: tokenAccent
            font.family: "Segoe UI"
            font.pixelSize: 13
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: if (shellReady) shellApi.clearScope()
            }
        }

        ListView {
            id: fieldSectionsView
            objectName: "fieldSections"
            anchors.left: parent.left
            anchors.right: archiveSidebar.visible ? archiveSidebar.left : parent.right
            anchors.top: zeroResultFilter.visible
                ? zeroResultFilter.bottom
                : (stickyHeader.visible ? stickyHeader.bottom : memoryCalendar.bottom)
            anchors.bottom: parent.bottom
            anchors.leftMargin: 22
            anchors.rightMargin: archiveSidebar.visible ? 8 : 22
            anchors.topMargin: 8
            anchors.bottomMargin: 12
            visible: !emptySafe && fieldSectionsActiveSafe
            opacity: !focusActive ? 1 : 0
            clip: true
            spacing: 14
            boundsBehavior: Flickable.StopAtBounds
            model: shellReady ? shellApi.fieldSections : []
            enabled: !focusActive
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            delegate: Column {
                id: sectionCol
                width: fieldSectionsView.width
                spacing: 6
                property var section: modelData
                property string sectionDay: section ? String(section.day) : ""

                Text {
                    objectName: "fieldSection_" + sectionCol.sectionDay
                    width: parent.width
                    text: section && section.label ? section.label : sectionCol.sectionDay
                    color: tokenText
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    Accessible.name: text
                }

                Flow {
                    width: parent.width
                    spacing: 0
                    Repeater {
                        model: section && section.mediaIds ? section.mediaIds : []
                        delegate: Item {
                            width: shellReady ? shellApi.cellSize : 160
                            height: shellReady ? shellApi.cellSize : 160

                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: 6
                                color: tokenBg2
                                radius: 2

                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    source: "image://archive/t/" + modelData
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    color: "transparent"
                                    border.width: sectionTile.containsMouse ? 1 : 0
                                    border.color: tokenAccent
                                    radius: 2
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
                    if (!focusActive && fieldSectionsActiveSafe)
                        fieldSectionsView.contentY = 0
                }
            }
        }

        GridView {
            id: grid
            objectName: "fieldGrid"
            anchors.left: parent.left
            anchors.right: archiveSidebar.visible ? archiveSidebar.left : parent.right
            anchors.top: zeroResultFilter.visible
                ? zeroResultFilter.bottom
                : (stickyHeader.visible ? stickyHeader.bottom : memoryCalendar.bottom)
            anchors.bottom: parent.bottom
            anchors.leftMargin: 22
            anchors.rightMargin: archiveSidebar.visible ? 8 : 22
            anchors.topMargin: 8
            anchors.bottomMargin: 12
            visible: !emptySafe && !fieldSectionsActiveSafe
            opacity: !focusActive ? 1 : 0
            cellWidth: shellReady ? shellApi.cellSize : 160
            cellHeight: shellReady ? shellApi.cellSize : 160
            cacheBuffer: 400
            boundsBehavior: Flickable.StopAtBounds
            model: archiveModel
            currentIndex: 0
            enabled: !focusActive && !fieldSectionsActiveSafe
            keyNavigationEnabled: !focusActive && !fieldSectionsActiveSafe
            highlightFollowsCurrentItem: false
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            delegate: Item {
                width: grid.cellWidth
                height: grid.cellHeight

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 6
                    color: tokenBg2
                    radius: 2

                    Image {
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

                    Rectangle {
                        anchors.fill: parent
                        color: "transparent"
                        border.width: tile.containsMouse || grid.currentIndex === index ? 1 : 0
                        border.color: grid.currentIndex === index ? tokenAccent : tokenBorder
                        radius: 2
                    }

                    MouseArea {
                        id: tile
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            if (!shellReady)
                                return
                            grid.currentIndex = index
                            shellApi.setScroll(grid.contentY)
                            if (kind === "video")
                                return
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
                    if (!focusActive)
                        grid.contentY = 0
                }
            }
        }

        Column {
            objectName: "emptyState"
            visible: emptySafe
            anchors.centerIn: parent
            spacing: 14
            width: 820

            Text {
                width: parent.width
                text: "Explore your local photo memory"
                color: tokenText
                font.family: "Segoe UI Variable"
                font.pixelSize: 30
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
            }
            Text {
                width: parent.width
                text: jobRunning
                      ? "Adding your folder. The library will unlock here as media is indexed."
                      : "Semblon keeps your originals where they are, then helps you browse, review, search, and understand what is in your archive."
                                      color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 15
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
            }

            Text {
                objectName: "emptyStatus"
                width: parent.width
                visible: jobLabelSafe !== "" || canResumeSafe
                text: jobLabelSafe === "Last add failed" ? "The last add didn't finish. Try again or choose another folder."
                      : (canResumeSafe ? "The last add was stopped. Resume it or choose another folder." : jobLabelSafe)
                                      color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
                horizontalAlignment: Text.AlignHCenter
            }

            Grid {
                columns: 4
                columnSpacing: 12
                rowSpacing: 12
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width

                Rectangle {
                    objectName: "archiveCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: tokenBg1
                    border.color: tokenBorder
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Archive"; color: tokenText; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Browse your local library"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle {
                    objectName: "peopleCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: tokenBg1
                    border.color: tokenBorder
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "People"; color: tokenText; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Review groups with human decisions"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle {
                    objectName: "searchCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: tokenBg1
                    border.color: tokenBorder
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Search"; color: tokenText; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Find faces, people, and media"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle {
                    objectName: "lensCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: tokenBg1
                    border.color: tokenBorder
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Ask photo"; color: tokenText; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Read, describe, and inspect visual context"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }
            }

            Item { width: 1; height: 8 }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: addLabel.implicitWidth + 36
                height: 40
                radius: 8
                color: addArea.containsMouse ? tokenAccentDim : tokenBg2
                border.color: tokenAccent
                border.width: 1
                visible: !jobRunning
                Text {
                    id: addLabel
                    anchors.centerIn: parent
                    text: "Add a folder"
                    color: tokenText
                    font.family: "Segoe UI"
                    font.pixelSize: 14
                }
                MouseArea {
                    id: addArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.addFolder()
                }
            }
            Rectangle {
                objectName: "emptyResume"
                anchors.horizontalCenter: parent.horizontalCenter
                width: resumeEmptyLabel.implicitWidth + 36
                height: 40
                radius: 8
                color: resumeEmptyArea.containsMouse ? tokenAccentDim : tokenBg2
                border.color: tokenBorder
                border.width: 1
                visible: canResumeSafe && !jobRunning
                Text {
                    id: resumeEmptyLabel
                    objectName: "resumeJob"
                    anchors.centerIn: parent
                    text: jobLabelSafe === "Last add failed" ? "Try again" : "Resume"
                    color: tokenText
                    font.family: "Segoe UI"
                    font.pixelSize: 14
                }
                MouseArea {
                    id: resumeEmptyArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.resumeJob()
                }
            }
        }

        Item {
            id: focusLayer
            objectName: "focusLayer"
            anchors.fill: parent
            visible: focusActive
            opacity: focusActive ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            Rectangle {
                anchors.fill: parent
                color: tokenBg
            }

            Image {
                id: photo
                anchors.fill: parent
                anchors.margins: 48
                visible: focusKindSafe !== "video"
                source: (focusActive && focusKindSafe !== "video")
                        ? ("image://archive/f/" + focusIdSafe) : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
            }

            Item {
                id: observationLayer
                objectName: "observationLayer"
                anchors.fill: photo
                visible: focusKindSafe !== "video" && photo.paintedWidth > 0

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
            }

            MouseArea {
                id: regionDrag
                objectName: "regionDrag"
                anchors.fill: photo
                enabled: focusKindSafe !== "video" && photo.paintedWidth > 0
                z: 2
                property real rx: 0
                property real ry: 0
                property real rw: 0
                property real rh: 0
                property bool hasRect: false
                property real x0: 0
                property real y0: 0
                property bool dragging: false

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

                function hitObservation(px, py) {
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
                    if (pw <= 1 || ph <= 1)
                        return ""
                    for (var i = focusBoxesSafe.length - 1; i >= 0; i--) {
                        var box = focusBoxesSafe[i]
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
                    dragging = false
                    if (shellReady)
                        shellApi.clearDrawnQuery()
                    x0 = mouse.x
                    y0 = mouse.y
                    rx = mouse.x
                    ry = mouse.y
                    rw = 0
                    rh = 0
                    hasRect = true
                }
                onPositionChanged: function(mouse) {
                    if (!pressed)
                        return
                    rx = Math.min(x0, mouse.x)
                    ry = Math.min(y0, mouse.y)
                    rw = Math.abs(mouse.x - x0)
                    rh = Math.abs(mouse.y - y0)
                    if (rw >= 4 || rh >= 4)
                        dragging = true
                }
                onReleased: function(mouse) {
                    var origin = contentOrigin()
                    var pw = photo.paintedWidth
                    var ph = photo.paintedHeight
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
                        hasRect = true
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
                    shell.findSimilar()
                }
            }

            Rectangle {
                visible: regionDrag.hasRect && focusKindSafe !== "video"
                x: photo.x + regionDrag.rx
                y: photo.y + regionDrag.ry
                width: regionDrag.rw
                height: regionDrag.rh
                color: tokenAccentDim
                border.color: tokenAccent
                border.width: 1
                z: 3
            }

            // Playback is deferred. This output stays hidden so a non-working
            // player is not shown. Remaining work: play focusUrl in a viewer
            // that does not admit source_type=video to open_focus or DBSCAN.
            VideoOutput {
                id: videoOut
                anchors.fill: parent
                anchors.margins: 48
                visible: false
            }

            MediaPlayer {
                id: player
                videoOutput: videoOut
                audioOutput: AudioOutput {}
                onMediaStatusChanged: {
                }
            }

            Text {
                objectName: "videoMissing"
                visible: false
                text: ""
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 15
            }

            Text {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 22
                text: "Back"
                color: backArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 14
                MouseArea {
                    id: backArea
                    anchors.fill: parent
                    anchors.margins: -8
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.escape()
                }
            }

            Text {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 22
                anchors.bottomMargin: similarStrip.visible ? 108 : 22
                text: focusNameSafe
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Column {
                objectName: "focusInspector"
                anchors.left: parent.left
                anchors.bottom: parent.bottom
                anchors.leftMargin: 22
                anchors.bottomMargin: similarStrip.visible ? 108 : 22
                spacing: 8
                width: 220

                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 6
                    color: similarHit.containsMouse ? tokenBg2 : tokenBg3
                    border.color: tokenAccent
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Similar"
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                    }
                    MouseArea {
                        id: similarHit
                        objectName: "similarAction"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady) shellApi.findSimilarWhole()
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 32
                    visible: primaryModeSafe
                    radius: 6
                    color: askArea.containsMouse ? tokenAccentDim : tokenBg2
                    border.color: tokenAccent
                    border.width: 1
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
                        onClicked: if (shellReady) shellApi.askPhoto()
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 32
                    visible: advancedModeSafe
                    radius: 6
                    color: statusArea.containsMouse ? tokenAccentDim : tokenBg2
                    border.color: tokenAccent
                    border.width: 1
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
                        onClicked: if (shellReady) shellApi.submitCommand("status")
                    }
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
                Text {
                    objectName: "resultText"
                    width: parent.width
                    text: shellReady ? shell.resultText : ""
                    color: tokenMuted
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
            }

            Text {
                objectName: "similarNote"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 28
                visible: similarStateSafe === "empty" || similarStateSafe === "unavailable"
                text: similarNoteSafe
                color: tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
            }

            Flickable {
                id: similarStrip
                objectName: "similarStrip"
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 22
                width: Math.min(Math.max(similarCountSafe * 80 - 8, 0), parent.width - 96)
                height: similarReady && similarCountSafe > 0 ? 76 : 0
                contentWidth: stripRow.width
                contentHeight: 76
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                visible: height > 0

                Row {
                    id: stripRow
                    spacing: 8
                    Repeater {
                        model: similarModel
                        delegate: Item {
                            width: 72
                            height: 72
                            objectName: "similarThumb"

                            Rectangle {
                                anchors.fill: parent
                                color: tokenBg2
                                radius: 2
                                border.width: thumbArea.containsMouse ? 1 : 0
                                border.color: tokenAccent

                                Image {
                                    anchors.fill: parent
                                    anchors.margins: 1
                                    source: shellReady ? shellApi.thumbFor(mediaId) : ""
                                    fillMode: Image.PreserveAspectCrop
                                    asynchronous: true
                                    cache: true
                                }

                                MouseArea {
                                    id: thumbArea
                                    objectName: "similarThumbHit"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (shellReady) shellApi.openFocus(mediaId)
                                }
                            }
                        }
                    }
                }
            }

            Text {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 18
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
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 18
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
                    player.stop()
                    player.source = ""
                }
            }
        }
    }
}
