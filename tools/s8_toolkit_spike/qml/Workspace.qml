import QtQuick
import QtQuick.Layouts
import "surfaces"

GlassSurface {
    id: root
    property string section: "Review"
    property var images: []
    property var items: []
    property int selectedIndex: -1
    property int donorIndex: -1
    signal itemClicked(int index)
    signal itemDonorToggled(int index)

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
            visible: root.section !== "Review"
            text: "Workspace stub — Review is the live vertical. FaceKit stays in Python."
            color: "#B3B3B3"
            font.pixelSize: 12
            font.family: "Segoe UI"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }
        Text {
            visible: root.section === "Review"
            text: "Clusters are evidence. Name creates a person. Click = select; Ctrl+click = merge donor."
            color: "#B3B3B3"
            font.pixelSize: 12
            font.family: "Segoe UI"
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        ListView {
            id: boardList
            visible: root.section === "Review"
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.preferredHeight: parent.height * 0.45
            clip: true
            spacing: 4
            model: root.items
            boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                required property var modelData
                required property int index
                width: boardList.width
                height: 36
                radius: 8
                color: {
                    if (index === root.selectedIndex)
                        return "#334CC2FF"
                    if (index === root.donorIndex)
                        return "#33C4A35A"
                    return "#00000000"
                }
                border.width: index === root.selectedIndex || index === root.donorIndex ? 1 : 0
                border.color: index === root.donorIndex ? "#C4A35A" : "#4CC2FF"
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.leftMargin: 10
                    anchors.right: parent.right
                    anchors.rightMargin: 10
                    text: modelData.label
                    color: "#F2F2F2"
                    font.pixelSize: 12
                    font.family: "Consolas"
                    elide: Text.ElideRight
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: (mouse) => {
                        if (mouse.modifiers & Qt.ControlModifier)
                            root.itemDonorToggled(index)
                        else
                            root.itemClicked(index)
                    }
                }
            }
            Text {
                anchors.centerIn: parent
                visible: root.items.length === 0
                text: "No board items — open a store with a finished run"
                color: "#B3B3B3"
                font.family: "Segoe UI"
            }
        }

        ListView {
            id: strip
            visible: root.section === "Review"
            Layout.fillWidth: true
            Layout.preferredHeight: 160
            clip: true
            spacing: 12
            orientation: ListView.Horizontal
            model: root.images
            boundsBehavior: Flickable.StopAtBounds
            delegate: ImageSurface {
                width: Math.min(strip.height * 0.85, 220)
                height: strip.height
                source: modelData
                caption: ""
            }
            Text {
                anchors.centerIn: parent
                visible: root.images.length === 0
                text: "Select an item with media paths"
                color: "#B3B3B3"
                font.family: "Segoe UI"
            }
        }

        Item {
            visible: root.section !== "Review"
            Layout.fillWidth: true
            Layout.fillHeight: true
        }
    }
}
