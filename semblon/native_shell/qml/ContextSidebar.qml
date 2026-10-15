import QtQuick
import QtQuick.Controls

// Archive browse controls for the left navigation column.
// Not a second floating "Explore" product panel.
Item {
    id: root
    objectName: "archiveSidebar"
    Accessible.name: "Archive browse"

    property var shellApi: null
    property bool shellReady: false
    property bool advancedMode: false
    property color tokenBg1: "#131417"
    property color tokenBg2: "#1b1d21"
    property color tokenBg3: "#24272c"
    property color tokenAccent: "#4f8cff"
    property color tokenText: "#f2f3f5"
    property color tokenMuted: "#a8adb7"
    property color tokenFaint: "#6b7280"
    property color tokenBorder: "#2a2d33"
    property int motion: 180

    property bool foldersOpen: true
    property bool momentsOpen: false
    property bool similarOpen: true
    property bool mediaOpen: true
    property string searchQuery: ""

    readonly property var folderRows: shellReady ? shellApi.folderRows : []
    readonly property var momentRows: shellReady && shellApi.facet === "moments" ? shellApi.buckets : []
    readonly property string searchNorm: searchQuery.trim().toLowerCase()
    readonly property real contentHeight: column.implicitHeight

    function rowMatches(label) {
        if (searchNorm === "")
            return true
        return String(label || "").toLowerCase().indexOf(searchNorm) >= 0
    }

    function filteredFolders() {
        var src = folderRows
        var out = []
        for (var i = 0; i < src.length; i++) {
            if (rowMatches(src[i].displayName || src[i].label))
                out.push(src[i])
        }
        return out
    }

    function filteredMoments() {
        var src = momentRows
        var out = []
        for (var i = 0; i < src.length; i++) {
            if (rowMatches(src[i].label))
                out.push(src[i])
        }
        return out
    }

    function toggleSection(name) {
        if (name === "folders") foldersOpen = !foldersOpen
        else if (name === "moments") momentsOpen = !momentsOpen
        else if (name === "similar") similarOpen = !similarOpen
        else if (name === "media") mediaOpen = !mediaOpen
    }

    Column {
        id: column
        width: parent.width
        spacing: 10

        Rectangle {
            width: parent.width
            height: 1
            color: tokenBorder
            opacity: 0.85
        }

        Text {
            objectName: "contextSidebarTitle"
            width: parent.width
            text: "Browse"
            color: tokenFaint
            font.family: "Segoe UI"
            font.pixelSize: 11
            font.letterSpacing: 0.5
            font.weight: Font.DemiBold
        }

        Rectangle {
            width: parent.width
            height: 30
            radius: 6
            color: tokenBg2
            border.color: folderSearch.activeFocus ? tokenAccent : tokenBorder
            border.width: 1

            TextInput {
                id: folderSearch
                objectName: "contextSidebarSearch"
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: clearSearch.visible ? 26 : 8
                verticalAlignment: Text.AlignVCenter
                color: tokenText
                font.family: "Segoe UI"
                font.pixelSize: 12
                clip: true
                selectByMouse: true
                text: root.searchQuery
                onTextChanged: root.searchQuery = text
                Accessible.name: "Filter folders and categories"
            }

            Text {
                anchors.fill: parent
                anchors.leftMargin: 8
                verticalAlignment: Text.AlignVCenter
                visible: folderSearch.text === "" && !folderSearch.activeFocus
                text: "Filter folders…"
                color: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 12
            }

            Text {
                id: clearSearch
                objectName: "contextSidebarSearchClear"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 8
                visible: folderSearch.text !== ""
                text: "✕"
                color: tokenMuted
                font.pixelSize: 11
                Accessible.name: "Clear folder filter"
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -4
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.searchQuery = ""
                        folderSearch.text = ""
                    }
                }
            }
        }

        Text {
            objectName: "sidebarAll"
            width: parent.width
            text: shellReady && (shellApi.scopeLabel !== "" || shellApi.facet !== "memory")
                  ? "Show everything"
                  : "Everything"
            color: shellReady && shellApi.scopeLabel === "" && shellApi.facet === "memory"
                   ? tokenText : tokenAccent
            font.family: "Segoe UI"
            font.pixelSize: 13
            Accessible.name: text
            MouseArea {
                anchors.fill: parent
                anchors.margins: -3
                cursorShape: Qt.PointingHandCursor
                onClicked: if (shellReady) shellApi.clearScope()
            }
        }

        Column {
            width: parent.width
            spacing: 4
            Text {
                objectName: "sidebarSectionMedia"
                text: (root.mediaOpen ? "▾  " : "▸  ") + "Media"
                color: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.letterSpacing: 0.4
                Accessible.name: "Media, " + (root.mediaOpen ? "expanded" : "collapsed")
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.toggleSection("media")
                }
            }
            Flow {
                width: parent.width
                spacing: 6
                visible: root.mediaOpen
                Repeater {
                    model: [
                        {"key": "all", "label": "All"},
                        {"key": "photo", "label": "Photos"},
                        {"key": "video", "label": "Videos"}
                    ]
                    delegate: Rectangle {
                        property bool active: shellReady && shellApi.mediaKind === modelData.key
                        Component.onCompleted: objectName = "sidebarKind_" + modelData.key
                        width: kindLabel.implicitWidth + 14
                        height: 24
                        radius: 6
                        color: active ? tokenAccentDim : (kindArea.containsMouse ? tokenBg3 : "transparent")
                        border.color: active ? tokenAccent : tokenBorder
                        border.width: 1
                        Text {
                            id: kindLabel
                            anchors.centerIn: parent
                            text: modelData.label
                            color: active ? tokenText : tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                        }
                        Accessible.name: modelData.label + (active ? ", selected" : "")
                        MouseArea {
                            id: kindArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.setMediaKind(modelData.key)
                        }
                    }
                }
            }
            Text {
                objectName: "mediaKinds"
                visible: root.mediaOpen && shellReady
                width: parent.width
                wrapMode: Text.WordWrap
                text: shellApi.photoCount + " photos · " + shellApi.videoCount + " videos"
                color: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
            }
        }

        Column {
            width: parent.width
            spacing: 4
            Text {
                objectName: "sidebarSectionFolders"
                text: (root.foldersOpen ? "▾  " : "▸  ") + "Folders"
                color: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.letterSpacing: 0.4
                Accessible.name: "Folders, " + (root.foldersOpen ? "expanded" : "collapsed")
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.toggleSection("folders")
                }
            }
            Column {
                width: parent.width
                visible: root.foldersOpen
                spacing: 1
                Repeater {
                    model: root.filteredFolders()
                    delegate: Item {
                        width: parent.width
                        height: 26
                        property bool active: shellReady && shellApi.scopeKind === "folder" && shellApi.scopeLabel === modelData.label
                        Component.onCompleted: objectName = "sidebarFolder_" + modelData.label

                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: active ? tokenAccentDim : (folderArea.containsMouse ? tokenBg3 : "transparent")
                        }
                        Text {
                            anchors.left: parent.left
                            anchors.right: countBadge.left
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 6
                            text: modelData.displayName || modelData.label
                            color: active ? tokenAccent : tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            Accessible.name: modelData.accessibleName || text
                        }
                        Text {
                            id: countBadge
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.countLabel !== undefined ? String(modelData.countLabel) : String(modelData.count)
                            color: tokenFaint
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                        }
                        ToolTip.visible: folderArea.containsMouse
                        ToolTip.delay: 450
                        ToolTip.text: (modelData.displayName || modelData.label) + " — "
                                      + (modelData.exactCount !== undefined ? modelData.exactCount : modelData.count)
                                      + " photos"
                        MouseArea {
                            id: folderArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.selectFolder(modelData.label)
                        }
                    }
                }
                Text {
                    visible: root.filteredFolders().length === 0
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: root.searchNorm !== "" ? "No folders match." : "No folders indexed yet."
                    color: tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                }
            }
        }

        Column {
            width: parent.width
            spacing: 4
            Text {
                objectName: "sidebarMoments"
                text: (root.momentsOpen ? "▾  " : "▸  ") + "Moments"
                color: shellReady && shellApi.facet === "moments" ? tokenAccent : tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.letterSpacing: 0.4
                Accessible.name: "Moments, " + (root.momentsOpen ? "expanded" : "collapsed")
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root.toggleSection("moments")
                        if (shellReady && shellApi.facet !== "moments")
                            shellApi.setFacet("moments")
                    }
                }
            }
            Column {
                width: parent.width
                visible: root.momentsOpen
                spacing: 1
                Repeater {
                    model: root.filteredMoments()
                    delegate: Item {
                        width: parent.width
                        height: 26
                        Component.onCompleted: objectName = "sidebarBucket_" + modelData.key
                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: bucketArea.containsMouse ? tokenBg3 : "transparent"
                        }
                        Text {
                            anchors.left: parent.left
                            anchors.right: mCount.left
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.leftMargin: 6
                            text: modelData.label
                            color: tokenMuted
                            font.family: "Segoe UI"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            Accessible.name: modelData.label + ", " + modelData.count + " photos"
                        }
                        Text {
                            id: mCount
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: shellReady ? shellApi.formatCount(Number(modelData.count || 0)) : String(modelData.count || 0)
                            color: tokenFaint
                            font.family: "Segoe UI"
                            font.pixelSize: 11
                        }
                        MouseArea {
                            id: bucketArea
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: if (shellReady) shellApi.selectBucket(modelData.key)
                        }
                    }
                }
                Text {
                    visible: shellReady && shellApi.facet === "moments" && root.filteredMoments().length === 0
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: root.searchNorm !== ""
                          ? "No moments match."
                          : "No named Moments yet."
                    color: tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                }
            }
        }

        Column {
            width: parent.width
            spacing: 4
            Text {
                text: (root.similarOpen ? "▾  " : "▸  ") + "Similar"
                color: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.letterSpacing: 0.4
                Accessible.name: "Similar memories, " + (root.similarOpen ? "expanded" : "collapsed")
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.toggleSection("similar")
                }
            }
            Column {
                visible: root.similarOpen
                width: parent.width
                spacing: 4
                Text {
                    objectName: "sidebarSimilar"
                    width: parent.width
                    text: "Find similar"
                    color: shellReady && shellApi.similarActionReady
                           ? (similarNavArea.containsMouse ? tokenText : tokenAccent)
                           : tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    Accessible.name: shellReady ? shellApi.similarActionHint : "Find similar"
                    MouseArea {
                        id: similarNavArea
                        anchors.fill: parent
                        anchors.margins: -3
                        hoverEnabled: true
                        cursorShape: shellReady && shellApi.similarActionReady
                                     ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: if (shellReady) shellApi.findSimilarWhole()
                    }
                }
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: shellReady ? shellApi.similarActionHint : ""
                    color: tokenFaint
                    font.family: "Segoe UI"
                    font.pixelSize: 11
                }
            }
        }
    }
}
