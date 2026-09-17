import QtQuick

Rectangle {
    id: root
    property real radiusPx: 14
    property color fill: "#66FFFFFF"
    property real fillOpacity: 0.22
    property color stroke: "#33FFFFFF"

    radius: radiusPx
    color: Qt.rgba(fill.r, fill.g, fill.b, fillOpacity)
    border.color: stroke
    border.width: 1
}
