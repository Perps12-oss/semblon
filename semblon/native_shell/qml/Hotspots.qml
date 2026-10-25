import QtQuick

// Dots over the things in a picture that can be found again. Tap one, or tap anywhere else to look there.
// Opacity and scale only: nothing here touches the disk or waits on a search.
Item {
    id: spots
    objectName: "hotspots"

    property Item picture: null          // the painted picture area; dots are placed in its space
    property bool allowed: true         // off while the loupe is on, or when the person hides the dots
    property real hitSize: 44

    // Where the last tap on empty picture landed, as a fraction of the picture.
    property real tapX: -1
    property real tapY: -1
    property real tapW: 0
    property real tapH: 0
    readonly property bool tapShown: tapW > 0 && tapH > 0

    signal pickedDot(string observationId)
    signal pickedSpot(real nx, real ny)

    visible: allowed && picture !== null
    anchors.fill: parent

    function clearTap() { tapX = -1; tapY = -1; tapW = 0; tapH = 0 }
    function dotAt(x, y) {
        var spotsNow = shell.hotspots
        for (var i = 0; i < spotsNow.length; i++) {
            var dx = spotsNow[i].cx * picture.width - x
            var dy = spotsNow[i].cy * picture.height - y
            if (Math.abs(dx) <= hitSize / 2 && Math.abs(dy) <= hitSize / 2)
                return true
        }
        return false
    }
    // Empty picture was tapped. Dots keep their own taps.
    function tapped(x, y) {
        if (!picture || picture.width <= 0 || picture.height <= 0 || dotAt(x, y))
            return
        pickedSpot(x / picture.width, y / picture.height)
    }
    function showTap(spec) {
        var p = String(spec || "").split(",")
        if (p.length !== 4) { clearTap(); return }
        tapX = parseFloat(p[0]); tapY = parseFloat(p[1]); tapW = parseFloat(p[2]); tapH = parseFloat(p[3])
    }

    Rectangle {
        objectName: "tapMark"
        visible: spots.tapShown
        x: spots.tapX * spots.picture.width
        y: spots.tapY * spots.picture.height
        width: spots.tapW * spots.picture.width
        height: spots.tapH * spots.picture.height
        radius: Math.min(width, height) / 2
        color: Qt.rgba(Theme.amber.r, Theme.amber.g, Theme.amber.b, 0.14)
        border.width: 2
        border.color: Theme.amber
        Accessible.ignored: true
    }

    Repeater {
        model: shell.hotspots
        delegate: Item {
            id: dot
            required property var modelData
            required property int index
            objectName: "hotspot"
            readonly property bool hot: hover.hovered || activeFocus
            readonly property bool chosen: shell.selectedObservationId === modelData.id
            x: modelData.cx * spots.picture.width - width / 2
            y: modelData.cy * spots.picture.height - height / 2
            width: spots.hitSize
            height: spots.hitSize
            opacity: 0
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: "Find more like this: " + modelData.label
            Accessible.onPressAction: dot.go()

            function go() { spots.pickedDot(modelData.id) }
            Keys.onReturnPressed: go()
            Keys.onEnterPressed: go()
            Keys.onSpacePressed: go()

            // Dots arrive one after another, then settle.
            Component.onCompleted: arrive.start()
            SequentialAnimation {
                id: arrive
                PauseAnimation { duration: Theme.reducedMotion ? 0 : 60 * dot.index }
                NumberAnimation { target: dot; property: "opacity"; to: 1; duration: Theme.medium }
            }

            // The area this dot stands for, shown on hover, focus and once chosen.
            Rectangle {
                visible: dot.hot || dot.chosen
                x: dot.modelData.nx * spots.picture.width - dot.x
                y: dot.modelData.ny * spots.picture.height - dot.y
                width: dot.modelData.nw * spots.picture.width
                height: dot.modelData.nh * spots.picture.height
                radius: 3
                color: "transparent"
                border.width: dot.chosen ? 3 : 2
                border.color: Theme.amber
                opacity: 0.9
            }
            // Keyboard focus ring.
            Rectangle {
                visible: dot.activeFocus
                anchors.centerIn: parent
                width: 34; height: 34; radius: 17
                color: "transparent"
                border.width: 2
                border.color: Theme.text
            }
            // Slow breathing ring: draws the eye without animating anything heavy.
            Rectangle {
                id: ring
                anchors.centerIn: parent
                width: 18; height: 18; radius: 9
                color: "transparent"
                border.width: 2
                border.color: Theme.amber
                opacity: 0
                scale: 1
                SequentialAnimation {
                    running: dot.visible && spots.visible && !Theme.reducedMotion && !shell.searchBusy && !dot.chosen
                    loops: Animation.Infinite
                    ParallelAnimation {
                        NumberAnimation { target: ring; property: "scale"; from: 1; to: 2.2; duration: 1600; easing.type: Easing.OutQuad }
                        NumberAnimation { target: ring; property: "opacity"; from: 0.75; to: 0; duration: 1600; easing.type: Easing.OutQuad }
                    }
                    PauseAnimation { duration: 700 }
                }
            }
            Rectangle {
                anchors.centerIn: parent
                width: dot.hot || dot.chosen ? 20 : 14
                height: width
                radius: width / 2
                color: Theme.amber
                border.width: 2
                border.color: Theme.bg
                Behavior on width { NumberAnimation { duration: Theme.fast } }
            }
            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: dot.go() }
        }
    }
}
