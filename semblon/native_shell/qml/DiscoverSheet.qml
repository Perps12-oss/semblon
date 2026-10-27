import QtQuick

// A small intent chooser. Every choice opens a view of the same archive.
Item {
    id: chooser
    property bool open: false
    signal dismissed()
    signal chosen(string category)

    visible: opacity > 0.01
    opacity: open ? 1 : 0
    z: 100
    Behavior on opacity { NumberAnimation { duration: Theme.fast } }

    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        opacity: chooser.open ? 1 : 0
        MouseArea {
            anchors.fill: parent
            onClicked: chooser.dismissed()
        }
    }

    Sheet {
        id: panel
        heading: "Discover"
        open: chooser.open
        anchors.centerIn: parent
        width: Math.min(parent.width - 40, 620)
        height: Math.min(parent.height - 40, 430)
        onDismissed: chooser.dismissed()

        Column {
            anchors.fill: parent
            spacing: Theme.gap * 1.5

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Choose what you want to find. Each view uses the photos already in your library."
                font.family: Theme.ui
                font.pixelSize: Theme.body
                color: Theme.muted
            }

            Flow {
                width: parent.width
                spacing: Theme.gap
                Tool {
                    label: "People"
                    primary: true
                    hint: "Review faces and name someone only when you are sure"
                    onActivated: chooser.chosen("people")
                }
                Tool {
                    label: "Objects"
                    hint: "Search object labels already found in your photos"
                    onActivated: chooser.chosen("objects")
                }
                Tool {
                    label: "Regions"
                    hint: "Open a photo, draw around a detail, and find similar areas"
                    onActivated: chooser.chosen("regions")
                }
                Tool {
                    label: "Words in photos"
                    hint: "Find text that appears inside your pictures"
                    onActivated: chooser.chosen("words")
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.line
            }

            Text {
                width: parent.width
                wrapMode: Text.WordWrap
                text: "Objects are searched from labels already stored in the library. If the optional object extra is missing or photos need another scan, Semblon will say so. Nothing is silently downloaded."
                font.family: Theme.ui
                font.pixelSize: Theme.small
                color: Theme.faint
            }
        }
    }
}
