import QtQuick

// Tidy up: copies of the same picture lie side by side. Pick the one to keep.
// Nothing is moved until a plain confirm says exactly what will happen.
Item {
    id: tidy
    objectName: "tidyDesk"
    property bool active: shell.tidyOpen
    signal closed()
    visible: opacity > 0.01
    opacity: active ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    focus: active
    Keys.onEscapePressed: { shell.closeTidy(); tidy.closed() }
    Accessible.role: Accessible.Pane
    Accessible.name: "Tidy up"

    Rectangle { anchors.fill: parent; color: Theme.bg }
    Grain { anchors.fill: parent }

    Text {
        id: head
        x: Theme.pad * 1.5; y: Theme.pad
        text: "Tidy up"
        font.family: Theme.display
        font.pixelSize: Theme.hero * 0.8
        font.weight: Font.Light
        color: Theme.text
    }
    Text {
        objectName: "tidySummary"
        x: Theme.pad * 1.5
        anchors.top: head.bottom
        width: parent.width - Theme.pad * 12
        wrapMode: Text.WordWrap
        text: shell.tidySummary + (shell.tidySets.length > 0
              ? ". Choose the copy to keep. Nothing is removed until you say so." : "")
        font.family: Theme.ui
        font.pixelSize: Theme.body
        color: Theme.muted
    }
    Tool {
        objectName: "tidyBack"
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.pad
        label: "Back to photos"
        onActivated: { shell.closeTidy(); tidy.closed() }
    }

    Rectangle {
        objectName: "tidyProgress"
        visible: shell.tidyBusy
        x: Theme.pad * 1.5; y: 118
        width: parent.width - Theme.pad * 12; height: 6
        radius: 3
        color: Theme.line
        Accessible.role: Accessible.ProgressBar
        Accessible.name: "Looking for copies, " + shell.tidyPercent + " percent done"
        Rectangle {
            width: parent.width * shell.tidyPercent / 100; height: parent.height
            radius: 3
            color: Theme.amber
            Behavior on width { NumberAnimation { duration: 200 } }
        }
    }

    Flow {
        id: bar
        objectName: "tidyBar"
        x: Theme.pad * 1.5; y: 130
        width: parent.width - Theme.pad * 12
        spacing: Theme.gap
        Tool { objectName: "tidyExact"; label: "Exact copies"; selected: shell.tidyExactOn; hint: "Show copies that are the same file"; onActivated: shell.toggleTidyExact() }
        Tool { objectName: "tidyNear"; label: "Near copies"; selected: shell.tidyNearOn; hint: "Show pictures that look almost the same"; onActivated: shell.toggleTidyNear() }
        Text { text: "Sort by"; height: 32; verticalAlignment: Text.AlignVCenter; leftPadding: Theme.pad; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.faint }
        Tool { objectName: "sortCopies"; label: "Most copies"; selected: shell.tidySort === "copies"; onActivated: shell.setTidySort("copies") }
        Tool { objectName: "sortSize"; label: "Biggest"; selected: shell.tidySort === "size"; onActivated: shell.setTidySort("size") }
        Tool { objectName: "sortName"; label: "Name"; selected: shell.tidySort === "name"; onActivated: shell.setTidySort("name") }
        Tool { objectName: "sortTime"; label: "Newest"; selected: shell.tidySort === "time"; onActivated: shell.setTidySort("time") }
    }
    Flow {
        id: picks
        objectName: "tidyPicks"
        visible: shell.tidySets.length > 0
        x: Theme.pad * 1.5; y: 176
        width: parent.width - Theme.pad * 12
        spacing: Theme.gap
        Text { text: shell.tidyPickedCount === 0 ? "Tick photos to bin several at once." : shell.tidyPickedCount + " ticked"; height: 32; verticalAlignment: Text.AlignVCenter; font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted; rightPadding: Theme.pad }
        Tool { objectName: "pickRest"; label: "Tick all but the first in each set"; onActivated: shell.pickAllButFirst() }
        Tool { objectName: "pickClear"; label: "Clear ticks"; visible: shell.tidyPickedCount > 0; onActivated: shell.clearTidyPicks() }
        Tool { objectName: "pickBin"; label: "Move ticked to the Recycle Bin"; primary: true; visible: shell.tidyPickedCount > 0; onActivated: shell.binPicked() }
    }

    ListView {
        id: sets
        objectName: "tidySets"
        anchors.fill: parent
        anchors.topMargin: 220
        anchors.leftMargin: Theme.pad * 1.5
        anchors.rightMargin: Theme.pad * 1.5
        clip: true
        spacing: Theme.pad * 1.5
        model: shell.tidySets
        activeFocusOnTab: true
        delegate: Column {
            id: group
            property int setIndex: modelData.id
            width: sets.width
            spacing: Theme.gap
            Text {
                text: (modelData.exact ? "Exact copies" : "Near copies") + " \u00b7 " + modelData.members.length + " photos"
                font.family: Theme.ui
                font.pixelSize: Theme.tiny
                font.weight: Font.DemiBold
                font.letterSpacing: 1.2
                color: Theme.faint
            }
            Row {
                spacing: Theme.pad
                Repeater {
                    model: modelData.members
                    delegate: Column {
                        spacing: 6
                        width: 200
                        Rectangle {
                            width: 200; height: 150
                            color: Theme.surface
                            border.width: modelData.picked ? 3 : 1
                            border.color: modelData.picked ? Theme.amber : Theme.line
                            MouseArea { anchors.fill: parent; onClicked: shell.toggleTidyPick(modelData.path) }
                            Image {
                                anchors.fill: parent
                                anchors.margins: 2
                                source: modelData.thumb
                                fillMode: Image.PreserveAspectFit
                                asynchronous: true
                                Accessible.ignored: true
                            }
                        }
                        Text { width: parent.width; elide: Text.ElideMiddle; text: modelData.name; font.family: Theme.ui; font.pixelSize: Theme.body; color: Theme.text }
                        Text { width: parent.width; elide: Text.ElideRight; text: modelData.folder + " \u00b7 " + modelData.size + (modelData.when ? " \u00b7 " + modelData.when : ""); font.family: Theme.ui; font.pixelSize: Theme.small; color: Theme.muted }
                        Tool {
                            objectName: "tickCopy"
                            label: modelData.picked ? "Ticked" : "Tick"
                            selected: modelData.picked
                            hint: "Tick " + modelData.name + " to bin it with others"
                            onActivated: shell.toggleTidyPick(modelData.path)
                        }
                        Tool {
                            objectName: "keepCopy"
                            label: "Keep this one"
                            primary: index === 0
                            hint: "Keep " + modelData.name + " and offer to bin the other copies"
                            onActivated: shell.keepCopy(group.setIndex, index)
                        }
                    }
                }
            }
        }
        Text {
            visible: shell.tidySets.length === 0 && !shell.tidyBusy
            text: "No copies found."
            font.family: Theme.display
            font.pixelSize: Theme.title
            color: Theme.muted
        }
    }
}
