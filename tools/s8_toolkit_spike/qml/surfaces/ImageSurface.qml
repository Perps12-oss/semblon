import QtQuick
import QtQuick.Layouts

GlassSurface {
    id: root
    property url source: ""
    property string caption: ""
    radiusPx: 16
    fillOpacity: 0.10
    clip: true

    Image {
        anchors.fill: parent
        anchors.margins: 1
        source: root.source
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        visible: root.source.toString() !== ""
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity {
            NumberAnimation { duration: 180 }
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.source.toString() === ""
        text: "No still in this snapshot"
        color: "#B3B3B3"
        font.pixelSize: 14
        font.family: "Segoe UI"
    }

    Text {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 12
        text: root.caption
        color: "#F2F2F2"
        font.pixelSize: 12
        font.family: "Segoe UI"
        style: Text.Outline
        styleColor: "#66000000"
    }
}
