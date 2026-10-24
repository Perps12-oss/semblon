import QtQuick

// People: loose prints lie on the table. Name one to make a person. Drag a print onto a person to say "same".
// A group of faces is not a person until you give it a name. "Not sure" is always fine.
Item {
    id: table
    objectName: "peopleDesk"
    property bool active: shell.peopleOpen
    signal closed()
    visible: opacity > 0.01
    opacity: active ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    focus: active
    Keys.onEscapePressed: { shell.closePeople(); table.closed() }
    Accessible.role: Accessible.Pane
    Accessible.name: "People"

    Rectangle { anchors.fill: parent; color: Theme.bg }
    Grain { anchors.fill: parent }

    Text {
        id: head
        x: Theme.pad * 1.5; y: Theme.pad
        text: "People"
        font.family: Theme.display
        font.pixelSize: Theme.hero * 0.8
        font.weight: Font.Light
        color: Theme.text
    }
    Text {
        x: Theme.pad * 1.5
        anchors.top: head.bottom
        width: parent.width / 2
        wrapMode: Text.WordWrap
        text: shell.peopleEmpty
              ? "No faces to look at yet. Add a folder and faces will appear here."
              : "These are faces that look alike. Pick one, then give it a name, or leave it as unknown."
        font.family: Theme.ui
        font.pixelSize: Theme.body
        color: Theme.muted
    }
    Tool {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.pad
        label: "Back to photos"
        onActivated: { shell.closePeople(); table.closed() }
    }

    GridView {
        id: prints
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: 130
        anchors.leftMargin: Theme.pad
        width: parent.width * 0.52
        cellWidth: 150
        cellHeight: 176
        clip: true
        model: peopleModel
        activeFocusOnTab: true
        keyNavigationEnabled: true
        objectName: "printGrid"
        // Keyboard twin of the drags: Enter picks, S marks as the same as the first named target, X sends it away.
        Keys.onPressed: function (e) {
            if (prints.currentIndex < 0 && prints.count > 0) prints.currentIndex = 0
            var it = prints.currentItem
            if (!it) return
            if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter) { shell.selectGroup(it.subj); e.accepted = true }
            else if (e.key === Qt.Key_X) { shell.selectGroup(it.subj); shell.decide("ignore", it.subj, ""); e.accepted = true }
            else if (e.key === Qt.Key_S) {
                shell.selectGroup(it.subj)
                var c = shell.mergeCandidates
                if (c.length > 0) shell.decide("merge", it.subj, c[0].subject)
                e.accepted = true
            }
        }
        Accessible.role: Accessible.List
        Accessible.name: "Groups of faces. Enter picks one. S marks it the same as the next group. X sends it away."
        delegate: Item {
            id: plate
            width: prints.cellWidth
            height: prints.cellHeight
            readonly property bool chosen: shell.selectedSubject === subject
            readonly property string subj: subject
            objectName: "print"
            Accessible.role: Accessible.Button
            Accessible.name: (named ? title : "Unnamed group") + ", " + faceCount + (faceCount === 1 ? " photo" : " photos")

            Rectangle {
                id: card
                width: 130; height: 160
                x: 8; y: 8
                color: Theme.paper
                rotation: ((index * 37) % 7) - 3
                border.width: plate.chosen || print.GridView.isCurrentItem && prints.activeFocus ? 3 : 0
                border.color: Theme.amber
                Drag.active: drag.active
                Drag.keys: ["print"]
                Drag.hotSpot.x: width / 2
                Drag.hotSpot.y: height / 2
                Drag.source: plate
                states: State { when: drag.active; PropertyChanges { target: card; z: 50; scale: 1.06 } }
                Image {
                    x: 8; y: 8; width: 114; height: 114
                    source: faceId ? "image://face/" + faceId : "image://archive/t/" + mediaId
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                }
                Text {
                    x: 8; y: 126; width: 114
                    text: named ? title : "Unnamed"
                    elide: Text.ElideRight
                    font.family: Theme.display
                    font.pixelSize: Theme.body
                    font.weight: named ? Font.DemiBold : Font.Normal
                    color: Theme.paperInk
                }
                Text {
                    x: 8; y: 144; width: 114
                    text: faceCount + (faceCount === 1 ? " photo" : " photos")
                    font.family: Theme.ui
                    font.pixelSize: Theme.tiny
                    color: Theme.paperMuted
                }
                DragHandler {
                    id: drag
                    onActiveChanged: if (!active) {
                        var t = card.Drag.target
                        if (t && t.subjectId !== undefined && t.subjectId !== subject)
                            shell.decide("merge", subject, t.subjectId)
                        card.x = 8; card.y = 8
                    }
                }
                TapHandler { onTapped: { prints.currentIndex = index; shell.selectGroup(subject) } }
            }
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
            DropArea {
                anchors.fill: parent
                keys: ["print"]
                property string subjectId: subject
                Rectangle { anchors.fill: parent; color: Theme.amber; opacity: parent.containsDrag ? 0.25 : 0 }
            }
        }
    }

    // The right-hand side: the chosen group, big, with the plain choices.
    Item {
        id: detail
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.topMargin: 130
        anchors.rightMargin: Theme.pad * 1.5
        width: parent.width * 0.42
        visible: shell.selectedSubject !== ""

        Text {
            id: who
            text: shell.selectedTitle
            font.family: Theme.display
            font.pixelSize: Theme.title
            color: Theme.text
            width: parent.width
            elide: Text.ElideRight
        }
        Text {
            id: sub
            anchors.top: who.bottom
            text: shell.selectedCount + (shell.selectedCount === 1 ? " photo" : " photos")
                  + (shell.selectedPersonId === "" ? ". Not named yet, so Semblon is treating this as a group, not a person." : "")
            font.family: Theme.ui
            font.pixelSize: Theme.small
            color: Theme.muted
            width: parent.width
            wrapMode: Text.WordWrap
        }
        Flow {
            id: faces
            objectName: "splitFaceGrid"
            anchors.top: sub.bottom
            anchors.topMargin: Theme.pad
            width: parent.width
            spacing: 6
            Repeater {
                model: shell.selectedMembers.slice(0, 18)
                Item {
                    id: faceCell
                    width: 64; height: 64
                    property bool picked: { shell.splitSelectionCount; return shell.isSplitFaceSelected(modelData.face_id) }
                    activeFocusOnTab: true
                    Accessible.role: Accessible.CheckBox
                    Accessible.name: "Face " + (index + 1) + (picked ? ", picked to split out" : "")
                    Keys.onSpacePressed: shell.toggleSplitFace(modelData.face_id)
                    Image {
                        anchors.fill: parent
                        source: "image://face/" + modelData.face_id
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                    }
                    Rectangle { anchors.fill: parent; color: "transparent"; border.width: faceCell.picked || faceCell.activeFocus ? 3 : 0; border.color: Theme.amber }
                    TapHandler { onTapped: shell.toggleSplitFace(modelData.face_id) }
                }
            }
        }
        Rectangle {
            id: nameBox
            anchors.top: faces.bottom
            anchors.topMargin: Theme.pad
            width: parent.width
            height: 44
            radius: Theme.radius
            color: Theme.surface
            border.width: nameInput.activeFocus ? 2 : 1
            border.color: nameInput.activeFocus ? Theme.amber : Theme.line
            visible: shell.canNameSelected
            TextInput {
                id: nameInput
                anchors.fill: parent
                anchors.margins: 12
                verticalAlignment: TextInput.AlignVCenter
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.text
                selectByMouse: true
                clip: true
                Accessible.name: "Type a name for this person"
                onAccepted: nameGo.activated()
                Text {
                    visible: nameInput.text === ""
                    text: "Type a name, such as Grandma"
                    font: nameInput.font
                    color: Theme.faint
                }
            }
        }
        Flow {
            anchors.top: nameBox.visible ? nameBox.bottom : faces.bottom
            anchors.topMargin: Theme.pad
            width: parent.width
            spacing: Theme.gap
            Tool {
                id: nameGo
                label: "Name this person"
                primary: true
                visible: shell.canNameSelected
                enabled: nameInput.text.trim() !== ""
                onActivated: { shell.decide("name", shell.selectedSubject, nameInput.text.trim()); nameInput.text = "" }
            }
            Tool {
                label: "Split picked faces out"
                hint: "Tap faces above, then split them into their own group"
                visible: shell.canSplitSelected
                onActivated: shell.splitSelectedFaces()
            }
            Tool {
                label: "See the photos"
                onActivated: shell.openEvidence(shell.evidenceId)
            }
            Tool {
                label: "Not sure yet"
                hint: "Leave this group unknown. That is always fine."
                onActivated: { shell.selectGroup(""); }
            }
            Tool {
                label: "Not a real person"
                visible: shell.canIgnoreSelected
                onActivated: shell.decide("ignore", shell.selectedSubject, "")
            }
            Tool {
                label: "Not the same people"
                visible: shell.canRuleOutSelected
                onActivated: shell.decide("rule_out", shell.selectedSubject, "")
            }
            Tool {
                label: "See their photos by date"
                visible: shell.canBrowsePersonTime
                onActivated: { shell.browseSelectedPersonInTime(); shell.closePeople(); table.closed() }
            }
        }
        Text {
            anchors.bottom: parent.bottom
            width: parent.width
            wrapMode: Text.WordWrap
            text: shell.peopleNote
            font.family: Theme.ui
            font.pixelSize: Theme.small
            color: Theme.muted
        }
    }

    // Named people are stacks you can drop a print onto.
    Row {
        objectName: "mergeTargetFlow"
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Theme.pad
        spacing: Theme.gap
        Repeater {
            model: shell.mergeCandidates
            Rectangle {
                id: stack
                property string subjectId: modelData.subject !== undefined ? modelData.subject : ""
                objectName: "sameAsStack"
                width: 120; height: 40
                activeFocusOnTab: true
                Keys.onReturnPressed: shell.decide("merge", shell.selectedSubject, stack.subjectId)
                Keys.onSpacePressed: shell.decide("merge", shell.selectedSubject, stack.subjectId)
                Accessible.role: Accessible.Button
                Accessible.name: "Same as " + (modelData.title || "")
                radius: Theme.pill
                color: stackDrop.containsDrag ? Theme.amber : Theme.surface
                border.width: activeFocus ? 3 : 1
                border.color: activeFocus ? Theme.amber : Theme.line
                visible: subjectId !== ""
                Text {
                    anchors.centerIn: parent
                    text: "Same as " + (modelData.title || "")
                    elide: Text.ElideRight
                    width: parent.width - 16
                    horizontalAlignment: Text.AlignHCenter
                    font.family: Theme.ui
                    font.pixelSize: Theme.small
                    color: stackDrop.containsDrag ? Theme.onAmber : Theme.text
                }
                DropArea { id: stackDrop; anchors.fill: parent; keys: ["print"]; property string subjectId: stack.subjectId }
                TapHandler { onTapped: shell.decide("merge", shell.selectedSubject, stack.subjectId) }
            }
        }
    }
}
