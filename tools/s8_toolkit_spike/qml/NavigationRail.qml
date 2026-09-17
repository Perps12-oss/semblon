import QtQuick
import QtQuick.Layouts
import "surfaces"

GlassSurface {
    id: root
    property var sections: []
    property string current: "Review"
    signal picked(string name)

    radiusPx: 16
    fillOpacity: 0.18
    implicitWidth: 196

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 6

        Text {
            text: "SEMBLON"
            color: "#F2F2F2"
            font.pixelSize: 13
            font.family: "Segoe UI"
            font.letterSpacing: 1.2
            font.weight: Font.DemiBold
        }
        Text {
            text: "Shell spike"
            color: "#B3B3B3"
            font.pixelSize: 11
            font.family: "Segoe UI"
            Layout.bottomMargin: 8
        }

        Repeater {
            model: root.sections
            delegate: Item {
                required property string modelData
                Layout.fillWidth: true
                height: 36
                GlassCard {
                    anchors.fill: parent
                    radiusPx: 10
                    fillOpacity: root.current === modelData ? 0.28 : 0.0
                    stroke: root.current === modelData ? "#4CC2FF" : "#00000000"
                    Behavior on fillOpacity {
                        NumberAnimation { duration: 160 }
                    }
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 12
                    text: modelData
                    color: root.current === modelData ? "#F2F2F2" : "#B3B3B3"
                    font.pixelSize: 14
                    font.family: "Segoe UI"
                }
                MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.picked(modelData)
                }
            }
        }
        Item { Layout.fillHeight: true }
    }
}
