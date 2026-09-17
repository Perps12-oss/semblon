import QtQuick
import QtQuick.Layouts

GlassCard {
    id: root
    property string label: ""
    property string value: ""

    implicitHeight: 72
    implicitWidth: 140

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 4
        Text {
            text: root.label
            color: "#B3B3B3"
            font.pixelSize: 11
            font.family: "Segoe UI"
        }
        Text {
            text: root.value
            color: "#F2F2F2"
            font.pixelSize: 20
            font.family: "Segoe UI"
            font.weight: Font.DemiBold
        }
    }
}
