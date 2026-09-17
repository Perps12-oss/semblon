import QtQuick
import QtQuick.Layouts
import "surfaces"

GlassSurface {
    id: root
    property string runId: ""
    property string packId: ""
    property int clusters: 0
    property int unassigned: 0
    property int okFaces: 0
    property int persons: 0
    radiusPx: 16
    fillOpacity: 0.18
    implicitWidth: 280

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 14
        spacing: 10

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
            text: root.packId
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
            EvidenceSurface { Layout.fillWidth: true; label: "ok faces"; value: String(root.okFaces) }
            EvidenceSurface { Layout.fillWidth: true; label: "clusters"; value: String(root.clusters) }
            EvidenceSurface { Layout.fillWidth: true; label: "unassigned"; value: String(root.unassigned) }
            EvidenceSurface { Layout.fillWidth: true; label: "persons"; value: String(root.persons) }
        }
        Item { Layout.fillHeight: true }
    }
}
