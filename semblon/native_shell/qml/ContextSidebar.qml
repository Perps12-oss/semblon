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
    property color tokenBg0: "#0d0e12"
    property color tokenBg1: "#1c1d21"
    property color tokenBg2: "#25262c"
    property color tokenBg3: "#2e3036"
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

    component SectionHeader: Item {
        id: hdr
        property string sectionKey: ""
        property string title: ""
        property string iconName: "folder"
        property bool open: true
        property bool accented: false
        property string objectNameValue: ""
        signal activated()
        width: parent.width
        height: 28
        Component.onCompleted: if (objectNameValue !== "") objectName = objectNameValue

        Row {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            Text {
                text: hdr.open ? "▾" : "▸"
                color: tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
                anchors.verticalCenter: parent.verticalCenter
            }
            DuotoneIcon {
                width: 14
                height: 14
                icon: hdr.iconName
                fillColor: hdr.accented ? tokenAccent : "#8A8D93"
                cutoutColor: tokenBg1
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: hdr.title
                color: hdr.accented ? tokenAccent : tokenFaint
                font.family: "Segoe UI"
                font.pixelSize: 11
                font.letterSpacing: 1.0
                font.weight: Font.DemiBold
                font.capitalization: Font.AllUppercase
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                root.toggleSection(hdr.sectionKey)
                hdr.activated()
            }
        }
    }

    component CountPill: Rectangle {
        property string label: ""
        width: Math.max(28, pillText.implicitWidth + 12)
        height: 18
        radius: 9
        color: tokenBg3
        Text {
            id: pillText
            anchors.centerIn: parent
            text: label
            color: "#B0B3B8"
            font.family: "Segoe UI"
            font.pixelSize: 11
            font.weight: Font.Medium
        }
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
            font.letterSpacing: 1.0
            font.weight: Font.DemiBold
            font.capitalization: Font.AllUppercase
        }

        Rectangle {
            width: parent.width
            height: 32
            radius: 6
            color: tokenBg0
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

        Item {
            objectName: "sidebarAll"
            width: parent.width
            height: 36
            readonly property bool everythingActive: shellReady
                && shellApi.scopeLabel === "" && shellApi.facet === "memory"

            Rectangle {
                anchors.fill: parent
                radius: 6
                color: parent.everythingActive
                       ? Qt.rgba(1, 1, 1, 0.08)
                       : (allArea.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent")
            }
            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.topMargin: 8
                anchors.bottomMargin: 8
                width: 3
                radius: 1.5
                color: tokenAccent
                visible: parent.everythingActive
            }
            Row {
                anchors.left: parent.left
                anchors.leftMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                DuotoneIcon {
                    width: 16
                    height: 16
                    icon: "library"
                    fillColor: (parent.parent.everythingActive || allArea.containsMouse) ? tokenAccent : "#8A8D93"
                    cutoutColor: tokenBg1
                }
                Text {
                    text: shellReady && (shellApi.scopeLabel !== "" || shellApi.facet !== "memory")
                          ? "Show everything"
                          : "Everything"
                    color: (parent.parent.everythingActive || allArea.containsMouse) ? tokenText : tokenMuted
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    anchors.verticalCenter: parent.verticalCenter
                    Accessible.name: text
                }
            }
            MouseArea {
                id: allArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (shellReady) shellApi.showEverything()
            }
        }

        Column {
            width: parent.width
            spacing: 4
            SectionHeader {
                sectionKey: "media"
                title: "Media"
                iconName: "media"
                open: root.mediaOpen
                objectNameValue: "sidebarSectionMedia"
                Accessible.name: "Media, " + (root.mediaOpen ? "expanded" : "collapsed")
            }
            Rectangle {
                objectName: "mediaKindSegment"
                width: parent.width
                height: 32
                radius: 8
                color: tokenBg0
                border.color: tokenBorder
                border.width: 1
                visible: root.mediaOpen

                Row {
                    anchors.fill: parent
                    anchors.margins: 3
                    spacing: 2

                    Repeater {
                        model: [
                            {"key": "all", "label": "All"},
                            {"key": "photo", "label": "Photos"},
                            {"key": "video", "label": "Videos"}
                        ]
                        delegate: Rectangle {
                            property bool active: shellReady && shellApi.mediaKind === modelData.key
                            Component.onCompleted: objectName = "sidebarKind_" + modelData.key
                            width: (parent.width - 4) / 3
                            height: parent.height
                            radius: 6
                            color: active
                                   ? tokenBg3
                                   : (kindArea.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent")
                            border.color: active ? Qt.rgba(tokenAccent.r, tokenAccent.g, tokenAccent.b, 0.45) : "transparent"
                            border.width: active ? 1 : 0
                            Text {
                                anchors.centerIn: parent
                                text: modelData.label
                                color: active ? tokenText : tokenMuted
                                font.family: "Segoe UI"
                                font.pixelSize: 11
                                font.weight: active ? Font.DemiBold : Font.Normal
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
            SectionHeader {
                sectionKey: "folders"
                title: "Folders"
                iconName: "folder"
                open: root.foldersOpen
                objectNameValue: "sidebarSectionFolders"
                Accessible.name: "Folders, " + (root.foldersOpen ? "expanded" : "collapsed")
            }
            Column {
                width: parent.width
                visible: root.foldersOpen
                spacing: 2
                Repeater {
                    model: root.filteredFolders()
                    delegate: Item {
                        width: parent.width
                        height: 36
                        property bool active: shellReady && shellApi.scopeKind === "folder" && shellApi.scopeLabel === modelData.label
                        Component.onCompleted: objectName = "sidebarFolder_" + modelData.label

                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: active
                                   ? Qt.rgba(1, 1, 1, 0.08)
                                   : (folderArea.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent")
                        }
                        Rectangle {
                            anchors.left: parent.left
                            anchors.top: parent.top
                            anchors.bottom: parent.bottom
                            anchors.topMargin: 8
                            anchors.bottomMargin: 8
                            width: 3
                            radius: 1.5
                            color: tokenAccent
                            visible: active
                        }
                        DuotoneIcon {
                            id: folderIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            width: 16
                            height: 16
                            icon: "folder"
                            fillColor: (active || folderArea.containsMouse) ? tokenAccent : "#8A8D93"
                            cutoutColor: tokenBg1
                        }
                        Text {
                            anchors.left: folderIcon.right
                            anchors.leftMargin: 10
                            anchors.right: folderPill.left
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.displayName || modelData.label
                            color: (active || folderArea.containsMouse) ? tokenText : "#E1E3E6"
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            Accessible.name: modelData.accessibleName || text
                        }
                        CountPill {
                            id: folderPill
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            label: modelData.countLabel !== undefined ? String(modelData.countLabel) : String(modelData.count)
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
            SectionHeader {
                objectName: "sidebarMoments"
                sectionKey: "moments"
                title: "Moments"
                iconName: "moments"
                open: root.momentsOpen
                accented: shellReady && shellApi.facet === "moments"
                Accessible.name: "Moments, " + (root.momentsOpen ? "expanded" : "collapsed")
                onActivated: {
                    if (shellReady && shellApi.facet !== "moments")
                        shellApi.setFacet("moments")
                }
            }
            Column {
                width: parent.width
                visible: root.momentsOpen
                spacing: 2
                Repeater {
                    model: root.filteredMoments()
                    delegate: Item {
                        width: parent.width
                        height: 36
                        Component.onCompleted: objectName = "sidebarBucket_" + modelData.key
                        Rectangle {
                            anchors.fill: parent
                            radius: 6
                            color: bucketArea.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent"
                        }
                        DuotoneIcon {
                            id: momentIcon
                            anchors.left: parent.left
                            anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            width: 16
                            height: 16
                            icon: "tag"
                            fillColor: bucketArea.containsMouse ? tokenAccent : "#8A8D93"
                            cutoutColor: tokenBg1
                        }
                        Text {
                            anchors.left: momentIcon.right
                            anchors.leftMargin: 10
                            anchors.right: mPill.left
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            color: bucketArea.containsMouse ? tokenText : "#E1E3E6"
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            elide: Text.ElideRight
                            Accessible.name: modelData.label + ", " + modelData.count + " photos"
                        }
                        CountPill {
                            id: mPill
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            label: shellReady ? shellApi.formatCount(Number(modelData.count || 0)) : String(modelData.count || 0)
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
            SectionHeader {
                sectionKey: "similar"
                title: "Similar"
                iconName: "similar"
                open: root.similarOpen
                objectNameValue: "sidebarSectionSimilar"
                Accessible.name: "Similar memories, " + (root.similarOpen ? "expanded" : "collapsed")
            }
            Column {
                visible: root.similarOpen
                width: parent.width
                spacing: 4
                Item {
                    width: parent.width
                    height: 36
                    Rectangle {
                        anchors.fill: parent
                        radius: 6
                        color: similarNavArea.containsMouse ? Qt.rgba(1, 1, 1, 0.04) : "transparent"
                    }
                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10
                        DuotoneIcon {
                            width: 16
                            height: 16
                            icon: "similar"
                            fillColor: shellReady && shellApi.similarActionReady
                                       ? (similarNavArea.containsMouse ? tokenAccent : tokenAccent)
                                       : "#8A8D93"
                            cutoutColor: tokenBg1
                            opacity: shellReady && shellApi.similarActionReady ? 1 : 0.55
                        }
                        Text {
                            objectName: "sidebarSimilar"
                            text: "Find similar"
                            color: shellReady && shellApi.similarActionReady
                                   ? (similarNavArea.containsMouse ? tokenText : tokenAccent)
                                   : tokenFaint
                            font.family: "Segoe UI"
                            font.pixelSize: 13
                            anchors.verticalCenter: parent.verticalCenter
                            Accessible.name: shellReady ? shellApi.similarActionHint : "Find similar"
                        }
                    }
                    MouseArea {
                        id: similarNavArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: shellReady && shellApi.similarActionReady
                                     ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: if (shellReady) shellApi.findSimilar()
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
