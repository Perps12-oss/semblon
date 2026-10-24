import QtQuick

// The Light Table: four verbs along the bottom edge of the Roll.
Item {
    id: bar
    property string mode: ""          // "", "moment", "detail", "tidy"
    signal peopleRequested()
    signal dateRequested(string prefix)
    signal settingsRequested()
    signal paletteRequested()
    readonly property alias field: entry
    implicitHeight: panel.height + 12

    function focusEntry(m) { mode = m; entry.forceActiveFocus() }
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

    Rectangle {
        id: panel
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
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
            spacing: Theme.gap

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
                    selectByMouse: true
                    Accessible.name: "Describe what you are looking for"
                    onAccepted: bar.submit()
                    Keys.onEscapePressed: { bar.mode = ""; shell.clearMatches(); text = "" }
                    Text {
                        visible: entry.text === ""
                        text: bar.mode === "detail"
                              ? "Describe it: a red bicycle, a birthday cake, a handwritten sign"
                              : "Type a date or a few words: summer 2019, the beach, a dog"
                        font: entry.font
                        color: Theme.faint
                    }
                }
            }
            Text {
                visible: bar.mode === "tidy"
                width: parent.width
                wrapMode: Text.WordWrap
                text: shell.resultText !== "" ? shell.resultText
                      : "Tidy up only reports. It never moves or deletes your photos."
                font.family: Theme.ui
                font.pixelSize: Theme.small
                color: Theme.muted
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
                    hint: "Jump to a date or search by words"
                    selected: bar.mode === "moment"
                    onActivated: bar.focusEntry(bar.mode === "moment" ? "" : "moment")
                }
                Tool {
                    objectName: "peopleButton"
                    label: "Find a person"
                    hint: "Review faces and give them names"
                    onActivated: bar.peopleRequested()
                }
                Tool {
                    label: "Find a detail"
                    hint: "Describe it, or open a photo and draw around it"
                    selected: bar.mode === "detail"
                    onActivated: bar.focusEntry(bar.mode === "detail" ? "" : "detail")
                }
                Tool {
                    label: "Tidy up"
                    selected: bar.mode === "tidy"
                    onActivated: { bar.mode = bar.mode === "tidy" ? "" : "tidy"; if (bar.mode === "tidy") shell.scanDuplicates() }
                }
                Tool {
                    visible: shell.matchesOnRoll
                    label: "Show everything again"
                    primary: true
                    onActivated: { shell.clearMatches(); entry.text = "" }
                }
                Tool { label: "Everything (Ctrl+K)"; quiet: true; onActivated: bar.paletteRequested() }
            }
        }
    }
}
