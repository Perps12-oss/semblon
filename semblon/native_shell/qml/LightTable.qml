import QtQuick

// The Light Table: four verbs along the bottom edge of the Roll.
Item {
    id: bar
    property string mode: ""          // "", "moment", "detail", "tidy"
    signal peopleRequested()
    signal dateRequested(string prefix)
    signal settingsRequested()
    signal paletteRequested()
    property bool receded: false       // set by the window while the Roll scrolls
    readonly property bool empty: shell.empty
    readonly property alias field: entry
    implicitHeight: panel.height + 12

    function focusEntry(m) {
        if (empty)
            return
        mode = m
        entry.forceActiveFocus()
    }
    function submit() {
        var t = entry.text.trim()
        if (t === "")
            return
        if (/^\d{4}(-\d{1,2})?$/.test(t)) {
            var p = t.split("-")
            bar.dateRequested(p[0] + (p.length > 1 ? "-" + ("0" + p[1]).slice(-2) : ""))
            return
        }
        shell.setSearchMode("text")
        shell.submitCommand(t)
        shell.showMatchesOnRoll()
    }

    HoverHandler { id: nearPointer }
    readonly property bool shrunk: receded && !nearPointer.hovered && mode === "" && !shell.matchesOnRoll

    Rectangle {
        id: panel
        transformOrigin: Item.Bottom
        opacity: bar.shrunk ? 0.35 : 1
        scale: bar.shrunk ? 0.94 : 1
        Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
        Behavior on scale { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 20
        width: Math.min(parent.width - 24, 760)
        height: col.implicitHeight + Theme.pad * 1.4
        radius: Theme.radius * 2
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        Grain { anchors.fill: parent }

        Column {
            id: col
            anchors.centerIn: parent
            width: parent.width - Theme.pad * 2
            spacing: Theme.gap * 1.6

            Rectangle {
                visible: bar.mode === "moment" || bar.mode === "detail"
                width: parent.width
                height: 44
                radius: Theme.pill
                color: Theme.bg
                border.width: entry.activeFocus ? 2 : 1
                border.color: entry.activeFocus ? Theme.amber : Theme.line
                TextInput {
                    id: entry
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    verticalAlignment: TextInput.AlignVCenter
                    font.family: Theme.ui
                    font.pixelSize: Theme.body
                    color: Theme.text
                    clip: true
                    enabled: !bar.empty
                    selectByMouse: true
                    Accessible.name: "Describe what you are looking for"
                    onAccepted: bar.submit()
                    Keys.onEscapePressed: { bar.mode = ""; shell.clearMatches(); text = "" }
                    Text {
                        visible: entry.text === ""
                        text: bar.empty ? "Add a folder of photos first, then search them here"
                              : bar.mode === "detail"
                              ? "Describe it: a red bicycle, a birthday cake, a handwritten sign"
                              : "Type a date or a few words: summer 2019, the beach, a dog"
                        font: entry.font
                        color: Theme.faint
                    }
                }
            }
            Text {
                visible: shell.matchesOnRoll
                width: parent.width
                text: shell.similarNote !== "" ? shell.similarNote : "Showing matches on the roll."
                font.family: Theme.ui
                font.pixelSize: Theme.small
                color: Theme.amber
            }
            Flow {
                width: parent.width
                spacing: Theme.gap
                layoutDirection: Qt.LeftToRight
                Tool {
                    label: "Find a moment"
                    dimmed: bar.empty
                    hint: "Jump to a date or search by words"
                    selected: bar.mode === "moment"
                    onActivated: bar.focusEntry(bar.mode === "moment" ? "" : "moment")
                }
                Tool {
                    objectName: "peopleButton"
                    label: "Find a person"
                    dimmed: bar.empty
                    hint: "Review faces and give them names"
                    onActivated: bar.peopleRequested()
                }
                Tool {
                    label: "Find a detail"
                    dimmed: bar.empty
                    hint: "Describe it, or open a photo and draw around it"
                    selected: bar.mode === "detail"
                    onActivated: bar.focusEntry(bar.mode === "detail" ? "" : "detail")
                }
                Tool {
                    label: "Tidy up"
                    hint: "Find copies of the same photo. Nothing is deleted without asking"
                    dimmed: bar.empty
                    selected: shell.tidyOpen
                    onActivated: shell.openTidy()
                }
                Tool {
                    visible: shell.matchesOnRoll
                    label: "Show everything again"
                    primary: true
                    onActivated: { shell.clearMatches(); entry.text = "" }
                }
                Tool {
                    objectName: "moreButton"
                    label: Qt.platform.os === "osx" ? "More\u2026 \u2318K" : "More\u2026 Ctrl+K"
                    hint: "Every action in one list"
                    quiet: true
                    onActivated: bar.paletteRequested()
                }
            }
        }
    }
}
