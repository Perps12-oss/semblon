import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: window
    width: 1180
    height: 720
    minimumWidth: 880
    minimumHeight: 560
    visible: true
    title: "Semblon"
    color: "transparent"
    flags: Qt.Window | Qt.FramelessWindowHint

    background: Rectangle {
        color: theme.windowMaterial === "solid" ? "#1A1A1A" : "#00000000"
    }

    AppShell {
        anchors.fill: parent
    }
}
