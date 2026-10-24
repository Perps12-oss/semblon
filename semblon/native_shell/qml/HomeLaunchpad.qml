import QtQuick
import QtQuick.Controls

// First arrival and return desk. One reading surface, not a dashboard.
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
    property color tokenBg: "#10161C"
    property color tokenBg1: "#141A22"
    property color tokenBg2: "#1C2430"
    property color tokenBg3: "#243044"
    property color tokenAccent: "#2DD4BF"
    property color tokenAccentDim: "#12343A"
    property color tokenText: "#F4F7FB"
    property color tokenMuted: "#A8B3C2"
    property color tokenFaint: "#7E8B9C"
    property color tokenBorder: "#2A3544"

    property bool catalogueOpen: false
    property string catalogueFilter: ""

    readonly property string displayFace: "Noto Serif"
    readonly property string uiFace: "Inter"

    readonly property var catalogueRows: [
        { id: "library", title: "Library", body: "Walk through your pictures by time.", action: "library", availability: "Ready", advanced: false },
        { id: "discover", title: "Visual discovery", body: "Open a picture, point at a detail, and find it again.", action: "discover", availability: "Ready", advanced: false },
        { id: "people", title: "People", body: "Look at suggested groups. A group is not a person until you name them.", action: "people", availability: "Ready", advanced: false },
        { id: "searchNames", title: "Search names", body: "Find someone you have already named.", action: "searchNames", availability: "Ready", advanced: false },
        { id: "searchText", title: "Text in photos", body: "Find words that appear inside pictures, when reading text is ready.", action: "searchText", availability: "Extra", advanced: false },
        { id: "searchObjects", title: "Things in photos", body: "Find things Semblon can recognise, once that extra piece is installed.", action: "searchObjects", availability: "Extra", advanced: false },
        { id: "ask", title: "Ask about a picture", body: "Read what Semblon can say about the open picture.", action: "ask", availability: "Ready", advanced: false },
        { id: "keeps", title: "Kept finds", body: "Open a search you saved, with the same picture and the same detail.", action: "keeps", availability: "Ready", advanced: false },
        { id: "activity", title: "Recent activity", body: "See what was added and what finished.", action: "activity", availability: "Ready", advanced: false },
        { id: "duplicates", title: "Copies", body: "Look for pictures that are the same, or nearly the same.", action: "duplicates", availability: "More options", advanced: true },
        { id: "appearance", title: "Look and feel", body: "Colour theme and photo size live in Settings.", action: "appearance", availability: "Ready", advanced: false }
    ]

    function inkOn(bg) {
        function lin(u) {
            return u <= 0.03928 ? u / 12.92 : Math.pow((u + 0.055) / 1.055, 2.4)
        }
        var L = 0.2126 * lin(bg.r) + 0.7152 * lin(bg.g) + 0.0722 * lin(bg.b)
        return L > 0.42 ? "#101418" : "#f7f4ee"
    }

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

    // Signature rule. Marks this as a desk, not a panel.
    Rectangle {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 3
        color: tokenAccent
    }

    Flickable {
        id: scroll
        anchors.fill: parent
        anchors.leftMargin: 3
        contentWidth: width
        contentHeight: page.implicitHeight + 96
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        Column {
            id: page
            width: Math.min(1040, parent.width - 72)
            x: 36
            y: 28
            spacing: 16

            Column {
                width: parent.width
                spacing: 28
                visible: !catalogueOpen

                Column {
                    width: parent.width
                    spacing: 10

                    Text {
                        text: "A PRIVATE PLACE FOR YOUR PICTURES"
                        color: tokenAccent
                        font.family: root.uiFace
                        font.pixelSize: 11
                        font.letterSpacing: 2.2
                        font.weight: Font.DemiBold
                    }
                    Text {
                        width: Math.min(parent.width, 640)
                        text: "There is more to remember."
                        color: tokenText
                        font.family: root.displayFace
                        font.pixelSize: parent.width < 640 ? 36 : 44
                        font.weight: Font.Medium
                        lineHeight: 0.95
                        wrapMode: Text.WordWrap
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                    Text {
                        width: Math.min(parent.width, 560)
                        text: emptyArchive
                              ? "Your pictures stay in their folders. Add one folder, open a picture, and point at something you want to find again."
                              : "Open a picture, point at a detail, or return to someone you have already named."
                        color: tokenMuted
                        font.family: root.uiFace
                        font.pixelSize: 16
                        lineHeight: 1.35
                        wrapMode: Text.WordWrap
                    }
                }

                Column {
                    width: Math.min(parent.width, 640)
                    spacing: 8

                    Rectangle {
                        width: parent.width
                        height: 52
                        radius: 0
                        color: "transparent"
                        border.color: homeSearch.activeFocus ? tokenAccent : tokenBorder
                        border.width: homeSearch.activeFocus ? 1.5 : 1

                        Row {
                            anchors.fill: parent
                            anchors.leftMargin: 16
                            anchors.rightMargin: 12
                            spacing: 10

                            TextField {
                                id: homeSearch
                                objectName: "homeSearchField"
                                width: parent.width - modeChip.width - 10
                                height: parent.height
                                verticalAlignment: TextInput.AlignVCenter
                                placeholderText: emptyArchive ? "Search names after you have named someone" : "Search names"
                                placeholderTextColor: tokenFaint
                                color: tokenText
                                font.family: root.uiFace
                                font.pixelSize: 15
                                background: Item {}
                                selectByMouse: true
                                Accessible.name: "Search names"
                                onAccepted: if (shellReady) shellApi.submitCommand(text)
                            }
                            Rectangle {
                                id: modeChip
                                width: modeChipLabel.implicitWidth + 16
                                height: 26
                                radius: 0
                                anchors.verticalCenter: parent.verticalCenter
                                color: "transparent"
                                border.color: tokenBorder
                                border.width: 1
                                Text {
                                    id: modeChipLabel
                                    anchors.centerIn: parent
                                    text: searchModeShort
                                    color: tokenMuted
                                    font.family: root.uiFace
                                    font.pixelSize: 11
                                    font.letterSpacing: 0.6
                                }
                            }
                        }
                    }
                    Text {
                        width: parent.width
                        text: "This looks up people you have named. Words inside pictures, and things in pictures, are other searches in Settings. A detail search starts from Visual discovery."
                        color: tokenFaint
                        font.family: root.uiFace
                        font.pixelSize: 12
                        wrapMode: Text.WordWrap
                    }
                }

                Column {
                    width: parent.width
                    spacing: 14

                    Text {
                        objectName: "emptyStatus"
                        width: Math.min(parent.width, 640)
                        visible: jobLabel !== "" || canResume
                        text: jobLabel === "Last add failed"
                              ? "The last add didn't finish. Your pictures were not changed. Try again, or choose another folder."
                              : (canResume ? "The last add was stopped. Resume it, or choose another folder." : jobLabel)
                        color: tokenMuted
                        font.family: root.uiFace
                        font.pixelSize: 14
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        width: Math.min(parent.width, 640)
                        visible: jobRunning
                        text: "Adding your folder. Pictures that are ready can already be opened in the library."
                        color: tokenMuted
                        font.family: root.uiFace
                        font.pixelSize: 15
                        wrapMode: Text.WordWrap
                    }

                    Rectangle {
                        objectName: "homeAddFolder"
                        width: Math.max(240, addPrimaryLabel.implicitWidth + 56)
                        height: 56
                        radius: 0
                        visible: emptyArchive && !jobRunning
                        color: addPrimaryArea.containsMouse ? tokenText : tokenAccent
                        border.width: addPrimaryArea.activeFocus ? 2 : 0
                        border.color: tokenText

                        Text {
                            id: addPrimaryLabel
                            anchors.centerIn: parent
                            text: "Add a folder"
                            color: addPrimaryArea.containsMouse ? tokenBg : root.inkOn(parent.color)
                            font.family: root.uiFace
                            font.pixelSize: 16
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.4
                        }
                        MouseArea {
                            id: addPrimaryArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            Accessible.name: "Add a folder of pictures"
                            Accessible.role: Accessible.Button
                            onClicked: root.runAction("addFolder")
                        }
                    }

                    Row {
                        spacing: 18
                        visible: !emptyArchive && !jobRunning

                        Text {
                            text: archiveSummary !== "" ? archiveSummary : "Your library is ready."
                            color: tokenText
                            font.family: root.displayFace
                            font.pixelSize: 20
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            objectName: "homeAddFolderQuiet"
                            text: "Add a folder"
                            color: quietAddArea.containsMouse ? tokenText : tokenAccent
                            font.family: root.uiFace
                            font.pixelSize: 14
                            font.underline: quietAddArea.containsMouse
                            anchors.verticalCenter: parent.verticalCenter
                            Accessible.name: "Add another folder"
                            Accessible.role: Accessible.Button
                            MouseArea {
                                id: quietAddArea
                                anchors.fill: parent
                                anchors.margins: -6
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.runAction("addFolder")
                            }
                        }
                    }

                    Rectangle {
                        objectName: "emptyResume"
                        width: resumeEmptyLabel.implicitWidth + 36
                        height: 44
                        radius: 0
                        color: resumeEmptyArea.containsMouse ? tokenAccentDim : "transparent"
                        border.color: tokenAccent
                        border.width: 1
                        visible: canResume && !jobRunning
                        Text {
                            id: resumeEmptyLabel
                            objectName: "resumeJob"
                            anchors.centerIn: parent
                            text: jobLabel === "Last add failed" ? "Try again" : "Resume"
                            color: tokenText
                            font.family: root.uiFace
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: resumeEmptyArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            Accessible.name: resumeEmptyLabel.text
                            Accessible.role: Accessible.Button
                            onClicked: root.runAction("resume")
                        }
                    }
                }

                Column {
                    id: firstRunGuide
                    objectName: "firstRunGuide"
                    width: parent.width
                    spacing: 0
                    visible: emptyArchive && !jobRunning

                    Text {
                        text: "START HERE"
                        color: tokenFaint
                        font.family: root.uiFace
                        font.pixelSize: 11
                        font.letterSpacing: 1.8
                        bottomPadding: 12
                    }

                    Repeater {
                        model: [
                            { n: "01", title: "Add pictures", body: "Choose a folder. Semblon reads it here and leaves the files where they are." },
                            { n: "02", title: "Point at a detail", body: "Open one picture and point, or draw around the thing you want to find again." },
                            { n: "03", title: "Name someone only when you are sure", body: "Suggested groups are not people. Unknown is a fine answer." }
                        ]
                        delegate: Column {
                            width: firstRunGuide.width
                            spacing: 0

                            Rectangle {
                                width: parent.width
                                height: 1
                                color: tokenBorder
                            }
                            Row {
                                width: parent.width
                                spacing: 18
                                topPadding: 8
                                bottomPadding: 8

                                Text {
                                    text: modelData.n
                                    color: tokenAccent
                                    font.family: root.displayFace
                                    font.pixelSize: 22
                                    width: 48
                                }
                                Column {
                                    width: parent.width - 66
                                    spacing: 4
                                    Text {
                                        text: modelData.title
                                        color: tokenText
                                        font.family: root.displayFace
                                        font.pixelSize: 20
                                        wrapMode: Text.WordWrap
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.body
                                        color: tokenMuted
                                        font.family: root.uiFace
                                        font.pixelSize: 14
                                        wrapMode: Text.WordWrap
                                    }
                                }
                            }
                        }
                    }
                    Rectangle {
                        width: parent.width
                        height: 1
                        color: tokenBorder
                    }
                }

                Column {
                    width: parent.width
                    spacing: 14

                    Text {
                        text: "GO FURTHER"
                        color: tokenFaint
                        font.family: root.uiFace
                        font.pixelSize: 11
                        font.letterSpacing: 1.8
                    }

                    Grid {
                        width: parent.width
                        columns: parent.width < 720 ? 1 : 3
                        columnSpacing: 18
                        rowSpacing: 18

                        Repeater {
                            model: [
                                { objectName: "archiveCard", index: "01", title: "Library", action: "library" },
                                { objectName: "discoverCard", index: "02", title: "Visual discovery", action: "discover" },
                                { objectName: "peopleCard", index: "03", title: "People", action: "people" }
                            ]
                            delegate: Rectangle {
                                objectName: modelData.objectName
                                width: page.width < 720 ? page.width : (page.width - 36) / 3
                                height: cardCol.implicitHeight + 36
                                radius: 0
                                color: cardArea.containsMouse ? tokenBg1 : "transparent"
                                border.color: cardArea.containsMouse ? tokenAccent : tokenBorder
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

                                Column {
                                    id: cardCol
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 16
                                    spacing: 8

                                    Text {
                                        text: modelData.index
                                        color: tokenAccent
                                        font.family: root.displayFace
                                        font.pixelSize: 13
                                        font.letterSpacing: 1
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.title
                                        color: tokenText
                                        font.family: root.displayFace
                                        font.pixelSize: 22
                                        wrapMode: Text.WordWrap
                                    }
                                    Text {
                                        width: parent.width
                                        text: cardBody
                                        color: tokenMuted
                                        font.family: root.uiFace
                                        font.pixelSize: 13
                                        wrapMode: Text.WordWrap
                                        lineHeight: 1.3
                                    }
                                }
                                MouseArea {
                                    id: cardArea
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    Accessible.name: modelData.title
                                    Accessible.role: Accessible.Button
                                    onClicked: root.runAction(modelData.action)
                                }
                            }
                        }
                    }
                }

                Row {
                    spacing: 16

                    Text {
                        text: "There is more to explore."
                        color: tokenFaint
                        font.family: root.uiFace
                        font.pixelSize: 13
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        objectName: "exploreAllCapabilities"
                        text: "Explore all capabilities"
                        color: catalogueLinkArea.containsMouse ? tokenText : tokenAccent
                        font.family: root.uiFace
                        font.pixelSize: 14
                        font.underline: catalogueLinkArea.containsMouse
                        Accessible.name: "Explore all capabilities"
                        Accessible.role: Accessible.Button
                        MouseArea {
                            id: catalogueLinkArea
                            anchors.fill: parent
                            anchors.margins: -6
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

            Column {
                width: parent.width
                spacing: 18
                visible: catalogueOpen

                Text {
                    objectName: "catalogueBack"
                    text: "Back to the start"
                    color: backArea.containsMouse ? tokenText : tokenAccent
                    font.family: root.uiFace
                    font.pixelSize: 14
                    Accessible.name: "Back to the start"
                    Accessible.role: Accessible.Button
                    MouseArea {
                        id: backArea
                        anchors.fill: parent
                        anchors.margins: -6
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: catalogueOpen = false
                    }
                }
                Text {
                    width: parent.width
                    text: "What you can do"
                    color: tokenText
                    font.family: root.displayFace
                    font.pixelSize: 40
                    wrapMode: Text.WordWrap
                }
                Text {
                    width: Math.min(parent.width, 560)
                    text: "Every door below is something Semblon can already do. Extras say so before you open them."
                    color: tokenMuted
                    font.family: root.uiFace
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                }

                Rectangle {
                    width: Math.min(parent.width, 480)
                    height: 44
                    color: "transparent"
                    border.color: catalogueSearch.activeFocus ? tokenAccent : tokenBorder
                    border.width: 1
                    TextField {
                        id: catalogueSearch
                        objectName: "catalogueFilterField"
                        anchors.fill: parent
                        anchors.leftMargin: 14
                        anchors.rightMargin: 14
                        verticalAlignment: TextInput.AlignVCenter
                        placeholderText: "Find something you can do"
                        placeholderTextColor: tokenFaint
                        color: tokenText
                        font.family: root.uiFace
                        font.pixelSize: 14
                        background: Item {}
                        selectByMouse: true
                        Accessible.name: "Find something you can do"
                        onTextChanged: catalogueFilter = text
                    }
                }

                Repeater {
                    model: catalogueRows
                    delegate: Rectangle {
                        width: page.width
                        height: visible ? catCol.implicitHeight + 28 : 0
                        visible: root.rowVisible(modelData)
                        color: catArea.containsMouse ? tokenBg1 : "transparent"
                        border.color: tokenBorder
                        border.width: visible ? 1 : 0

                        Column {
                            id: catCol
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 16
                            spacing: 4
                            Row {
                                spacing: 12
                                Text {
                                    text: modelData.title
                                    color: tokenText
                                    font.family: root.displayFace
                                    font.pixelSize: 20
                                }
                                Text {
                                    text: modelData.availability
                                    color: tokenFaint
                                    font.family: root.uiFace
                                    font.pixelSize: 12
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }
                            Text {
                                width: parent.width
                                text: modelData.body
                                color: tokenMuted
                                font.family: root.uiFace
                                font.pixelSize: 14
                                wrapMode: Text.WordWrap
                            }
                        }
                        MouseArea {
                            id: catArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            Accessible.name: modelData.title
                            Accessible.role: Accessible.Button
                            onClicked: root.runAction(modelData.action)
                        }
                    }
                }
            }
        }
    }
}
