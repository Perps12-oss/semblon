import QtQuick
import QtQuick.Layouts
import "surfaces"

GlassSurface {
    id: root
    property var images: []
    property string section: "Review"
    radiusPx: 18
    fillOpacity: 0.12

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        Text {
            text: root.section
            color: "#F2F2F2"
            font.pixelSize: 20
            font.family: "Segoe UI"
            font.weight: Font.DemiBold
        }
        Text {
            text: "Presentation only — FaceKit stays in Python."
            color: "#B3B3B3"
            font.pixelSize: 12
            font.family: "Segoe UI"
        }

        ListView {
            id: strip
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 12
            orientation: ListView.Horizontal
            model: root.images
            boundsBehavior: Flickable.StopAtBounds
            delegate: ImageSurface {
                width: Math.min(strip.height * 0.85, 320)
                height: strip.height
                source: modelData
                caption: ""
            }
            Text {
                anchors.centerIn: parent
                visible: root.images.length === 0
                text: "No media paths in snapshot"
                color: "#B3B3B3"
                font.family: "Segoe UI"
            }
        }
    }
}
