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

    readonly property bool shellReady: shell !== undefined && shell !== null
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
    readonly property int motion: shellReady && shellApi.reducedMotion ? 0 : 180
    readonly property color tokenBg: shellReady ? shellApi.bg0 : "#0b0c0e"
    readonly property color tokenBg1: shellReady ? shellApi.bg1 : "#131417"
    readonly property color tokenAccent: shellReady ? shellApi.accent : "#4f8cff"
    readonly property color tokenText: shellReady ? shellApi.text1 : "#f2f3f5"
    readonly property color tokenMuted: shellReady ? shellApi.text2 : "#a8adb7"
    readonly property color tokenReview: shellReady ? shellApi.reviewColor : "#a15cf5"
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

    header: Rectangle {
        color: tokenBg1
        height: 72
        width: window.width

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: "#243140"
        }

        Column {
            id: brand
            anchors.left: parent.left
            anchors.leftMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            Text {
                id: wordmark
                text: "Semblon"
                color: "#E7EEF5"
                font.family: "Segoe UI Variable"
                font.pixelSize: 20
                font.weight: Font.DemiBold
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.wordmark()
                }
            }
            Text {
                id: lensLine
                objectName: "lensLine"
                text: lensLabelSafe
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                font.letterSpacing: 0.4
            }
            Row {
                spacing: 8

                Rectangle {
                    objectName: "primaryModeButton"
                    width: 74
                    height: 24
                    radius: 12
                    color: primaryModeSafe ? "#17333A" : "#1C2430"
                    border.color: primaryModeSafe ? "#2DD4BF" : "#243140"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "Primary"
                        color: primaryModeSafe ? "#5EEAD4" : "#8AA0B2"
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady) shellApi.setMode("primary")
                    }
                }

                Rectangle {
                    objectName: "advancedModeButton"
                    width: 84
                    height: 24
                    radius: 12
                    color: advancedModeSafe ? "#17333A" : "#1C2430"
                    border.color: advancedModeSafe ? "#2DD4BF" : "#243140"
                    border.width: 1

                    Text {
                        anchors.centerIn: parent
                        text: "Advanced"
                        color: advancedModeSafe ? "#5EEAD4" : "#8AA0B2"
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }

                    MouseArea {
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady) shellApi.setMode("advanced")
                    }
                }
            }

        }

        Rectangle {
            id: command
            width: 320
            height: 36
            visible: advancedModeSafe
            radius: 8
            color: "#1C2430"
            border.color: commandField.activeFocus ? "#2DD4BF" : "#243140"
            border.width: 1
            anchors.left: brand.right
            anchors.leftMargin: 36
            anchors.verticalCenter: parent.verticalCenter

            TextField {
                id: commandField
                objectName: "commandField"
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: TextInput.AlignVCenter
                placeholderText: primaryModeSafe ? "Search people" : "Command: people, status"
                placeholderTextColor: "#6E8294"
                color: "#E7EEF5"
                font.family: "Segoe UI"
                font.pixelSize: 14
                background: Item {}
                selectByMouse: true
                onAccepted: if (shellReady) shellApi.submitCommand(text)
            }
        }

        Rectangle {
            id: searchBox
            width: 320
            height: 36
            visible: primaryModeSafe
            radius: 8
            color: tokenBg1
            border.color: searchField.activeFocus ? tokenAccent : "#2a2d33"
            border.width: 1
            anchors.left: brand.right
            anchors.leftMargin: 36
            anchors.verticalCenter: parent.verticalCenter

            TextField {
                id: searchField
                objectName: "searchField"
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                verticalAlignment: TextInput.AlignVCenter
                placeholderText: "Search memory"
                placeholderTextColor: "#6b7280"
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 14
                background: Item {}
                selectByMouse: true
                onAccepted: if (shellReady) shellApi.submitCommand(text)
            }
        }

        Row {
            id: headerActions
            anchors.right: parent.right
            anchors.rightMargin: 28
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            Text {
                objectName: "peopleButton"
                text: "People"
                color: peopleArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                MouseArea {
                    id: peopleArea
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.openPeople()
                }
            }

            Text {
                objectName: "settingsButton"
                text: "Settings"
                color: settingsArea.containsMouse ? tokenText : tokenMuted
                font.family: "Segoe UI"
                font.pixelSize: 13
                MouseArea {
                    id: settingsArea
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.toggleSettings()
                }
            }

            Text {
                text: "Add folder"
                color: addFolderArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                MouseArea {
                    id: addFolderArea
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady && !jobRunning) shellApi.addFolder()
                }
            }
        }

        Row {
            anchors.right: headerActions.left
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10
            visible: jobRunning
            objectName: "processingMark"

            Item {
                width: 16
                height: 16
                anchors.verticalCenter: parent.verticalCenter
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
                        ctx.strokeStyle = "#2DD4BF"
                        ctx.lineWidth = 1.5
                        ctx.beginPath()
                        ctx.arc(width / 2, height / 2, 6, 0, Math.PI * 1.35)
                        ctx.stroke()
                    }
                    Component.onCompleted: requestPaint()
                }
            }
            Text {
                text: jobLabelSafe
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                objectName: "pauseJob"
                text: jobStateSafe === "paused" ? "Resume" : "Pause"
                visible: jobRunning
                color: pauseArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    id: pauseArea
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) {
                        if (shellApi.jobState === "paused")
                            shellApi.resumeJob()
                        else
                            shellApi.pauseJob()
                    }
                }
            }
            Text {
                objectName: "cancelJob"
                text: "Cancel"
                color: cancelArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 13
                anchors.verticalCenter: parent.verticalCenter
                MouseArea {
                    id: cancelArea
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: if (shellReady) shellApi.cancelJob()
                }
            }
        }

        Text {
            objectName: "resumeJob"
            text: "Resume"
            visible: shellReady && shellApi.canResume && !shellApi.jobActive
            anchors.right: atmospherePicker.left
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            color: resumeArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
            font.family: "Segoe UI"
            font.pixelSize: 13
            MouseArea {
                id: resumeArea
                anchors.fill: parent
                anchors.margins: -6
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (shellReady) shellApi.resumeJob()
            }
        }

        ComboBox {
            id: atmospherePicker
            objectName: "atmospherePicker"
            anchors.right: headerActions.left
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            width: 160
            model: shellReady ? shellApi.atmosphereChoices : []
            textRole: "label"
            displayText: (currentIndex >= 0 && model.length > currentIndex) ? model[currentIndex].label : "Atmosphere"

            onActivated: if (shellReady && currentIndex >= 0 && model.length > currentIndex) {
                shellApi.setAtmosphere(model[currentIndex].id)
            }

            Component.onCompleted: {
                if (!shellReady)
                    return
                for (var i = 0; i < model.length; i++) {
                    if (model[i].id === atmosphereIdSafe) {
                        currentIndex = i
                        break
                    }
                }
            }

            Connections {
                target: shellApi
                function onLensChanged() {
                    for (var i = 0; i < atmospherePicker.model.length; i++) {
                        if (atmospherePicker.model[i].id === atmosphereIdSafe) {
                            atmospherePicker.currentIndex = i
                            return
                        }
                    }
                }
            }
        }
    }

    Item {
        id: stage
        anchors.fill: parent

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
                    color: facetArea.containsMouse ? tokenText : tokenMuted
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
                    color: actionArea.containsMouse ? "#1B2B38" : "#141C25"
                    border.color: "#2a3340"
                    border.width: 1

                    Text {
                        id: actionText
                        anchors.centerIn: parent
                        text: modelData.label
                        color: "#E7EEF5"
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
            color: "#121B22"
            border.color: "#243140"
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
                    Text { text: "Library"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 11 }
                    Text { text: shellReady ? shellApi.count + " items" : "0 items"; color: "#E7EEF5"; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                    Text { objectName: "mediaKinds"; text: shellReady ? shellApi.photoCount + " photos · " + shellApi.videoCount + " videos" : ""; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 11 }
                }

                Column {
                    width: 96
                    spacing: 2
                    Text { text: "Review"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 11 }
                    Text { text: shellReady ? shellApi.reviewCountText : "0 groups"; color: "#E7EEF5"; font.family: "Segoe UI"; font.pixelSize: 12; font.weight: Font.DemiBold; wrapMode: Text.WordWrap }
                }

                Column {
                    width: 124
                    spacing: 2
                    Text { text: "Ready"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 11 }
                    Text { text: "Browse and search"; color: "#5EEAD4"; font.family: "Segoe UI"; font.pixelSize: 12 }
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
            color: shellReady && shellApi.surfaceState === "error" ? "#e5484d" : tokenMuted
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
            border.color: "#2a2d33"
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
                        color: settingHit.containsMouse ? "#24272c" : "#1b1d21"
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
                        color: settingHitAdvanced.containsMouse ? "#24272c" : "#1b1d21"
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
            border.color: "#2a2d33"
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
                    color: "#1b1d21"
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
            color: "#10161C"
            ScrollView {
                anchors.fill: parent
                anchors.margins: 28
                clip: true

                Column {
                    width: stage.width - 56
                    spacing: 16

                    Text {
                        text: "People"
                        color: "#E7EEF5"
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
                        color: "#8AA0B2"
                    }

                    Row {
                        width: parent.width
                        spacing: 18

                        Rectangle {
                            width: 320
                            height: 620
                            radius: 10
                            color: "#141C25"
                            border.color: "#243140"
                            border.width: 1

                            Column {
                                anchors.fill: parent
                                anchors.margins: 16
                                spacing: 12

                                Text {
                                    text: "Groups"
                                    color: "#E7EEF5"
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
                                        height: 54
                                        radius: 8
                                        color: named
                                                ? ((shellReady && shell.selectedSubject === subject) ? "#17333A" : "#1A222D")
                                                : "#241c2e"
                                        border.color: named
                                                ? ((shellReady && shell.selectedSubject === subject) ? "#2DD4BF" : "#243140")
                                                : tokenReview
                                        border.width: 1

                                        Column {
                                            anchors.fill: parent
                                            anchors.margins: 10
                                            spacing: 2

                                            Text {
                                                text: title
                                                color: "#E7EEF5"
                                                font.pixelSize: 14
                                                elide: Text.ElideRight
                                            }
                                            Text {
                                                text: faceCount + (faceCount === 1 ? " face" : " faces")
                                                color: "#8AA0B2"
                                                font.pixelSize: 12
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
                            color: "#141C25"
                            border.color: "#243140"
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
                                            color: "#E7EEF5"
                                            font.pixelSize: 20
                                            font.family: "Segoe UI Variable"
                                            font.weight: Font.DemiBold
                                            elide: Text.ElideRight
                                        }
                                        Text {
                                              text: shellReady && shell.selectedSubject !== ""
                                                  ? (selectedCountSafe + (selectedCountSafe === 1 ? " face" : " faces"))
                                                  : "Choose a group to review evidence, merge, name, note, or split faces."
                                            color: "#8AA0B2"
                                            font.pixelSize: 13
                                            wrapMode: Text.WordWrap
                                        }
                                    }

                                    Text {
                                        objectName: "peopleEvidence"
                                        visible: shellReady && shell.evidenceId !== ""
                                        text: "Open evidence"
                                        color: evidenceArea.containsMouse ? "#E7EEF5" : "#5EEAD4"
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
                                    color: "#E7EEF5"
                                    font.family: "Segoe UI"
                                    font.pixelSize: 14
                                    background: Rectangle {
                                        radius: 8
                                        color: "#1A222D"
                                        border.color: decisionText.activeFocus ? "#2DD4BF" : "#243140"
                                        border.width: 1
                                    }
                                }

                                Row {
                                    width: parent.width
                                    spacing: 16

                                    Text {
                                        text: "Name"
                                        color: decisionText.text.trim().length > 0 ? "#5EEAD4" : "#6E8294"
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("name", shellApi.selectedSubject, decisionText.text)
                                        }
                                    }
                                    Text {
                                        text: "Note"
                                        color: decisionText.text.trim().length > 0 ? "#5EEAD4" : "#6E8294"
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("note", shellApi.selectedSubject, decisionText.text)
                                        }
                                    }
                                    Text {
                                        text: "Ignore"
                                        color: "#5EEAD4"
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.decide("ignore", shellApi.selectedSubject, "")
                                        }
                                    }
                                    Text {
                                        text: primaryModeSafe ? "Not this person" : "Rule out"
                                        color: "#5EEAD4"
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
                                    color: "#8AA0B2"
                                    font.pixelSize: 13
                                    wrapMode: Text.WordWrap
                                }

                                Rectangle {
                                    width: parent.width
                                    height: 86
                                    radius: 8
                                    color: "#10161C"
                                    border.color: "#243140"
                                    border.width: 1

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 8

                                        Text {
                                            text: "Merge with another group"
                                            color: "#E7EEF5"
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
                                                    color: shellReady && mergeTargetSubjectSafe === subject ? "#17333A" : "#1A222D"
                                                    border.color: shellReady && mergeTargetSubjectSafe === subject ? "#2DD4BF" : "#243140"
                                                    border.width: 1

                                                    Text {
                                                        id: titleText
                                                        anchors.centerIn: parent
                                                        text: title + " · " + faceCount
                                                        color: "#E7EEF5"
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
                                        color: canMergeSelectedSafe ? "#5EEAD4" : "#6E8294"
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
                                        color: splitSelectionCountSafe > 0 ? "#5EEAD4" : "#6E8294"
                                        font.pixelSize: 14
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.clearSplitSelection()
                                        }
                                    }

                                    Text {
                                        text: splitSelectionCountSafe > 0 ? (splitSelectionCountSafe === 1 ? "1 face selected" : splitSelectionCountSafe + " faces selected") : "Select faces below to split them out"
                                        color: "#8AA0B2"
                                        font.pixelSize: 13
                                    }

                                    Text {
                                        text: "Split selected"
                                        color: canSplitSelectedSafe ? "#5EEAD4" : "#6E8294"
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
                                    color: "#10161C"
                                    border.color: "#243140"
                                    border.width: 1

                                    Column {
                                        anchors.fill: parent
                                        anchors.margins: 12
                                        spacing: 10

                                        Text {
                                            text: "Select faces to split"
                                            color: "#E7EEF5"
                                            font.pixelSize: 14
                                        }
                                        Text {
                                            text: "Click one or more faces, then split only those faces out of the group."
                                            color: "#8AA0B2"
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
                                                color: shellReady && shell.isSplitFaceSelected(face_id) ? "#17333A" : "#1A222D"
                                                border.color: shellReady && shell.isSplitFaceSelected(face_id) ? "#2DD4BF" : "#243140"
                                                border.width: 1

                                                Column {
                                                    anchors.fill: parent
                                                    anchors.margins: 6
                                                    spacing: 4

                                                    Rectangle {
                                                        width: parent.width
                                                        height: 76
                                                        radius: 6
                                                        color: "#10161C"
                                                        border.color: "#243140"
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
                                                        color: "#E7EEF5"
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
                                    color: backPeopleArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
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

        GridView {
            id: grid
            objectName: "fieldGrid"
            anchors.fill: parent
            anchors.margins: 22
            anchors.topMargin: 52
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
                    anchors.margins: 6
                    color: "#1C2430"
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
                        border.color: grid.currentIndex === index ? "#2DD4BF" : "#3D4C5C"
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
            }

            Connections {
                target: shellApi
                function onFocusChanged() {
                    if (!focusActive && shellReady)
                        grid.contentY = shellApi.scrollY
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
                color: "#E7EEF5"
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
                color: "#8AA0B2"
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
                color: "#8AA0B2"
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
                    color: "#141C25"
                    border.color: "#243140"
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Archive"; color: "#E7EEF5"; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Browse your local library"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle {
                    objectName: "peopleCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: "#141C25"
                    border.color: "#243140"
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "People"; color: "#E7EEF5"; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Review groups with human decisions"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle {
                    objectName: "searchCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: "#141C25"
                    border.color: "#243140"
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Search"; color: "#E7EEF5"; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Find faces, people, and media"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }

                Rectangle {
                    objectName: "lensCard"
                    width: 180
                    height: 110
                    radius: 10
                    color: "#141C25"
                    border.color: "#243140"
                    border.width: 1
                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8
                        Text { text: "Ask photo"; color: "#E7EEF5"; font.family: "Segoe UI"; font.pixelSize: 16; font.weight: Font.DemiBold }
                        Text { text: "Read, describe, and inspect visual context"; color: "#8AA0B2"; font.family: "Segoe UI"; font.pixelSize: 12; wrapMode: Text.WordWrap }
                    }
                }
            }

            Item { width: 1; height: 8 }
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: addLabel.implicitWidth + 36
                height: 40
                radius: 8
                color: addArea.containsMouse ? "#12343A" : "#1C2430"
                border.color: "#2DD4BF"
                border.width: 1
                visible: !jobRunning
                Text {
                    id: addLabel
                    anchors.centerIn: parent
                    text: "Add a folder"
                    color: "#5EEAD4"
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
                color: resumeEmptyArea.containsMouse ? "#12343A" : "#1C2430"
                border.color: "#243140"
                border.width: 1
                visible: canResumeSafe && !jobRunning
                Text {
                    id: resumeEmptyLabel
                    anchors.centerIn: parent
                    text: jobLabelSafe === "Last add failed" ? "Try again" : "Resume"
                    color: "#E7EEF5"
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
                color: "#10161C"
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
                color: "#332DD4BF"
                border.color: "#2DD4BF"
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
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 15
            }

            Text {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 22
                text: "Back"
                color: backArea.containsMouse ? "#E7EEF5" : "#8AA0B2"
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
                color: "#8AA0B2"
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
                    color: similarHit.containsMouse ? "#1b1d21" : "#24272c"
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
                    color: askArea.containsMouse ? "#12343A" : "#1C2430"
                    border.color: "#2DD4BF"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Ask about this photo"
                        color: "#5EEAD4"
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
                    color: statusArea.containsMouse ? "#12343A" : "#1C2430"
                    border.color: "#2DD4BF"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "Run diagnostics status"
                        color: "#5EEAD4"
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
                    color: "#10161C"
                    border.color: "#243140"
                    border.width: 1
                    radius: 8
                    implicitHeight: diagnosticsText.implicitHeight + 14

                    Text {
                        id: diagnosticsText
                        anchors.fill: parent
                        anchors.margins: 7
                        text: shellReady ? shellApi.diagnosticsText : ""
                        color: "#8AA0B2"
                        font.family: "Consolas"
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                }
                Text {
                    objectName: "resultText"
                    width: parent.width
                    text: shellReady ? shell.resultText : ""
                    color: "#8AA0B2"
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
                color: "#8AA0B2"
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
                                color: "#1C2430"
                                radius: 2
                                border.width: thumbArea.containsMouse ? 1 : 0
                                border.color: "#2DD4BF"

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
                color: "#E7EEF5"
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
                color: "#E7EEF5"
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
