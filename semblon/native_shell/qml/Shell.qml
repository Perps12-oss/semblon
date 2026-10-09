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
    color: canvas

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
    readonly property bool lightPalette: shellReady && shellApi.lightPalette
    readonly property bool contactVisible: shellReady && shellApi.archiveNav === "time" && shellApi.centreView === "contact"
    readonly property bool spatialVisible: shellReady && shellApi.archiveNav === "time" && shellApi.centreView === "spatial"
    readonly property color chrome: lightPalette ? "#f3efe6" : "#202329"
    readonly property color canvas: lightPalette ? "#f7f4ee" : "#17191d"
    readonly property color fg: lightPalette ? "#2a241c" : "#f0ece6"
    readonly property color muted: lightPalette ? "#6e655c" : "#9a958c"
    readonly property color faint: lightPalette ? "#8a8176" : "#6e737c"
    readonly property color accent: lightPalette ? "#8a5a32" : "#c4a574"
    readonly property color selectBg: lightPalette ? "#e7d7c4" : "#3a3027"
    readonly property color line: lightPalette ? "#e0d6c8" : "#2e333a"
    readonly property color tile: lightPalette ? "#efeae2" : "#292d34"
    readonly property string similarNavLabel: "Similar"

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

    header: Rectangle {
        id: topBar
        color: window.chrome
        height: 56
        width: window.width

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: window.line
        }

        Text {
            id: wordmark
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            text: "semblon."
            color: window.fg
            font.family: "Georgia"
            font.pixelSize: 22
            font.weight: Font.DemiBold
            MouseArea {
                anchors.fill: parent
                anchors.margins: -6
                cursorShape: Qt.PointingHandCursor
                onClicked: if (shellReady) shellApi.wordmark()
            }
        }

        Row {
            id: lensNav
            anchors.left: wordmark.right
            anchors.leftMargin: 22
            anchors.verticalCenter: parent.verticalCenter
            spacing: 16

            Repeater {
                model: [
                    { key: "time", label: "Time" },
                    { key: "folders", label: "Folders" },
                    { key: "people", label: "People" },
                    { key: "similar", label: window.similarNavLabel },
                    { key: "unresolved", label: "Unresolved" }
                ]
                delegate: Item {
                    width: navLabel.implicitWidth
                    height: 28
                    objectName: modelData.key === "people" ? "peopleButton" : ""
                    property bool active: modelData.key === "people"
                            ? peopleVisible
                            : (shellReady && shellApi.archiveNav === modelData.key && !peopleVisible)
                    Text {
                        id: navLabel
                        anchors.verticalCenter: parent.verticalCenter
                        text: modelData.label
                        color: active || navHit.containsMouse ? window.fg : window.muted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        font.weight: active ? Font.DemiBold : Font.Normal
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1
                        color: window.accent
                        visible: active
                    }
                    MouseArea {
                        id: navHit
                        anchors.fill: parent
                        anchors.margins: -4
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (!shellReady)
                                return
                            if (modelData.key === "people")
                                shellApi.openPeople()
                            else
                                shellApi.setNav(modelData.key)
                        }
                    }
                }
            }
        }

        Text {
            id: lensLine
            objectName: "lensLine"
            visible: false
            text: lensLabelSafe
        }
        Item {
            objectName: "peopleButton"
            width: 0
            height: 0
            visible: false
        }

        Rectangle {
            id: archiveSearchBox
            width: 240
            height: 32
            radius: 2
            color: window.canvas
            border.color: archiveSearch.activeFocus ? window.accent : window.line
            border.width: 1
            anchors.right: toolsButton.left
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter

            TextField {
                id: archiveSearch
                objectName: "archiveSearch"
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 8
                verticalAlignment: TextInput.AlignVCenter
                placeholderText: "Search named people"
                placeholderTextColor: window.faint
                color: window.fg
                font.family: "Segoe UI"
                font.pixelSize: 13
                background: Item {}
                selectByMouse: true
                onAccepted: if (shellReady) shellApi.searchNamed(text)
            }
        }

        Rectangle {
            id: toolsButton
            objectName: "indexTools"
            width: toolsLabel.implicitWidth + 22
            height: 32
            radius: 2
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            color: toolsHit.containsMouse ? window.tile : "transparent"
            border.color: window.line
            border.width: 1
            Text {
                id: toolsLabel
                anchors.centerIn: parent
                text: "Index & Tools"
                color: window.fg
                font.family: "Segoe UI"
                font.pixelSize: 13
            }
            MouseArea {
                id: toolsHit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (shellReady) shellApi.toggleTools()
            }
        }
    }

    Item {
        id: workspace
        anchors.fill: parent

        Rectangle {
            id: indexCol
            width: 216
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            color: window.chrome
            Rectangle {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: 1
                color: window.line
            }
            Flickable {
                anchors.fill: parent
                anchors.margins: 14
                contentHeight: indexBody.implicitHeight
                clip: true
                flickableDirection: Flickable.VerticalFlick
                boundsBehavior: Flickable.StopAtBounds
                Column {
                    id: indexBody
                    width: indexCol.width - 28
                    spacing: 14
                    Text {
                        text: "Archive index"
                        color: window.fg
                        font.family: "Georgia"
                        font.italic: true
                        font.pixelSize: 16
                    }
                    Text { text: "LIBRARY"; color: window.faint; font.pixelSize: 11; font.family: "Segoe UI"; font.letterSpacing: 1 }
                    Column {
                        width: parent.width
                        spacing: 2
                        Repeater {
                            model: [
                                { key: "time", label: "All media", count: shellReady ? shellApi.photoCount : 0 },
                                { key: "time", label: "Photos", count: shellReady ? shellApi.photoCount : 0 },
                                { key: "videos", label: "Videos", count: shellReady ? shellApi.videoCount : 0 }
                            ]
                            delegate: Rectangle {
                                width: parent.width
                                height: 26
                                radius: 2
                                color: (shellReady && shellApi.archiveNav === modelData.key && modelData.label !== "Photos" && shellApi.centreView === "contact") ? window.selectBg : "transparent"
                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    Text { text: modelData.label; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                                    Item { width: parent.width - 90; height: 1 }
                                    Text { text: modelData.count; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: if (shellReady) {
                                        shellApi.setNav(modelData.key)
                                        if (modelData.key === "time")
                                            shellApi.setCentre("contact")
                                    }
                                }
                            }
                        }
                    }
                    Text { text: "BROWSE BY YEAR"; color: window.faint; font.pixelSize: 11; font.family: "Segoe UI"; font.letterSpacing: 1 }
                    Text {
                        width: parent.width
                        text: shellReady ? shellApi.yearNote : ""
                        color: window.muted
                        font.family: "Segoe UI"
                        font.pixelSize: 11
                        wrapMode: Text.WordWrap
                    }
                    Column {
                        width: parent.width
                        spacing: 2
                        Repeater {
                            model: shellReady ? shellApi.yearRows : []
                            delegate: Row {
                                width: parent.width
                                height: 22
                                Text { text: modelData.label; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                                Item { width: Math.max(8, parent.width - 70); height: 1 }
                                Text { text: modelData.count; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 12 }
                            }
                        }
                    }
                    Text { text: "SAVED VIEWS"; color: window.faint; font.pixelSize: 11; font.family: "Segoe UI"; font.letterSpacing: 1 }
                    Text {
                        width: parent.width
                        text: shellReady ? shellApi.savedViewsNote : ""
                        color: window.muted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                    Text { text: "EXPLORE"; color: window.faint; font.pixelSize: 11; font.family: "Segoe UI"; font.letterSpacing: 1 }
                    Rectangle {
                        width: parent.width
                        height: 26
                        radius: 2
                        color: spatialVisible ? window.selectBg : "transparent"
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            text: "Spatial relationships"
                            color: window.fg
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setCentre("spatial")
                        }
                    }
                    Rectangle {
                        width: parent.width
                        height: 26
                        radius: 2
                        color: (shellReady && shellApi.archiveNav === "unresolved") ? window.selectBg : "transparent"
                        Row {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            Text { text: "To name"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                            Item { width: parent.width - 80; height: 1 }
                            Text { text: shellReady ? shellApi.unnamedCount : 0; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 12 }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setNav("unresolved")
                        }
                    }
                }
            }
        }

        Item {
            id: stage
            anchors.left: indexCol.right
            anchors.right: inspectorCol.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom

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
                                        color: (shellReady && shell.selectedSubject === subject) ? "#17333A" : "#1A222D"
                                        border.color: (shellReady && shell.selectedSubject === subject) ? "#2DD4BF" : "#243140"
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

        Column {
            id: centreHead
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.leftMargin: 22
            anchors.rightMargin: 22
            anchors.topMargin: 16
            spacing: 6
            visible: !focusActive && !peopleVisible
            height: visible ? implicitHeight : 0

            Text {
                text: shellReady
                      ? ("ARCHIVE / " + (spatialVisible ? "SPATIAL" : shellApi.archiveNav.toUpperCase()))
                      : ""
                color: window.faint
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.letterSpacing: 1.2
            }
            Item {
                width: parent.width
                height: centreTitle.implicitHeight
                Text {
                    id: centreTitle
                    text: shellReady ? shellApi.collectionTitle : ""
                    color: window.fg
                    font.family: "Georgia"
                    font.italic: true
                    font.pixelSize: 34
                }
                Text {
                    anchors.right: parent.right
                    anchors.bottom: centreTitle.bottom
                    text: shellReady ? (shellApi.collectionCount + " in this view") : ""
                    color: window.muted
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                }
            }
            Text {
                width: parent.width
                text: shellReady ? shellApi.collectionNote : ""
                color: window.muted
                font.family: "Segoe UI"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                visible: shellReady && shellApi.searchNote !== ""
                text: shellReady ? shellApi.searchNote : ""
                color: window.accent
                font.family: "Segoe UI"
                font.pixelSize: 13
                wrapMode: Text.WordWrap
            }
            Item {
                width: parent.width
                height: 32
                Row {
                    spacing: 8
                    Rectangle {
                        objectName: "contactViewButton"
                        width: contactLabel.implicitWidth + 20
                        height: 30
                        radius: 2
                        color: contactVisible ? window.tile : "transparent"
                        border.color: contactVisible ? window.accent : window.line
                        border.width: 1
                        Text { id: contactLabel; anchors.centerIn: parent; text: "Contact sheet"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.setCentre("contact") }
                    }
                    Rectangle {
                        objectName: "spatialViewButton"
                        width: spatialLabel.implicitWidth + 20
                        height: 30
                        radius: 2
                        color: spatialVisible ? window.tile : "transparent"
                        border.color: spatialVisible ? window.accent : window.line
                        border.width: 1
                        Text { id: spatialLabel; anchors.centerIn: parent; text: "Spatial relationships"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.setCentre("spatial") }
                    }
                }
                Row {
                    anchors.right: parent.right
                    spacing: 8
                    Rectangle {
                        objectName: "resetViewButton"
                        width: resetLabel.implicitWidth + 20
                        height: 30
                        radius: 2
                        color: "transparent"
                        border.color: window.line
                        border.width: 1
                        Text { id: resetLabel; anchors.centerIn: parent; text: "Reset view"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.resetView() }
                    }
                    Rectangle {
                        width: moreLabel.implicitWidth + 20
                        height: 30
                        radius: 2
                        color: "transparent"
                        border.color: window.line
                        border.width: 1
                        Text { id: moreLabel; anchors.centerIn: parent; text: "More tools"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.toggleTools() }
                    }
                }
            }
        }

        GridView {
            id: grid
            objectName: "fieldGrid"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: centreHead.bottom
            anchors.bottom: reviewQueue.top
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            anchors.topMargin: 8
            visible: !emptySafe && contactVisible
            opacity: !focusActive ? 1 : 0
            cellWidth: 168
            cellHeight: 168
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
                    color: window.tile
                    radius: 0

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
                        border.width: (shellReady && shellApi.selectedMediaId === mediaId) ? 2 : 1
                        border.color: (shellReady && shellApi.selectedMediaId === mediaId) ? window.accent : window.line
                        radius: 0
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
                            shellApi.selectMedia(mediaId)
                        }
                        onDoubleClicked: {
                            if (!shellReady)
                                return
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
            id: altPanel
            visible: shellReady && shellApi.archiveNav !== "time" && !focusActive && !peopleVisible
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: centreHead.bottom
            anchors.bottom: parent.bottom
            anchors.margins: 22
            spacing: 12

            Text {
                width: parent.width
                text: shellReady ? shellApi.collectionNote : ""
                color: window.muted
                font.family: "Segoe UI"
                font.pixelSize: 14
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: shellReady && shellApi.archiveNav === "folders" ? shellApi.folderRows : []
                delegate: Row {
                    width: altPanel.width
                    spacing: 12
                    Text { text: modelData.label; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 14 }
                    Text { text: modelData.count; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 13 }
                }
            }
            Repeater {
                model: shellReady && shellApi.archiveNav === "unresolved" ? shellApi.reviewRows : []
                delegate: Rectangle {
                    width: altPanel.width
                    height: 64
                    radius: 2
                    color: "transparent"
                    border.color: window.line
                    border.width: 1
                    Row {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 12
                        Column {
                            width: parent.width - 100
                            spacing: 4
                            Text { text: modelData.title; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 14; elide: Text.ElideRight }
                            Text { text: modelData.detail + " · unconfirmed"; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 12 }
                        }
                        Rectangle {
                            width: 72
                            height: 28
                            radius: 2
                            anchors.verticalCenter: parent.verticalCenter
                            color: window.tile
                            border.color: window.line
                            border.width: 1
                            Text { anchors.centerIn: parent; text: "Review"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 12 }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (shellReady) shellApi.openReview(modelData.subject)
                            }
                        }
                    }
                }
            }
        }

        Item {
            objectName: "spatialEmpty"
            visible: spatialVisible && !focusActive && !peopleVisible
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: centreHead.bottom
            anchors.bottom: parent.bottom

            Canvas {
                anchors.fill: parent
                onPaint: {
                    var ctx = getContext("2d")
                    ctx.reset()
                    ctx.fillStyle = window.faint
                    var y = 16
                    while (y < height) {
                        var x = 16
                        while (x < width) {
                            ctx.fillRect(x, y, 1, 1)
                            x += 16
                        }
                        y += 16
                    }
                }
                Component.onCompleted: requestPaint()
                onWidthChanged: requestPaint()
                onHeightChanged: requestPaint()
            }
            Column {
                anchors.centerIn: parent
                width: Math.min(520, parent.width - 48)
                spacing: 10
                Text {
                    width: parent.width
                    text: "Spatial relationships"
                    color: window.fg
                    font.family: "Georgia"
                    font.italic: true
                    font.pixelSize: 28
                    horizontalAlignment: Text.AlignHCenter
                }
                Text {
                    width: parent.width
                    text: shellReady ? shellApi.spatialNote : ""
                    color: window.muted
                    font.family: "Segoe UI"
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }

        Rectangle {
            id: reviewQueue
            objectName: "reviewQueue"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: (contactVisible && !focusActive && !peopleVisible) ? 148 : 0
            visible: height > 0
            color: window.canvas
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: window.line
            }
            Column {
                anchors.fill: parent
                anchors.margins: 14
                spacing: 8
                Item {
                    width: parent.width
                    height: 20
                    Text {
                        text: "Review queue"
                        color: window.fg
                        font.family: "Georgia"
                        font.italic: true
                        font.pixelSize: 16
                    }
                    Text {
                        anchors.right: parent.right
                        text: "Suggested · your decision required"
                        color: window.muted
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                    }
                }
                Text {
                    visible: !shellReady || shellApi.reviewRows.length === 0
                    text: "No suggestions. Unknown is a valid state."
                    color: window.muted
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                }
                Flickable {
                    width: parent.width
                    height: 76
                    contentWidth: reviewRow.width
                    flickableDirection: Flickable.HorizontalFlick
                    clip: true
                    Row {
                        id: reviewRow
                        spacing: 8
                        Repeater {
                            model: shellReady ? shellApi.reviewRows : []
                            delegate: Rectangle {
                                width: 220
                                height: 72
                                radius: 2
                                color: "transparent"
                                border.color: window.line
                                border.width: 1
                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 8
                                    Rectangle {
                                        width: 44
                                        height: 44
                                        color: window.tile
                                        Image {
                                            anchors.fill: parent
                                            visible: modelData.mediaId !== ""
                                            source: modelData.mediaId !== "" ? ("image://archive/t/" + modelData.mediaId) : ""
                                            fillMode: Image.PreserveAspectCrop
                                            asynchronous: true
                                        }
                                    }
                                    Column {
                                        width: 90
                                        spacing: 2
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text { width: parent.width; text: modelData.title; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 12; elide: Text.ElideRight }
                                        Text { width: parent.width; text: modelData.detail; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 11; wrapMode: Text.WordWrap }
                                        Text { text: "Unconfirmed"; color: window.accent; font.family: "Segoe UI"; font.pixelSize: 11 }
                                    }
                                    Rectangle {
                                        width: 58
                                        height: 26
                                        radius: 2
                                        anchors.verticalCenter: parent.verticalCenter
                                        color: window.tile
                                        border.color: window.line
                                        border.width: 1
                                        Text { anchors.centerIn: parent; text: "Review"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 12 }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: if (shellReady) shellApi.openReview(modelData.subject)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Column {
            objectName: "emptyState"
            visible: emptySafe && contactVisible && !spatialVisible
            anchors.centerIn: parent
            spacing: 14
            width: 420

            Text {
                width: parent.width
                text: "Your archive is empty"
                color: "#E7EEF5"
                font.family: "Segoe UI Variable"
                font.pixelSize: 28
                font.weight: Font.DemiBold
                horizontalAlignment: Text.AlignHCenter
            }
            Text {
                width: parent.width
                text: jobRunning
                      ? "Adding the folder. The archive will appear here."
                      : "Add a folder of photos. The files stay where they are."
                color: "#8AA0B2"
                font.family: "Segoe UI"
                font.pixelSize: 15
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
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
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 22
                spacing: 8
                width: 220

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

    Rectangle {
        id: inspectorCol
        objectName: "inspectorPane"
        width: 280
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: window.chrome
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 1
            color: window.line
        }
        Flickable {
            anchors.fill: parent
            anchors.leftMargin: 1
            anchors.margins: 16
            contentHeight: inspectorBody.implicitHeight
            clip: true
            flickableDirection: Flickable.VerticalFlick
            Column {
                id: inspectorBody
                width: inspectorCol.width - 34
                spacing: 12
                Text {
                    text: "Selected"
                    color: window.faint
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                    font.letterSpacing: 1.1
                }
                Text {
                    width: parent.width
                    text: shellReady && shellApi.selectedName !== "" ? shellApi.selectedName : "Nothing selected"
                    color: window.fg
                    font.family: "Georgia"
                    font.italic: true
                    font.pixelSize: 22
                    wrapMode: Text.WordWrap
                }
                Rectangle {
                    width: parent.width
                    height: 140
                    color: window.tile
                    visible: shellReady && shellApi.selectedMediaId !== "" && shellApi.selectedKind !== "Video"
                    Image {
                        anchors.fill: parent
                        source: (shellReady && shellApi.selectedMediaId !== "") ? ("image://archive/t/" + shellApi.selectedMediaId) : ""
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                }
                Text { width: parent.width; text: shellReady ? shellApi.selectedDay : ""; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                Text { width: parent.width; text: shellReady && shellApi.selectedKind !== "" ? shellApi.selectedKind : ""; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 13 }
                Text { text: "Identity"; color: window.faint; font.family: "Segoe UI"; font.pixelSize: 11; font.letterSpacing: 1 }
                Text { width: parent.width; text: shellReady ? shellApi.selectedIdentity : "Unknown"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                Text { text: "Place"; color: window.faint; font.family: "Segoe UI"; font.pixelSize: 11; font.letterSpacing: 1 }
                Text { width: parent.width; text: shellReady ? shellApi.selectedPlace : ""; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 13; wrapMode: Text.WordWrap }
                Text {
                    width: parent.width
                    text: "The review queue lists unnamed groups. This photo is not added to it from here."
                    color: window.muted
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
                Text {
                    width: parent.width
                    text: "Regions are drawn in Focus. Nothing is inspected until you draw."
                    color: window.muted
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    wrapMode: Text.WordWrap
                }
                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 2
                    color: window.tile
                    border.color: window.accent
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "Open Focus & details"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady && shellApi.selectedMediaId !== "") shellApi.openFocus(shellApi.selectedMediaId)
                    }
                }
                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 2
                    color: "transparent"
                    border.color: window.line
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "Find similar"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (shellReady) shellApi.prepareSimilar()
                    }
                }
            }
        }
    }

    Rectangle {
        objectName: "toolsPanel"
        visible: shellReady && shellApi.toolsOpen
        width: 320
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        z: 30
        color: window.chrome
        border.color: window.line
        border.width: 1
        Flickable {
            anchors.fill: parent
            anchors.margins: 16
            contentHeight: toolsBody.implicitHeight
            clip: true
            Column {
                id: toolsBody
                width: 288
                spacing: 12
                Text { text: "Index & Tools"; color: window.fg; font.family: "Georgia"; font.italic: true; font.pixelSize: 22 }
                Text {
                    width: parent.width
                    text: "Tools that exist in this archive. Nothing here runs unless you use it. Diagnostics stay in this panel."
                    color: window.muted
                    wrapMode: Text.WordWrap
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                }
                Row {
                    spacing: 8
                    Rectangle {
                        objectName: "primaryModeButton"
                        width: 74
                        height: 28
                        radius: 2
                        color: primaryModeSafe ? window.selectBg : "transparent"
                        border.color: primaryModeSafe ? window.accent : window.line
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "Primary"; color: window.fg; font.pixelSize: 12; font.family: "Segoe UI" }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.setMode("primary") }
                    }
                    Rectangle {
                        objectName: "advancedModeButton"
                        width: 84
                        height: 28
                        radius: 2
                        color: advancedModeSafe ? window.selectBg : "transparent"
                        border.color: advancedModeSafe ? window.accent : window.line
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "Advanced"; color: window.fg; font.pixelSize: 12; font.family: "Segoe UI" }
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.setMode("advanced") }
                    }
                }
                Text { text: "Appearance"; color: window.faint; font.pixelSize: 11; font.family: "Segoe UI"; font.letterSpacing: 1 }
                Text {
                    width: parent.width
                    text: "Light is the warm palette. Every other stored atmosphere uses the editorial dark palette in this shell."
                    color: window.muted
                    wrapMode: Text.WordWrap
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                }
                ComboBox {
                    id: atmospherePicker
                    objectName: "atmospherePicker"
                    width: parent.width
                    model: shellReady ? shellApi.atmosphereChoices : []
                    textRole: "label"
                    onActivated: if (shellReady && currentIndex >= 0 && model.length > currentIndex) {
                        shellApi.setAtmosphere(model[currentIndex].id)
                    }
                    Component.onCompleted: {
                        if (!shellReady)
                            return
                        for (var i = 0; i < model.length; ++i) {
                            if (model[i].id === atmosphereIdSafe) {
                                currentIndex = i
                                break
                            }
                        }
                    }
                    Connections {
                        target: shellApi
                        function onLensChanged() {
                            for (var i = 0; i < atmospherePicker.model.length; ++i) {
                                if (atmospherePicker.model[i].id === atmosphereIdSafe) {
                                    atmospherePicker.currentIndex = i
                                    return
                                }
                            }
                        }
                    }
                }
                Rectangle {
                    width: parent.width
                    height: 32
                    radius: 2
                    color: window.tile
                    border.color: window.line
                    border.width: 1
                    visible: !jobRunning
                    Text { anchors.centerIn: parent; text: "Add a folder"; color: window.fg; font.family: "Segoe UI"; font.pixelSize: 13 }
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.addFolder() }
                }
                Rectangle {
                    id: command
                    width: parent.width
                    height: 34
                    radius: 2
                    visible: advancedModeSafe
                    color: window.canvas
                    border.color: commandField.activeFocus ? window.accent : window.line
                    border.width: 1
                    TextField {
                        id: commandField
                        objectName: "commandField"
                        visible: advancedModeSafe
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        anchors.rightMargin: 8
                        verticalAlignment: TextInput.AlignVCenter
                        placeholderText: "Command: people, status"
                        placeholderTextColor: window.faint
                        color: window.fg
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        background: Item {}
                        selectByMouse: true
                        onAccepted: if (shellReady) shellApi.submitCommand(text)
                    }
                }
                Row {
                    objectName: "processingMark"
                    visible: jobRunning
                    spacing: 10
                    Text { text: jobLabelSafe; color: window.muted; font.family: "Segoe UI"; font.pixelSize: 13 }
                    Text {
                        objectName: "pauseJob"
                        text: jobStateSafe === "paused" ? "Resume" : "Pause"
                        color: window.fg
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        MouseArea {
                            anchors.fill: parent
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
                        color: window.fg
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.cancelJob() }
                    }
                }
                Text {
                    objectName: "resumeJob"
                    text: "Resume"
                    visible: shellReady && shellApi.canResume && !shellApi.jobActive
                    color: window.fg
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.resumeJob() }
                }
                Text {
                    text: "Close"
                    color: window.accent
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    MouseArea { anchors.fill: parent; anchors.margins: -4; cursorShape: Qt.PointingHandCursor; onClicked: if (shellReady) shellApi.closeTools() }
                }
            }
        }
    }
    }
}
