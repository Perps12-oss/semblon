import QtQuick

// Related: one photograph, then the objects and people already linked to it.
Item {
    id: desk
    objectName: "relatedDesk"
    property bool active: shell.relatedOpen
    readonly property bool showingPhotos: shell.relatedView === "photos"
    readonly property bool wide: width >= 860
    signal closed()

    visible: opacity > 0.01
    opacity: active ? 1 : 0
    enabled: active
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    focus: active
    Keys.onEscapePressed: {
        if (desk.showingPhotos) shell.backRelated()
        else { shell.closeRelated(); desk.closed() }
    }
    Accessible.role: Accessible.Pane
    Accessible.name: "Related to this photo"

    function stateColor(state) {
        if (state === "confirmed") return Theme.ok
        if (state === "contradicted") return Theme.danger
        if (state === "not_linked") return Theme.faint
        return Theme.muted
    }

    Rectangle { anchors.fill: parent; color: Theme.bg }
    Grain { anchors.fill: parent }

    Text {
        id: head
        x: Theme.pad * 1.5
        y: Theme.pad
        text: desk.showingPhotos ? shell.relatedItemTitle : "Related"
        font.family: Theme.display
        font.pixelSize: Theme.hero * 0.62
        font.weight: Font.Light
        color: Theme.text
    }
    Text {
        id: sub
        x: Theme.pad * 1.5
        anchors.top: head.bottom
        width: Math.min(parent.width * 0.62, 640)
        wrapMode: Text.WordWrap
        text: desk.showingPhotos
              ? "Oldest first. Choose a photograph to open it."
              : (shell.relatedNote !== "" ? shell.relatedNote : shell.relatedCoverage)
        font.family: Theme.ui
        font.pixelSize: Theme.body
        color: shell.relatedNote === "Saved." ? Theme.ok : Theme.muted
    }
    Tool {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.pad
        label: desk.showingPhotos ? "Back" : "Back to photos"
        onActivated: {
            if (desk.showingPhotos) shell.backRelated()
            else { shell.closeRelated(); desk.closed() }
        }
    }

    Image {
        id: origin
        anchors.left: parent.left
        anchors.top: sub.bottom
        anchors.leftMargin: Theme.pad
        anchors.topMargin: Theme.pad
        width: desk.wide ? 300 : parent.width - Theme.pad * 2
        height: desk.wide ? parent.height - y - Theme.pad : 220
        visible: !desk.showingPhotos
        fillMode: Image.PreserveAspectFit
        asynchronous: true
        cache: true
        source: !desk.showingPhotos && shell.relatedOriginId !== ""
                ? "image://archive/f/" + shell.relatedOriginId : ""
        Rectangle {
            anchors.fill: parent
            color: Theme.surface
            visible: origin.status === Image.Error || origin.source === ""
            Text {
                anchors.centerIn: parent
                text: "Photo unavailable"
                font.family: Theme.ui
                font.pixelSize: Theme.small
                color: Theme.muted
            }
        }
    }

    Flickable {
        id: scroller
        anchors.left: desk.wide ? origin.right : parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.top: desk.wide ? sub.bottom : origin.bottom
        anchors.margins: Theme.pad
        visible: !desk.showingPhotos
        clip: true
        contentWidth: width
        contentHeight: sections.implicitHeight
        flickableDirection: Flickable.VerticalFlick
        Column {
            id: sections
            width: scroller.width
            spacing: Theme.pad * 1.4

            Text { text: "Objects"; font.family: Theme.ui; font.pixelSize: Theme.lead; color: Theme.text }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: shell.relatedObjectsNote !== ""
                text: shell.relatedObjectsNote
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.muted
            }
            Item {
                id: objectGrid
                objectName: "relatedObjectGrid"
                property int count: objectCards.count
                width: Math.max(parent.width, 228)
                implicitWidth: width
                readonly property int cols: Math.max(1, Math.floor(width / 228))
                height: count === 0 ? 0 : Math.ceil(count / cols) * 276
                implicitHeight: height
                Repeater {
                    id: objectCards
                    model: shell.relatedObjects
                    delegate: Rectangle {
                        objectName: "relatedObjectCard"
                        x: (index % objectGrid.cols) * 228
                        y: Math.floor(index / objectGrid.cols) * 276
                        width: 220
                        height: modelData.canCorrect ? 268 : 196
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.line
                        Image {
                            x: 8; y: 8
                            width: parent.width - 16
                            height: 96
                            source: modelData.thumb
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                        Column {
                            x: 10
                            y: 112
                            width: parent.width - 20
                            spacing: 4
                            Text {
                                width: parent.width
                                text: modelData.title
                                elide: Text.ElideRight
                                font.family: Theme.ui
                                font.pixelSize: Theme.body
                                color: Theme.text
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: modelData.stateLabel
                                font.family: Theme.ui
                                font.pixelSize: Theme.small
                                color: desk.stateColor(modelData.state)
                            }
                            Text {
                                width: parent.width
                                text: modelData.countLabel
                                font.family: Theme.ui
                                font.pixelSize: Theme.small
                                color: Theme.muted
                            }
                        }
                        Tool {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.leftMargin: 8
                            anchors.bottomMargin: modelData.canCorrect ? 44 : 8
                            label: "Photographs"
                            pixel: Theme.tiny
                            onActivated: shell.openRelatedItem(modelData.key)
                        }
                        Row {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            anchors.margins: 8
                            spacing: 4
                            visible: modelData.canCorrect
                            Tool {
                                label: "Same object"
                                pixel: Theme.tiny
                                primary: true
                                onActivated: shell.confirmSameObject(modelData.key)
                            }
                            Tool {
                                label: "Not the same"
                                pixel: Theme.tiny
                                onActivated: shell.confirmDifferentObject(modelData.key)
                            }
                        }
                    }
                }
            }

            Text { text: "People"; font.family: Theme.ui; font.pixelSize: Theme.lead; color: Theme.text }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: shell.relatedPeopleNote !== ""
                text: shell.relatedPeopleNote
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.muted
            }
            Item {
                id: peopleGrid
                objectName: "relatedPeopleGrid"
                property int count: peopleCards.count
                width: Math.max(parent.width, 228)
                implicitWidth: width
                readonly property int cols: Math.max(1, Math.floor(width / 228))
                height: count === 0 ? 0 : Math.ceil(count / cols) * 228
                implicitHeight: height
                Repeater {
                    id: peopleCards
                    model: shell.relatedPeople
                    delegate: Rectangle {
                        objectName: "relatedPersonCard"
                        x: (index % peopleGrid.cols) * 228
                        y: Math.floor(index / peopleGrid.cols) * 228
                        width: 220
                        height: 220
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.line
                        Image {
                            x: 8; y: 8
                            width: 88
                            height: 88
                            source: modelData.thumb
                            fillMode: Image.PreserveAspectCrop
                            asynchronous: true
                            cache: true
                        }
                        Column {
                            x: 104
                            y: 12
                            width: parent.width - 116
                            spacing: 4
                            Text {
                                width: parent.width
                                text: modelData.title
                                wrapMode: Text.WordWrap
                                font.family: Theme.ui
                                font.pixelSize: Theme.body
                                color: Theme.text
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: modelData.stateLabel
                                font.family: Theme.ui
                                font.pixelSize: Theme.small
                                color: desk.stateColor(modelData.state)
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: modelData.countLabel
                                font.family: Theme.ui
                                font.pixelSize: Theme.small
                                color: Theme.muted
                            }
                        }
                        Row {
                            anchors.left: parent.left
                            anchors.bottom: parent.bottom
                            anchors.margins: 8
                            spacing: Theme.gap
                            Tool {
                                label: "Photographs"
                                pixel: Theme.tiny
                                onActivated: shell.openRelatedItem(modelData.key)
                            }
                            Tool {
                                label: "Open in People"
                                pixel: Theme.tiny
                                primary: true
                                onActivated: shell.openRelatedPerson(modelData.subject)
                            }
                        }
                    }
                }
            }

            Text { text: "Relationships"; font.family: Theme.ui; font.pixelSize: Theme.lead; color: Theme.text }
            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                visible: shell.relatedRelationshipsNote !== ""
                text: shell.relatedRelationshipsNote
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.muted
            }
            Item {
                id: relationList
                objectName: "relatedRelationList"
                property int count: relationCards.count
                width: parent.width
                implicitWidth: width
                height: count * 76
                implicitHeight: height
                Repeater {
                    id: relationCards
                    model: shell.relatedRelationships
                    delegate: Rectangle {
                        y: index * 76
                        width: relationList.width
                        height: 72
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.line
                        Column {
                            x: 10
                            y: 8
                            width: parent.width - 20
                            spacing: 2
                            Text {
                                width: parent.width
                                text: modelData.title
                                font.family: Theme.ui
                                font.pixelSize: Theme.body
                                color: Theme.text
                            }
                            Text {
                                width: parent.width
                                wrapMode: Text.WordWrap
                                text: modelData.detail
                                font.family: Theme.ui
                                font.pixelSize: Theme.small
                                color: desk.stateColor(modelData.state)
                            }
                        }
                    }
                }
            }
        }
    }

    Flickable {
        id: photos
        objectName: "relatedPhotos"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.top: sub.bottom
        anchors.margins: Theme.pad
        visible: desk.showingPhotos
        clip: true
        contentWidth: width
        contentHeight: photoHolder.height
        flickableDirection: Flickable.VerticalFlick
        Item {
            id: photoHolder
            width: photos.width
            readonly property int cols: Math.max(1, Math.floor(Math.max(width, 168) / 168))
            height: photoCards.count === 0 ? 0 : Math.ceil(photoCards.count / cols) * 168
            Repeater {
                id: photoCards
                model: shell.relatedPhotos
                delegate: Item {
                    x: (index % photoHolder.cols) * 168
                    y: Math.floor(index / photoHolder.cols) * 168
                    width: 168
                    height: 168
                    Image {
                        id: frame
                        anchors.fill: parent
                        anchors.margins: 6
                        source: "image://archive/t/" + modelData.mediaId
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        cache: true
                    }
                    Rectangle {
                        anchors.fill: frame
                        color: Theme.surface
                        visible: frame.status === Image.Error
                        Text {
                            anchors.centerIn: parent
                            text: "Photo unavailable"
                            font.family: Theme.ui
                            font.pixelSize: Theme.tiny
                            color: Theme.muted
                        }
                    }
                    TapHandler { onTapped: shell.openRelatedPhoto(modelData.mediaId) }
                    Accessible.role: Accessible.Button
                    Accessible.name: "Open photograph"
                }
            }
        }
    }
}
