import QtQuick
import QtQuick.Controls

// Permanent editorial launchpad. Visible empty or populated — never onboarding-only.
Item {
    id: root
    objectName: "emptyState"

    property var shellApi: null
    property bool shellReady: false
    property bool emptyArchive: true
    property bool jobRunning: false
    property bool canResume: false
    property string jobLabel: ""
    property string archiveSummary: ""
    property string searchModeShort: "Names"
    property bool advancedMode: false
    property color tokenBg: "#0a0b10"
    property color tokenBg1: "#151820"
    property color tokenBg2: "#22252d"
    property color tokenBg3: "#2c303a"
    property color tokenAccent: "#4f8cff"
    property color tokenAccentDim: "#2b4d8f"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2f3a"

    property bool catalogueOpen: false
    property string catalogueFilter: ""

    readonly property var catalogueRows: [
        { id: "library", title: "Library", body: "Browse the collection, including its timeline.", action: "library", availability: "Available", advanced: false },
        { id: "discover", title: "Visual discovery", body: "Point or draw inside a photo to find similar regions.", action: "discover", availability: "Available", advanced: false },
        { id: "people", title: "People", body: "Review groupings. A group is not yet a person.", action: "people", availability: "Available", advanced: false },
        { id: "searchNames", title: "Search names", body: "Find named people from what you remember.", action: "searchNames", availability: "Available", advanced: false },
        { id: "searchText", title: "Text in photos", body: "Search text found in photos when OCR is available.", action: "searchText", availability: "Optional", advanced: false },
        { id: "searchObjects", title: "Objects in photos", body: "Search labelled objects when an object pack is installed.", action: "searchObjects", availability: "Optional", advanced: false },
        { id: "ask", title: "Ask photo", body: "Read and describe the open photo.", action: "ask", availability: "Available", advanced: false },
        { id: "keeps", title: "Kept finds", body: "Reopen a visual search you saved.", action: "keeps", availability: "Available", advanced: false },
        { id: "activity", title: "Activity", body: "Recent imports and processing.", action: "activity", availability: "Available", advanced: false },
        { id: "duplicates", title: "Duplicates", body: "Find exact and near duplicates.", action: "duplicates", availability: "Advanced", advanced: true },
        { id: "appearance", title: "Appearance", body: "Theme and density live in Settings.", action: "appearance", availability: "Available", advanced: false }
    ]

    function rowVisible(row) {
        if (row.advanced && !advancedMode)
            return false
        var q = String(catalogueFilter || "").trim().toLowerCase()
        if (!q)
            return true
        return String(row.title).toLowerCase().indexOf(q) >= 0
               || String(row.body).toLowerCase().indexOf(q) >= 0
    }

    function runAction(action) {
        if (!shellReady || !shellApi)
            return
        if (action === "library")
            shellApi.showLibrary()
        else if (action === "discover")
            shellApi.openVisualDiscovery()
        else if (action === "people")
            shellApi.openPeople()
        else if (action === "searchNames") {
            shellApi.setSearchMode("people")
            shellApi.showLibrary()
        } else if (action === "searchText") {
            shellApi.setSearchMode("text")
            shellApi.showLibrary()
        } else if (action === "searchObjects") {
            shellApi.setSearchMode("object")
            shellApi.showLibrary()
        } else if (action === "ask") {
            shellApi.openVisualDiscovery()
            if (!emptyArchive)
                shellApi.askPhoto()
        } else if (action === "keeps") {
            if (shellApi.keptCount > 0)
                shellApi.openKept(0)
            else
                shellApi.showLibrary()
        } else if (action === "activity")
            shellApi.showActivity()
        else if (action === "duplicates")
            shellApi.scanDuplicates()
        else if (action === "appearance")
            shellApi.toggleSettings()
        else if (action === "addFolder") {
            if (!jobRunning)
                shellApi.addFolder()
        } else if (action === "resume")
            shellApi.resumeJob()
    }

    Rectangle {
        anchors.fill: parent
        color: tokenBg
    }

    Flickable {
        id: scroll
        anchors.fill: parent
        contentWidth: width
        contentHeight: page.implicitHeight + 80
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
            id: page
            width: Math.min(760, parent.width - 64)
            anchors.horizontalCenter: parent.horizontalCenter
            y: 48
            spacing: 18

            // —— Launchpad ——
            Column {
                width: parent.width
                spacing: 18
                visible: !catalogueOpen

                Text {
                    width: parent.width
                    text: "YOUR VISUAL MEMORY"
                    color: tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    font.letterSpacing: 1.2
                    horizontalAlignment: Text.AlignHCenter
                }
                Text {
                    width: parent.width
                    text: "There is more to remember."
                    color: tokenText
                    font.family: "Segoe UI Variable"
                    font.pixelSize: 28
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }
                Text {
                    width: parent.width
                    text: "Find a photo, follow a visual detail, or explore a connection you hadn't noticed."
                    color: tokenMuted
                    font.family: "Segoe UI"
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                }

                // Search well
                Column {
                    width: parent.width
                    spacing: 8

                    Rectangle {
                        width: parent.width
                        height: 44
                        radius: 10
                        color: tokenBg2
                        border.color: homeSearch.activeFocus ? tokenAccent : tokenBorder
                        border.width: 1

                        Row {
                            anchors.fill: parent
                            anchors.leftMargin: 14
                            anchors.rightMargin: 12
                            spacing: 10

                            TextField {
                                id: homeSearch
                                objectName: "homeSearchField"
                                width: parent.width - modeChip.width - 10
                                height: parent.height
                                verticalAlignment: TextInput.AlignVCenter
                                placeholderText: "Search names"
                                placeholderTextColor: tokenFaint
                                color: tokenText
                                font.family: "Segoe UI"
                                font.pixelSize: 14
                                background: Item {}
                                selectByMouse: true
                                onAccepted: if (shellReady) shellApi.submitCommand(text)
                            }
                            Rectangle {
                                id: modeChip
                                width: modeChipLabel.implicitWidth + 16
                                height: 26
                                radius: 6
                                anchors.verticalCenter: parent.verticalCenter
                                color: tokenBg3
                                border.color: tokenBorder
                                border.width: 1
                                Text {
                                    id: modeChipLabel
                                    anchors.centerIn: parent
                                    text: searchModeShort
                                    color: tokenMuted
                                    font.family: "Segoe UI"
                                    font.pixelSize: 11
                                }
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        text: "Typing searches names. Text in photos and objects are other modes in Settings. A region search starts from Visual discovery."
                        color: tokenFaint
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }
                }

                // State band
                Column {
                    width: parent.width
                    spacing: 10

                    Text {
                        objectName: "emptyStatus"
                        width: parent.width
                        visible: jobLabel !== "" || canResume
                        text: jobLabel === "Last add failed"
                              ? "The last add didn't finish. Try again or choose another folder."
                              : (canResume ? "The last add was stopped. Resume it or choose another folder." : jobLabel)
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }

                    Text {
                        width: parent.width
                        visible: jobRunning
                        text: "Adding your folder. The library will unlock here as media is indexed."
                        color: tokenMuted
                        font.family: "Segoe UI"
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                        horizontalAlignment: Text.AlignHCenter
                    }

                    // Empty: dominant Add a folder
                    Rectangle {
                        objectName: "homeAddFolder"
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: Math.max(180, addPrimaryLabel.implicitWidth + 48)
                        height: 44
                        radius: 8
                        visible: emptyArchive && !jobRunning
                        color: addPrimaryArea.containsMouse ? tokenAccentDim : tokenAccent
                        Text {
                            id: addPrimaryLabel
                            anchors.centerIn: parent
                            text: "Add a folder"
                            color: tokenText
                            font.family: "Segoe UI"
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                        }
                        MouseArea {
                            id: addPrimaryArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.runAction("addFolder")
                        }
                    }

                    // Loaded: compact summary + quiet add
                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: 16
                        visible: !emptyArchive && !jobRunning

                        Text {
                            text: archiveSummary
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            objectName: "homeAddFolderQuiet"
                            text: "Add a folder"
                            color: quietAddArea.containsMouse ? tokenText : tokenAccent
                            font.family: "Segoe UI"
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                            MouseArea {
                                id: quietAddArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.runAction("addFolder")
                            }
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
                        visible: canResume && !jobRunning
                        Text {
                            id: resumeEmptyLabel
                            objectName: "resumeJob"
                            anchors.centerIn: parent
                            text: jobLabel === "Last add failed" ? "Try again" : "Resume"
                            color: tokenText
                            font.family: "Segoe UI"
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: resumeEmptyArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.runAction("resume")
                        }
                    }
                }

                Text {
                    width: parent.width
                    text: "Explore"
                    color: tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    font.letterSpacing: 0.6
                    horizontalAlignment: Text.AlignHCenter
                }

                // Capability cards
                Column {
                    width: parent.width
                    spacing: 12

                    Repeater {
                        model: [
                            { objectName: "archiveCard", icon: "library", title: "Library", action: "library" },
                            { objectName: "discoverCard", icon: "similar", title: "Visual discovery", action: "discover" },
                            { objectName: "peopleCard", icon: "people", title: "People", action: "people" }
                        ]
                        delegate: Rectangle {
                            objectName: modelData.objectName
                            width: page.width
                            height: cardCol.implicitHeight + 28
                            radius: 12
                            color: cardArea.containsMouse ? tokenBg2 : tokenBg1
                            border.color: tokenBorder
                            border.width: 1
                            readonly property string cardBody: {
                                if (modelData.action === "library")
                                    return "Browse the collection, including its timeline."
                                if (modelData.action === "discover")
                                    return emptyArchive
                                           ? "Point or draw inside a photo to find similar regions. Add a folder first."
                                           : "Point or draw inside a photo to find similar regions."
                                return "Review groupings. A group is not yet a person."
                            }

                            Row {
                                id: cardCol
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                spacing: 14

                                DuotoneIcon {
                                    width: 22
                                    height: 22
                                    icon: modelData.icon
                                    fillColor: tokenAccent
                                    cutoutColor: tokenBg1
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Column {
                                    width: parent.width - 36
                                    spacing: 4
                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        color: tokenText
                                        font.family: "Segoe UI"
                                        font.pixelSize: 16
                                        font.weight: Font.DemiBold
                                        wrapMode: Text.WordWrap
                                    }
                                    Text {
                                        width: parent.width
                                        text: cardBody
                                        color: tokenMuted
                                        font.family: "Segoe UI"
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                            MouseArea {
                                id: cardArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.runAction(modelData.action)
                            }
                        }
                    }
                }

                Column {
                    width: parent.width
                    spacing: 6
                    topPadding: 8

                    Text {
                        width: parent.width
                        text: "There is more to explore"
                        color: tokenFaint
                        font.family: "Segoe UI"
                        font.pixelSize: 12
                        horizontalAlignment: Text.AlignHCenter
                    }
                    Text {
                        objectName: "exploreAllCapabilities"
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Explore all capabilities"
                        color: catalogueLinkArea.containsMouse ? tokenText : tokenAccent
                        font.family: "Segoe UI"
                        font.pixelSize: 14
                        MouseArea {
                            id: catalogueLinkArea
                            anchors.fill: parent
                            anchors.margins: -4
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                catalogueOpen = true
                                catalogueFilter = ""
                            }
                        }
                    }
                }
            }

            // —— Catalogue ——
            Column {
                width: parent.width
                spacing: 14
                visible: catalogueOpen

                Row {
                    width: parent.width
                    spacing: 12
                    Text {
                        objectName: "catalogueBack"
                        text: "← Home"
                        color: backArea.containsMouse ? tokenText : tokenAccent
                        font.family: "Segoe UI"
                        font.pixelSize: 14
                        anchors.verticalCenter: parent.verticalCenter
                        MouseArea {
                            id: backArea
                            anchors.fill: parent
                            anchors.margins: -4
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: catalogueOpen = false
                        }
                    }
                    Text {
                        text: "All capabilities"
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 20
                        font.weight: Font.DemiBold
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                Rectangle {
                    width: parent.width
                    height: 36
                    radius: 8
                    color: tokenBg2
                    border.color: catalogueSearch.activeFocus ? tokenAccent : tokenBorder
                    border.width: 1
                    TextField {
                        id: catalogueSearch
                        objectName: "catalogueFilterField"
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        verticalAlignment: TextInput.AlignVCenter
                        placeholderText: "Filter capabilities"
                        placeholderTextColor: tokenFaint
                        color: tokenText
                        font.family: "Segoe UI"
                        font.pixelSize: 13
                        background: Item {}
                        selectByMouse: true
                        onTextChanged: catalogueFilter = text
                    }
                }

                Repeater {
                    model: catalogueRows
                    delegate: Rectangle {
                        width: page.width
                        height: catCol.implicitHeight + 24
                        radius: 10
                        visible: root.rowVisible(modelData)
                        color: catArea.containsMouse ? tokenBg2 : tokenBg1
                        border.color: tokenBorder
                        border.width: 1

                        Column {
                            id: catCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 14
                            spacing: 4
                            Row {
                                spacing: 10
                                Text {
                                    text: modelData.title
                                    color: tokenText
                                    font.family: "Segoe UI"
                                    font.pixelSize: 15
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    text: modelData.availability
                                    color: tokenFaint
                                    font.family: "Segoe UI"
                                    font.pixelSize: 11
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            Text {
                                width: parent.width
                                text: modelData.body
                                color: tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                            }
                        }
                        MouseArea {
                            id: catArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.runAction(modelData.action)
                        }
                    }
                }
            }
        }
    }
}
