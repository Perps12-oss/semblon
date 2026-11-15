import QtQuick

// Contextual Lens & Synthesis pane. Owns the 4-tile strip, reasoning log, and
// composer with a live crop thumbnail. Only visible while Focus has a sticky
// selection or an active similar search — not a second top-level chrome.
Item {
    id: drawer
    objectName: "synthesisDrawer"
    property bool open: false
    property real cropX: 0
    property real cropY: 0
    property real cropW: 0
    property real cropH: 0
    property string focusId: ""
    signal closeRequested()
    signal askSubmitted(string prompt)
    signal hitOpened(string mediaId)

    visible: width > 2
    clip: true

    Rectangle {
        anchors.fill: parent
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
    }

    Column {
        id: body
        anchors.fill: parent
        anchors.margins: Theme.pad
        spacing: Theme.gap

        Row {
            width: parent.width
            spacing: Theme.gap
            Text {
                text: "Lens"
                font.family: Theme.display
                font.pixelSize: Theme.lead
                color: Theme.text
                anchors.verticalCenter: parent.verticalCenter
            }
            Item { width: parent.width - closeBtn.width - 80; height: 1 }
            Tool {
                id: closeBtn
                objectName: "closeSynthesisDrawer"
                label: "Close"
                onActivated: drawer.closeRequested()
            }
        }

        // Reasoning accordion (collapsible) — real notes from the search / name path.
        Item {
            id: accordion
            objectName: "reasoningAccordion"
            width: parent.width
            height: expanded ? accordionCol.height + 8 : headRow.height
            property bool expanded: true
            clip: true
            Behavior on height { NumberAnimation { duration: Theme.fast; easing.type: Theme.easing } }

            Rectangle {
                anchors.fill: parent
                color: Theme.raised
                border.width: 1
                border.color: Theme.line
                radius: Theme.radius
            }
            Column {
                id: accordionCol
                width: parent.width
                padding: Theme.gap
                spacing: 4
                Row {
                    id: headRow
                    width: parent.width - Theme.gap * 2
                    spacing: Theme.gap
                    Text {
                        text: accordion.expanded ? "▾ Reasoning" : "▸ Reasoning"
                        font.family: Theme.ui
                        font.pixelSize: Theme.small
                        color: Theme.muted
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: accordion.expanded = !accordion.expanded
                        }
                    }
                }
                Text {
                    objectName: "drawerSelectionNote"
                    width: parent.width - Theme.gap * 2
                    visible: accordion.expanded && shell.selectionNote !== ""
                    text: "[region] " + shell.selectionNote
                    wrapMode: Text.WordWrap
                    font.family: Theme.ui
                    font.pixelSize: Theme.tiny
                    color: Theme.faint
                }
                Text {
                    objectName: "drawerSimilarNote"
                    width: parent.width - Theme.gap * 2
                    visible: accordion.expanded && shell.similarNote !== ""
                    text: "[search] " + shell.similarNote
                    wrapMode: Text.WordWrap
                    font.family: Theme.ui
                    font.pixelSize: Theme.tiny
                    color: Theme.faint
                }
                Text {
                    objectName: "drawerNameNote"
                    width: parent.width - Theme.gap * 2
                    visible: accordion.expanded && shell.nameNote !== ""
                    text: "[describe] " + shell.nameNote
                    wrapMode: Text.WordWrap
                    font.family: Theme.ui
                    font.pixelSize: Theme.tiny
                    color: Theme.text
                }
            }
        }

        Text {
            text: shell.searchBusy ? "Looking…"
                : shell.similarState === "ready" ? (shell.similarCount + " matches")
                : "Matches appear after you settle the crop."
            font.family: Theme.ui
            font.pixelSize: Theme.small
            color: Theme.muted
        }

        // Yandex-style 4-tile strip with score / dims / source badges.
        Row {
            id: tileRow
            objectName: "drawerMatchStrip"
            width: parent.width
            spacing: 6
            Repeater {
                model: similarModel
                delegate: Item {
                    visible: index < 4
                    width: visible ? Math.floor((tileRow.width - 18) / 4) : 0
                    height: visible ? Math.floor(width * 0.75) : 0
                    activeFocusOnTab: visible
                    Accessible.role: Accessible.Button
                    Accessible.name: "Open match " + (index + 1)
                    Accessible.onPressAction: drawer.hitOpened(mediaId)
                    Keys.onReturnPressed: drawer.hitOpened(mediaId)
                    Keys.onEnterPressed: drawer.hitOpened(mediaId)
                    Image {
                        id: hitThumb
                        anchors.fill: parent
                        // Fit (not crop) so the normalized match box stays on the pictured region.
                        source: "image://archive/t/" + mediaId
                        fillMode: Image.PreserveAspectFit
                        asynchronous: true
                    }
                    Item {
                        anchors.centerIn: hitThumb
                        width: hitThumb.paintedWidth
                        height: hitThumb.paintedHeight
                        visible: matchW > 0 && matchH > 0
                        Rectangle {
                            objectName: "drawerStripMatchBox"
                            x: matchX * parent.width
                            y: matchY * parent.height
                            width: Math.max(2, matchW * parent.width)
                            height: Math.max(2, matchH * parent.height)
                            color: "transparent"
                            border.width: 2
                            border.color: Theme.amber
                        }
                    }
                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: badge.implicitHeight + 6
                        color: Theme.scrim
                        Text {
                            id: badge
                            objectName: "matchBadge"
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.margins: 4
                            text: Math.round((score || 0) * 100) + "% · " + (shell ? shell.mediaBadgeFor(mediaId) : "")
                            elide: Text.ElideRight
                            font.family: Theme.ui
                            font.pixelSize: Theme.tiny
                            color: Theme.text
                        }
                    }
                    Rectangle {
                        anchors.fill: parent
                        color: "transparent"
                        border.width: parent.activeFocus ? 2 : 1
                        border.color: parent.activeFocus ? Theme.amber : Theme.line
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            drawer.hitOpened(mediaId)
                            parent.forceActiveFocus()
                        }
                    }
                }
            }
        }

        // Stream / synthesis body — turn-bound history with frozen crops.
        Flickable {
            id: stream
            width: parent.width
            height: Math.max(80, drawer.height - y - chipsRow.height - composer.height - Theme.pad * 4)
            contentHeight: streamCol.height
            clip: true
            Column {
                id: streamCol
                objectName: "synthesisTurnList"
                width: stream.width
                spacing: Theme.gap
                Text {
                    width: parent.width
                    visible: shell.synthesisTurns.length === 0 && shell.similarState === "ready"
                    text: "Ask about the selected region, or open a match on the left."
                    wrapMode: Text.WordWrap
                    font.family: Theme.ui
                    font.pixelSize: Theme.small
                    color: Theme.faint
                }
                Repeater {
                    model: shell.synthesisTurns
                    delegate: Rectangle {
                        required property var modelData
                        required property int index
                        width: streamCol.width
                        height: turnCol.height + Theme.gap
                        radius: Theme.radius
                        color: Theme.raised
                        border.width: 1
                        border.color: Theme.line
                        Column {
                            id: turnCol
                            width: parent.width - Theme.gap * 2
                            x: Theme.gap
                            y: Theme.gap / 2
                            spacing: 4
                            Row {
                                spacing: 6
                                // Frozen 40×40 crop from this turn.
                                Item {
                                    width: 36; height: 36; clip: true
                                    Rectangle { anchors.fill: parent; radius: 6; color: Theme.bg }
                                    Image {
                                        visible: modelData.media_id && modelData.region
                                        source: modelData.media_id ? "image://archive/f/" + modelData.media_id : ""
                                        asynchronous: true
                                        width: modelData.region[2] > 0 ? parent.width / modelData.region[2] : parent.width
                                        height: modelData.region[3] > 0 ? parent.height / modelData.region[3] : parent.height
                                        x: modelData.region ? -modelData.region[0] * width : 0
                                        y: modelData.region ? -modelData.region[1] * height : 0
                                        fillMode: Image.Stretch
                                    }
                                }
                                Text {
                                    width: turnCol.width - 48
                                    text: modelData.prompt || "Describe this area"
                                    wrapMode: Text.WordWrap
                                    font.family: Theme.ui
                                    font.pixelSize: Theme.small
                                    color: Theme.muted
                                }
                            }
                            Text {
                                width: parent.width
                                text: modelData.reply || ""
                                wrapMode: Text.WordWrap
                                font.family: Theme.display
                                font.pixelSize: Theme.body
                                color: Theme.text
                            }
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: shell.restoreSynthesisTurn(index)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: "Restore crop from turn " + (index + 1)
                    }
                }
            }
        }

        // Zero-prompt starter chips — fire archive / describe actions without typing.
        Flow {
            id: chipsRow
            objectName: "starterChips"
            width: parent.width
            spacing: 6
            visible: shell.selectionOnFocus && !shell.searchBusy
            Tool {
                objectName: "chipDescribe"
                label: "Describe this area"
                onActivated: shell.askAboutSelection("")
            }
            Tool {
                objectName: "chipAskText"
                label: "Ask about selected text"
                visible: shell.selectedText !== ""
                onActivated: shell.askAboutSelection("About this text: " + shell.selectedText)
            }
            Tool {
                objectName: "chipTopMatch"
                label: "Open top match"
                visible: shell.similarCount > 0
                onActivated: drawer.hitOpened(shell.similarId(0))
            }
            Tool {
                objectName: "chipKeep"
                label: "Keep this find"
                visible: shell.similarState === "ready" && shell.similarCount > 0
                onActivated: shell.keepDiscovery()
            }
        }

        // Composer pill with live crop thumbnail.
        Rectangle {
            id: composer
            objectName: "synthesisComposer"
            width: parent.width
            height: 52
            radius: height / 2
            color: Theme.raised
            border.width: 1
            border.color: Theme.line

            // Live crop thumb bound to sticky user_box norms on the focus photo.
            Item {
                id: cropThumb
                objectName: "liveCropThumb"
                anchors.left: parent.left
                anchors.leftMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 40
                height: 40
                clip: true
                Rectangle {
                    anchors.fill: parent
                    radius: 8
                    color: Theme.bg
                    border.width: 1
                    border.color: Theme.line
                }
                Image {
                    id: cropSrc
                    visible: drawer.focusId !== "" && drawer.cropW > 0 && drawer.cropH > 0
                    source: drawer.focusId !== "" ? "image://archive/f/" + drawer.focusId : ""
                    asynchronous: true
                    // Scale so the crop fills the 40×40 thumb.
                    width: drawer.cropW > 0 ? parent.width / drawer.cropW : parent.width
                    height: drawer.cropH > 0 ? parent.height / drawer.cropH : parent.height
                    x: -drawer.cropX * width
                    y: -drawer.cropY * height
                    fillMode: Image.Stretch
                }
            }

            TextInput {
                id: prompt
                objectName: "composerInput"
                anchors.left: cropThumb.right
                anchors.right: sendBtn.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                height: 28
                color: Theme.text
                font.family: Theme.ui
                font.pixelSize: Theme.body
                clip: true
                selectByMouse: true
                Accessible.name: "Ask about this region"
                Keys.onReturnPressed: drawer.submit()
                Keys.onEnterPressed: drawer.submit()
            }
            Text {
                anchors.fill: prompt
                text: "Ask about this region…"
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.faint
                visible: prompt.text.length === 0 && !prompt.activeFocus
            }
            Tool {
                id: sendBtn
                objectName: "composerSend"
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                label: "↑"
                primary: true
                onActivated: drawer.submit()
            }
        }
    }

    function submit() {
        var text = prompt.text.trim()
        drawer.askSubmitted(text)
        prompt.text = ""
    }
}
