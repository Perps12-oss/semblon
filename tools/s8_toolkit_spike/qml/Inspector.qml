import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "surfaces"

GlassSurface {
    id: root
    property string runId: ""
    property string packId: ""
    property string selectedLabel: ""
    property string message: ""
    property int clusters: 0
    property int unassigned: 0
    property int reviewRequired: 0
    property int persons: 0
    property int okFaces: 0

    signal nameRequested(string displayName)
    signal noteRequested(string text)
    signal ignoreRequested()
    signal mergeRequested()
    signal splitRequested()
    signal reloadRequested()

    radiusPx: 16
    fillOpacity: 0.18
    implicitWidth: 300

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 8

        Text {
            text: "Inspector"
            color: "#F2F2F2"
            font.pixelSize: 14
            font.family: "Segoe UI"
            font.weight: Font.DemiBold
        }
        Text {
            text: "run_id"
            color: "#B3B3B3"
            font.pixelSize: 11
            font.family: "Segoe UI"
        }
        Text {
            text: root.runId === "" ? "—" : root.runId
            color: "#F2F2F2"
            font.pixelSize: 12
            font.family: "Segoe UI"
            wrapMode: Text.WrapAnywhere
            Layout.fillWidth: true
        }
        Text {
            text: root.packId === "" ? "" : root.packId
            color: "#B3B3B3"
            font.pixelSize: 10
            font.family: "Consolas"
            wrapMode: Text.WrapAnywhere
            Layout.fillWidth: true
        }

        GridLayout {
            columns: 2
            columnSpacing: 8
            rowSpacing: 8
            Layout.fillWidth: true
            EvidenceSurface { Layout.fillWidth: true; label: "review"; value: String(root.reviewRequired) }
            EvidenceSurface { Layout.fillWidth: true; label: "clusters"; value: String(root.clusters) }
            EvidenceSurface { Layout.fillWidth: true; label: "unassigned"; value: String(root.unassigned) }
            EvidenceSurface { Layout.fillWidth: true; label: "persons"; value: String(root.persons) }
        }

        Text {
            text: root.selectedLabel === "" ? "nothing selected" : root.selectedLabel
            color: "#F2F2F2"
            font.pixelSize: 11
            font.family: "Consolas"
            wrapMode: Text.WrapAnywhere
            Layout.fillWidth: true
        }

        TextField {
            id: nameField
            Layout.fillWidth: true
            placeholderText: "Display name"
            color: "#F2F2F2"
            placeholderTextColor: "#808080"
            background: Rectangle {
                radius: 6
                color: "#22000000"
                border.color: "#44FFFFFF"
            }
        }
        Button {
            text: "Name"
            Layout.fillWidth: true
            onClicked: root.nameRequested(nameField.text)
        }
        TextField {
            id: noteField
            Layout.fillWidth: true
            placeholderText: "Note"
            color: "#F2F2F2"
            placeholderTextColor: "#808080"
            background: Rectangle {
                radius: 6
                color: "#22000000"
                border.color: "#44FFFFFF"
            }
        }
        Button {
            text: "Note"
            Layout.fillWidth: true
            onClicked: root.noteRequested(noteField.text)
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Button { text: "Ignore"; Layout.fillWidth: true; onClicked: root.ignoreRequested() }
            Button { text: "Merge"; Layout.fillWidth: true; onClicked: root.mergeRequested() }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Button { text: "Split 1st"; Layout.fillWidth: true; onClicked: root.splitRequested() }
            Button { text: "Reload"; Layout.fillWidth: true; onClicked: root.reloadRequested() }
        }

        Text {
            text: root.message
            color: "#B3B3B3"
            font.pixelSize: 10
            font.family: "Consolas"
            wrapMode: Text.WrapAnywhere
            Layout.fillWidth: true
        }
        Item { Layout.fillHeight: true }
    }
}
