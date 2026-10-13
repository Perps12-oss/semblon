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
    property string stickyDay: ""
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
    readonly property int motion: shellReady && shellApi.reducedMotion ? 0 : 180
    readonly property color tokenBg: shellReady ? shellApi.bg0 : "#0f1015"
    readonly property color tokenBg1: shellReady ? shellApi.bg1 : "#161821"
    readonly property color tokenAccent: shellReady ? shellApi.accent : "#9eb3d4"
    readonly property color tokenText: shellReady ? shellApi.text1 : "#e7eaf0"
    readonly property color tokenMuted: shellReady ? shellApi.text2 : "#aeb3bf"
    readonly property color tokenReview: shellReady ? shellApi.reviewColor : "#8e7aab"
    readonly property color tokenBg2: shellReady ? shellApi.bg2 : "#1d1f29"
    readonly property color tokenBg3: shellReady ? shellApi.bg3 : "#262932"
    readonly property color tokenBorder: shellReady ? shellApi.border1 : "#2a2e38"
    readonly property color tokenFaint: shellReady ? shellApi.text3 : "#80858f"
    readonly property color tokenAccentDim: shellReady ? shellApi.accentDim : "#2c3a4e"
    readonly property color tokenDanger: shellReady ? shellApi.dangerColor : "#c47373"
    readonly property var primarySettingCalls: ["cycleDensity", "libraryHealth", "showActivity", "modePeople", "modeText", "rescan", "resetDefaults"]
    readonly property var primarySettingLabels: ["Density", "Library health", "Activity", "Search people", "Search text", "Rescan", "Reset defaults"]
    readonly property var advancedSettingCalls: ["scanDuplicates", "showCapabilities", "gpuAuto", "gpuOff", "namedItems", "knowledgePack", "installModel"]
    readonly property var advancedSettingLabels: ["Duplicates", "Capabilities", "GPU auto", "GPU off", "Named items", "Knowledge pack", "Install model"]
    readonly property var facetNames: ["Memory", "Days", "Folders", "Moments"]
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

    function formatDay(iso) {
        if (!iso)
            return "Undated"
        var parts = String(iso).split("-")
        if (parts.length !== 3)
            return String(iso)
        var months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        var month = parseInt(parts[1], 10)
        var day = parseInt(parts[2], 10)
        if (!(month >= 1 && month <= 12) || !(day >= 1 && day <= 31))
            return String(iso)
        return day + " " + months[month - 1] + " " + parts[0]
    }

    function refreshStickyDay() {
        if (!shellReady || emptySafe)
            return
        var cols = Math.max(1, Math.floor(grid.width / Math.max(1, grid.cellWidth)))
        var row = Math.max(0, Math.floor(grid.contentY / Math.max(1, grid.cellHeight)))
        stickyDay = shellApi.dayAt(row * cols)
    }

    function facetIsActive(label) {
        if (!shellReady)
            return label === "Memory"
        var facet = shellApi.facet
        if (label === "Memory")
            return facet === "memory"
        if (label === "Days")
            return facet === "timeline"
        if (label === "Folders")
            return facet === "folders"
        if (label === "Moments")
            return facet === "moments"
        return false
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
                    readonly property bool navActive: {
                        if (!window.shellReady)
                            return false
                        if (navId === "people")
                            return window.peopleVisible
                        if (navId === "settings")
                            return window.shellApi.settingsOpen
                        if (navId === "library")
                            return !window.peopleVisible && !window.shellApi.settingsOpen && !window.focusActive
                        return false
                    }
                    anchors.fill: parent
                    radius: 4
                    color: navActive ? tokenBg2 : (navArea.containsMouse ? tokenBg3 : "transparent")
                    onNavActiveChanged: navIconCanvas.requestPaint()
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
                                ctx.strokeStyle = navActive ? tokenAccent : (navArea.containsMouse ? tokenText : tokenMuted)
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
                            color: navActive ? tokenAccent : (navArea.containsMouse ? tokenText : tokenMuted)
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
                radius: 4
                visible: !sidebarCollapsed
                color: "transparent"
                border.color: primaryModeSafe ? tokenAccent : tokenBorder
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "Primary"
                    color: primaryModeSafe ? tokenAccent : tokenMuted
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
                radius: 4
                visible: !sidebarCollapsed
                color: "transparent"
                border.color: advancedModeSafe ? tokenAccent : tokenBorder
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "Advanced"
                    color: advancedModeSafe ? tokenAccent : tokenMuted
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
            id: facetBar
            objectName: "facetBar"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 28
            anchors.topMargin: 8
            spacing: 14
            visible: !peopleVisible && !focusActive
            z: 2

            Repeater {
                model: advancedModeSafe ? 4 : 3
                delegate: Text {
                    property string facetName: facetNames[index]
                    Component.onCompleted: objectName = "facet_" + facetName
                    text: facetName
                    color: window.facetIsActive(facetName) ? tokenAccent : (facetArea.containsMouse ? tokenText : tokenMuted)
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    MouseArea {
                        id: facetArea
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady) shellApi.setFacet(facetName)
                    }
                }
            }
        }

        Row {
            id: quickActionRail
            objectName: "quickActionRail"
            anchors.left: facetBar.left
            anchors.top: facetBar.bottom
            anchors.topMargin: 12
            spacing: 10
            visible: primaryModeSafe && !peopleVisible && !focusActive
            z: 2

            Repeater {
                model: [
                    { label: "Archive", action: "setFacet('memory')" },
                    { label: "People", action: "openPeople()" },
                    { label: "Search", action: "setSearchMode('people')" },
                    { label: "Ask photo", action: "findSimilarWhole()" }
                ]
                delegate: Rectangle {
                    width: actionText.implicitWidth + 18
                    height: 28
                    radius: 14
                    color: actionArea.containsMouse ? tokenBg3 : tokenBg2
                    border.color: tokenBorder
                    border.width: 1

                    Text {
                        id: actionText
                        anchors.centerIn: parent
                        text: modelData.label
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    MouseArea {
                        id: actionArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!shellReady) return
                            if (modelData.action === "setFacet('memory')") shellApi.setFacet("memory")
                            else if (modelData.action === "openPeople()") shellApi.openPeople()
                            else if (modelData.action === "setSearchMode('people')") shellApi.setSearchMode("people")
                            else if (modelData.action === "findSimilarWhole()") shellApi.findSimilarWhole()
                        }
                    }
                }
            }
        }

        Rectangle {
            id: librarySnapshot
            objectName: "librarySnapshot"
            anchors.left: quickActionRail.left
            anchors.top: quickActionRail.bottom
            anchors.topMargin: 8
            width: 390
            height: 56
            radius: 10
            color: tokenBg1
            border.color: tokenBorder
            border.width: 1
            visible: primaryModeSafe && !emptySafe && !peopleVisible && !focusActive
            z: 2

            Row {
                anchors.fill: parent
                anchors.margins: 12
                spacing: 18

                Column {
                    width: 150
                    spacing: 2
                    Text { text: "Library"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 11 }
                    Text { text: shellReady ? shellApi.count + " items" : "0 items"; color: tokenText; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                    Text { objectName: "mediaKinds"; text: shellReady ? shellApi.photoCount + " photos · " + shellApi.videoCount + " videos" : ""; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 11 }
                }

                Column {
                    width: 96
                    spacing: 2
                    Text { text: "Review"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 11 }
                    Text { text: shellReady ? shellApi.reviewCountText : "0 groups"; color: tokenText; font.family: "Segoe UI"; font.pixelSize: 12; font.weight: Font.DemiBold; wrapMode: Text.WordWrap }
                }

                Column {
                    width: 124
                    spacing: 2
                    Text { text: "Ready"; color: tokenMuted; font.family: "Segoe UI"; font.pixelSize: 11 }
                    Text { text: "Browse and search"; color: tokenAccent; font.family: "Segoe UI"; font.pixelSize: 12 }
                }
            }
        }

        Text {
            objectName: "surfaceState"
            anchors.left: facetBar.left
            anchors.top: librarySnapshot.visible ? librarySnapshot.bottom : quickActionRail.bottom
            anchors.topMargin: 4
            visible: shellReady && (shellApi.surfaceState === "error" || shellApi.surfaceState === "unavailable" || shellApi.surfaceState === "loading")
            text: shellReady ? (shellApi.noticeText || (shellApi.surfaceState === "loading" ? "Working…" : "Something went wrong. Try again.")) : ""
            color: shellReady && shellApi.surfaceState === "error" ? tokenDanger : tokenMuted
            font.family: "Segoe UI"
            font.pixelSize: 13
            z: 2
        }

        Row {
            id: bucketRow
            objectName: "bucketRow"
            anchors.left: facetBar.left
            anchors.top: facetBar.bottom
            anchors.topMargin: 18
            spacing: 10
            visible: !peopleVisible && !focusActive && shellReady && shellApi.buckets.length > 0
            z: 2

            Repeater {
                model: shellReady ? shellApi.buckets : []
                delegate: Text {
                    text: modelData.label + " (" + modelData.count + ")"
                    color: bucketHit.containsMouse ? tokenText : tokenMuted
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    MouseArea {
                        id: bucketHit
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady) shellApi.selectBucket(modelData.key)
                    }
                }
            }
        }

        Rectangle {
            objectName: "settingsSheet"
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 16
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
            anchors.top: facetBar.bottom
            anchors.leftMargin: 16
            anchors.topMargin: 12
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
                        font.pixelSize: 28
                        font.family: "Segoe UI Variable"
                        font.weight: Font.Medium
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
                                    spacing: 6
                                    delegate: Rectangle {
                                        width: ListView.view.width
                                        height: 64
                                        radius: 4
                                        color: tokenBg2
                                        border.color: (shellReady && shell.selectedSubject === subject)
                                                ? (named ? tokenAccent : tokenReview)
                                                : (named ? tokenBorder : tokenReview)
                                        border.width: 1

                                        Row {
                                            anchors.fill: parent
                                            anchors.leftMargin: 8
                                            anchors.rightMargin: 10
                                            spacing: 10

                                            Rectangle {
                                                width: 40
                                                height: 40
                                                radius: 20
                                                anchors.verticalCenter: parent.verticalCenter
                                                color: tokenBg
                                                clip: true

                                                Image {
                                                    anchors.fill: parent
                                                    visible: faceId !== ""
                                                    source: faceId !== "" ? ("image://face/" + faceId) : ""
                                                    fillMode: Image.PreserveAspectCrop
                                                    asynchronous: true
                                                    cache: true
                                                }
                                            }

                                            Column {
                                                width: parent.width - 50
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

                                    Text {
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
                                    width: parent.width
                                    spacing: 14

                                    Text {
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
                                        text: splitSelectionCountSafe > 0 ? (splitSelectionCountSafe === 1 ? "1 face selected" : splitSelectionCountSafe + " faces selected") : "Select faces below to split them out"
                                                                                color: tokenMuted
                                        font.pixelSize: 13
                                    }

                                    Text {
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

        Rectangle {
            id: archiveSidebar
            objectName: "archiveSidebar"
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.topMargin: 52
            anchors.rightMargin: 12
            anchors.bottomMargin: 12
            width: 190
            radius: 10
            color: tokenBg1
            border.color: tokenBorder
            border.width: 1
            visible: !emptySafe && !peopleVisible && !focusActive
            z: 2

            Flickable {
                anchors.fill: parent
                anchors.margins: 12
                contentHeight: archiveSidebarColumn.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds

                Column {
                    id: archiveSidebarColumn
                    width: parent.width
                    spacing: 6

                    Text {
                        objectName: "sidebarAll"
                        text: shellReady && shellApi.scopeLabel !== "" ? "Show everything" : "Everything"
                        color: shellReady && shellApi.scopeLabel === "" ? tokenText : tokenAccent
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -3
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.clearScope()
                        }
                    }

                    Text {
                        objectName: "sidebarSimilar"
                        text: "Similar"
                        color: similarNavArea.containsMouse ? tokenText : tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        MouseArea {
                            id: similarNavArea
                            anchors.fill: parent
                            anchors.margins: -3
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.findSimilarWhole()
                        }
                    }

                    Row {
                        spacing: 10
                        Repeater {
                            model: [
                                {"key": "all", "label": "All"},
                                {"key": "photo", "label": "Photos"},
                                {"key": "video", "label": "Videos"}
                            ]
                            delegate: Text {
                                property bool active: shellReady && shellApi.mediaKind === modelData.key
                                Component.onCompleted: objectName = "sidebarKind_" + modelData.key
                                text: modelData.label
                                color: active ? tokenAccent : (kindArea.containsMouse ? tokenText : tokenMuted)
                                font.family: "Segoe UI"
                                font.pixelSize: 12
                                MouseArea {
                                    id: kindArea
                                    anchors.fill: parent
                                    anchors.margins: -3
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (shellReady) shellApi.setMediaKind(modelData.key)
                                }
                            }
                        }
                    }

                    Item { width: 1; height: 6 }
                    Text { text: "Years"; color: tokenFaint; font.family: "Segoe UI"; font.pixelSize: 11; font.letterSpacing: 0.6 }

                    Repeater {
                        model: shellReady ? shellApi.yearRows : []
                        delegate: Text {
                            property bool active: shellReady && shellApi.scopeKind === "year" && shellApi.scopeLabel === modelData.label
                            Component.onCompleted: objectName = "sidebarYear_" + modelData.label
                            width: sidebarColumn.width
                            text: modelData.label + "  " + modelData.count
                            color: active ? tokenAccent : (yearArea.containsMouse ? tokenText : tokenMuted)
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            MouseArea {
                                id: yearArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.selectYear(modelData.label)
                            }
                        }
                    }

                    Item { width: 1; height: 6 }
                    Text { text: "Folders"; color: tokenFaint; font.family: "Segoe UI"; font.pixelSize: 11; font.letterSpacing: 0.6 }

                    Repeater {
                        model: shellReady ? shellApi.folderRows : []
                        delegate: Text {
                            property bool active: shellReady && shellApi.scopeKind === "folder" && shellApi.scopeLabel === modelData.label
                            Component.onCompleted: objectName = "sidebarFolder_" + modelData.label
                            width: sidebarColumn.width
                            text: modelData.label + "  " + modelData.count
                            color: active ? tokenAccent : (folderArea.containsMouse ? tokenText : tokenMuted)
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            MouseArea {
                                id: folderArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.selectFolder(modelData.label)
                            }
                        }
                    }
                }
            }
        }

        Text {
            id: dayHeader
            objectName: "dayHeader"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.leftMargin: 22
            anchors.topMargin: quickActionRail.visible ? 70 : 28
            visible: !emptySafe && !focusActive && !peopleVisible && stickyDay !== ""
            text: formatDay(stickyDay)
            color: tokenFaint
            font.family: "Segoe UI"
            font.pixelSize: 13
            font.letterSpacing: 0.8
            z: 3
        }

        GridView {
            id: grid
            objectName: "fieldGrid"
            anchors.fill: parent
            anchors.margins: 18
            anchors.rightMargin: archiveSidebar.visible ? 214 : 18
            anchors.topMargin: quickActionRail.visible ? 96 : 52
            visible: !emptySafe
            opacity: !focusActive ? 1 : 0
            cellWidth: shellReady ? shellApi.cellSize : 160
            cellHeight: shellReady ? shellApi.cellSize : 160
            cacheBuffer: 400
            boundsBehavior: Flickable.StopAtBounds
            model: archiveModel
            currentIndex: 0
            enabled: !focusActive
            keyNavigationEnabled: !focusActive
            highlightFollowsCurrentItem: false
            Behavior on opacity { NumberAnimation { duration: window.motion } }

            delegate: Item {
                width: grid.cellWidth
                height: grid.cellHeight

                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 2
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
                        visible: false
                        text: ""
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
                            shellApi.openFocus(mediaId)
                        }
                    }
                }
            }

            onContentYChanged: {
                if (!focusActive && shellReady)
                    shellApi.setScroll(contentY)
                window.refreshStickyDay()
            }
            onWidthChanged: window.refreshStickyDay()
            Component.onCompleted: window.refreshStickyDay()

            Connections {
                target: shellApi
                function onFocusChanged() {
                    if (!focusActive && shellReady)
                        grid.contentY = shellApi.scrollY
                    window.refreshStickyDay()
                }
                function onLibraryChanged() {
                    window.refreshStickyDay()
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
                radius: 4
                color: tokenText
                border.width: 0
                visible: !jobRunning
                Text {
                    id: addLabel
                    anchors.centerIn: parent
                    text: "Add a folder"
                    color: tokenBg
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
                anchors.leftMargin: 28
                anchors.rightMargin: 28
                anchors.topMargin: 56
                anchors.bottomMargin: similarStrip.visible ? 120 : 64
                visible: focusKindSafe !== "video"
                source: (focusActive && focusKindSafe !== "video")
                        ? ("image://archive/f/" + focusIdSafe) : ""
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                cache: false
            }

            MouseArea {
                id: regionDrag
                objectName: "regionDrag"
                anchors.fill: photo
                enabled: focusKindSafe !== "video" && photo.paintedWidth > 0
                property real rx: 0
                property real ry: 0
                property real rw: 0
                property real rh: 0
                property bool hasRect: false
                property real x0: 0
                property real y0: 0

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

                onPressed: function(mouse) {
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
                        if (!insidePainted(mouse.x, mouse.y)) {
                            hasRect = false
                            shell.clearDrawnQuery()
                            return
                        }
                        var spec = shell.pointAt(
                            Math.max(0, Math.min(0.999999, (mouse.x - origin.x) / pw)),
                            Math.max(0, Math.min(0.999999, (mouse.y - origin.y) / ph))
                        )
                        if (!spec) {
                            hasRect = false
                            return
                        }
                        var parts = spec.split(",")
                        if (parts.length !== 4) {
                            hasRect = false
                            return
                        }
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
            }

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
                text: "Close"
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
                    radius: 4
                    color: similarHit.containsMouse ? tokenBg3 : tokenBg2
                    border.color: tokenBorder
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
                    radius: 4
                    color: askArea.containsMouse ? tokenBg3 : tokenBg2
                    border.color: tokenBorder
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
                    if (focusKindSafe === "video" && shellReady && shellApi.focusUrl !== "")
                        player.source = shellApi.focusUrl
                    else
                        player.source = ""
                }
            }
        }
    }
}
