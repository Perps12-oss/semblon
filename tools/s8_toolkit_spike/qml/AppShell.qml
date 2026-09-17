import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "surfaces"

Item {
    id: shell
    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        Rectangle {
            id: chrome
            Layout.fillWidth: true
            height: 40
            color: "#22000000"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 8
                Text {
                    text: "SEMBLON"
                    color: "#F2F2F2"
                    font.family: "Segoe UI"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }
                Text {
                    text: "  toolkit spike"
                    color: "#B3B3B3"
                    font.family: "Segoe UI"
                    font.pixelSize: 12
                    Layout.fillWidth: true
                }
                Repeater {
                    model: [
                        { label: "—", act: "min" },
                        { label: "□", act: "max" },
                        { label: "✕", act: "close" }
                    ]
                    delegate: Rectangle {
                        required property var modelData
                        width: 36
                        height: 28
                        radius: 6
                        color: ma.containsMouse ? (modelData.act === "close" ? "#C42B1C" : "#33FFFFFF") : "#00000000"
                        Text {
                            anchors.centerIn: parent
                            text: modelData.label
                            color: "#F2F2F2"
                            font.pixelSize: 12
                        }
                        MouseArea {
                            id: ma
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: {
                                if (modelData.act === "min") window.showMinimized()
                                else if (modelData.act === "max") {
                                    if (window.visibility === Window.Maximized)
                                        window.showNormal()
                                    else
                                        window.showMaximized()
                                } else window.close()
                            }
                        }
                    }
                }
            }
            DragHandler {
                target: null
                onActiveChanged: if (active) window.startSystemMove()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 12
            spacing: 12

            NavigationRail {
                Layout.fillHeight: true
                sections: bridge.sections
                current: bridge.section
                onPicked: (name) => bridge.selectSection(name)
            }
            Workspace {
                Layout.fillWidth: true
                Layout.fillHeight: true
                section: bridge.section
                images: bridge.images
            }
            Inspector {
                Layout.fillHeight: true
                runId: bridge.runId
                packId: bridge.packId
                clusters: bridge.clusters
                unassigned: bridge.unassigned
                okFaces: bridge.okFaces
                persons: bridge.persons
            }
        }
    }

    OverlayLayer {
        anchors.fill: parent
        material: theme.windowMaterial
    }
}
