import QtQuick

// The one in-theme question sheet. Every "are you sure?" and every "get this ready?" lands here,
// so nothing ever opens a grey system pop-up. Buttons are verbs. Progress shows inline.
Item {
    id: confirm
    objectName: "confirmSheet"
    readonly property var ask: shell.confirm
    readonly property bool open: ask.open === true
    readonly property bool busy: ask.busy === true
    readonly property var facts: ask.facts || []

    visible: opacity > 0.01
    opacity: open ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
    enabled: open
    onOpenChanged: if (open) panel.forceActiveFocus()

    Rectangle {
        anchors.fill: parent
        color: Theme.scrim
        MouseArea { anchors.fill: parent; hoverEnabled: true }
    }

    Rectangle {
        id: panel
        objectName: "confirmPanel"
        anchors.centerIn: parent
        width: Math.min(parent.width - 60, 520)
        height: col.implicitHeight + Theme.pad * 3
        radius: Theme.radius * 1.6
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        scale: confirm.open ? 1 : 0.97
        Behavior on scale { NumberAnimation { duration: Theme.medium; easing.type: Theme.easing } }
        focus: true
        activeFocusOnTab: false
        Accessible.role: Accessible.Dialog
        Accessible.name: confirm.ask.title || ""
        Accessible.description: confirm.ask.body || ""
        Keys.onEscapePressed: if (!confirm.busy) shell.confirmDecline()

        Grain { anchors.fill: parent }

        Column {
            id: col
            x: Theme.pad * 1.5
            y: Theme.pad * 1.5
            width: parent.width - Theme.pad * 3
            spacing: Theme.pad
            Text {
                objectName: "confirmTitle"
                width: parent.width
                wrapMode: Text.WordWrap
                text: confirm.ask.title || ""
                font.family: Theme.display
                font.pixelSize: Theme.title
                font.weight: Font.Medium
                color: Theme.text
            }
            Text {
                objectName: "confirmBody"
                width: parent.width
                wrapMode: Text.WordWrap
                text: confirm.ask.body || ""
                font.family: Theme.ui
                font.pixelSize: Theme.body
                lineHeight: 1.25
                color: Theme.muted
            }
            Column {
                width: parent.width
                spacing: 6
                visible: confirm.facts.length > 0
                Repeater {
                    model: confirm.facts
                    delegate: Row {
                        spacing: 10
                        Rectangle { y: 7; width: 6; height: 6; radius: 3; color: Theme.amber }
                        Text {
                            width: col.width - 16
                            wrapMode: Text.WordWrap
                            text: modelData
                            font.family: Theme.ui
                            font.pixelSize: Theme.small
                            color: Theme.text
                        }
                    }
                }
            }
            // Progress, inline, while the extra is being fetched.
            Column {
                objectName: "confirmProgress"
                width: parent.width
                spacing: 8
                visible: confirm.busy
                Text {
                    width: parent.width
                    wrapMode: Text.WordWrap
                    text: confirm.ask.progress || "Getting it ready\u2026"
                    font.family: Theme.ui
                    font.pixelSize: Theme.body
                    color: Theme.text
                }
                Rectangle {
                    width: parent.width
                    height: 6
                    radius: 3
                    color: Theme.line
                    clip: true
                    Rectangle {
                        id: sweep
                        width: parent.width * 0.3
                        height: parent.height
                        radius: 3
                        color: Theme.amber
                        SequentialAnimation on x {
                            running: confirm.busy && !Theme.reducedMotion
                            loops: Animation.Infinite
                            NumberAnimation { from: -sweep.width; to: sweep.parent.width; duration: 1300; easing.type: Easing.InOutQuad }
                        }
                    }
                }
            }
            Row {
                visible: !confirm.busy
                anchors.right: parent.right
                spacing: Theme.gap
                Tool {
                    id: no
                    objectName: "confirmNo"
                    label: confirm.ask.no || "Not now"
                    KeyNavigation.tab: yes
                    KeyNavigation.backtab: yes
                    onActivated: shell.confirmDecline()
                }
                Tool {
                    id: yes
                    objectName: "confirmYes"
                    label: confirm.ask.yes || "Continue"
                    primary: true
                    KeyNavigation.tab: no
                    KeyNavigation.backtab: no
                    onActivated: shell.confirmAccept()
                }
            }
        }
    }
    // Land on the primary verb when the sheet appears.
    Connections {
        target: confirm
        function onOpenChanged() { if (confirm.open) Qt.callLater(function () { (confirm.ask.danger ? no : yes).forceActiveFocus() }) }
    }
}
