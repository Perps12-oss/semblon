import QtQuick

Item {
    id: root
    property string material: "solid"

    Rectangle {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 12
        width: badge.implicitWidth + 20
        height: 28
        radius: 14
        color: "#44000000"
        border.color: "#33FFFFFF"
        Text {
            id: badge
            anchors.centerIn: parent
            text: "●  " + (root.material === "solid" ? "Solid fallback" : root.material.charAt(0).toUpperCase() + root.material.slice(1) + " ready")
            color: "#F2F2F2"
            font.pixelSize: 11
            font.family: "Segoe UI"
        }
    }
}
