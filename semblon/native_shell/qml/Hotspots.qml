import QtQuick

// Dots over the things in a picture that can be found again. Tap one, or tap anywhere else to look there.
// Opacity, scale and position only: nothing here touches the disk or waits on a search.
Item {
    id: spots
    objectName: "hotspots"

    property Item picture: null         // the painted picture area; dots are placed in its space
    property bool allowed: true         // off while the loupe is on, or when the person hides the dots
    property real hitSize: 44
    property int settleMs: 300          // a second tap inside this window is a zoom, not a search
    readonly property int shimmerMs: Theme.reducedMotion ? 0 : 400

    // Where the last tap on empty picture landed, as a fraction of the picture.
    property real tapX: -1
    property real tapY: -1
    property real tapW: 0
    property real tapH: 0
    readonly property bool tapShown: tapW > 0 && tapH > 0
    property var hidden: []             // dots the person put away for this photo
    property real waitX: 0
    property real waitY: 0
    property var menuDot: null          // the dot whose menu is open

    // The area being looked for, in picture pixels, or null. The rest of the picture is dimmed around it.
    readonly property var target: {
        if (!picture) return null
        if (tapShown) return { x: tapX * picture.width, y: tapY * picture.height, w: tapW * picture.width, h: tapH * picture.height }
        var all = shell.hotspots
        for (var i = 0; i < all.length; i++)
            if (all[i].id === shell.selectedObservationId)
                return { x: all[i].nx * picture.width, y: all[i].ny * picture.height, w: all[i].nw * picture.width, h: all[i].nh * picture.height }
        return null
    }

    signal pickedDot(var dot)
    signal pickedSpot(real nx, real ny)

    visible: allowed && picture !== null
    anchors.fill: parent

    function clearTap() { tapX = -1; tapY = -1; tapW = 0; tapH = 0; hidden = []; menuDot = null; settle.stop() }
    function isHidden(id) { return hidden.indexOf(id) >= 0 }
    function hide(id) { hidden = hidden.concat([id]); menuDot = null }
    function dotAt(x, y) {
        var all = shell.hotspots
        for (var i = 0; i < all.length; i++) {
            if (isHidden(all[i].id)) continue
            var dx = all[i].cx * picture.width - x
            var dy = all[i].cy * picture.height - y
            if (Math.abs(dx) <= hitSize / 2 && Math.abs(dy) <= hitSize / 2)
                return true
        }
        return false
    }
    // Empty picture was tapped. Wait out the zoom window; a second tap calls cancelPending.
    function tapped(x, y) {
        menuDot = null
        if (!picture || picture.width <= 0 || picture.height <= 0 || dotAt(x, y))
            return
        waitX = x; waitY = y
        settle.restart()
    }
    function cancelPending() { settle.stop() }
    function showTap(spec) {
        var p = String(spec || "").split(",")
        if (p.length !== 4) { clearTap(); return }
        tapX = parseFloat(p[0]); tapY = parseFloat(p[1]); tapW = parseFloat(p[2]); tapH = parseFloat(p[3])
    }
    function shimmer() { if (shimmerMs > 0) sweep.restart() }

    Timer {
        id: settle
        interval: spots.settleMs
        onTriggered: spots.pickedSpot(spots.waitX / spots.picture.width, spots.waitY / spots.picture.height)
    }

    // One quick sweep of light on arrival: the picture is being looked over.
    Item {
        anchors.fill: parent
        clip: true
        visible: sweep.running
        Rectangle {
            id: band
            width: parent.width * 0.35
            height: parent.height
            x: -width
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0.0; color: "transparent" }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, 0.16) }
                GradientStop { position: 1.0; color: "transparent" }
            }
        }
        NumberAnimation { id: sweep; target: band; property: "x"; from: -band.width; to: spots.width; duration: Math.max(1, spots.shimmerMs); easing.type: Easing.InOutQuad }
    }

    // Dim everything but the chosen area, so it is clear what is being looked for.
    Item {
        objectName: "dim"
        anchors.fill: parent
        visible: spots.target !== null
        readonly property color shade: Qt.rgba(0, 0, 0, 0.45)
        Rectangle { color: parent.shade; x: 0; y: 0; width: parent.width; height: spots.target ? spots.target.y : 0 }
        Rectangle { color: parent.shade; x: 0; y: spots.target ? spots.target.y + spots.target.h : 0; width: parent.width; height: spots.target ? parent.height - (spots.target.y + spots.target.h) : 0 }
        Rectangle { color: parent.shade; x: 0; y: spots.target ? spots.target.y : 0; width: spots.target ? spots.target.x : 0; height: spots.target ? spots.target.h : 0 }
        Rectangle { color: parent.shade; x: spots.target ? spots.target.x + spots.target.w : 0; y: spots.target ? spots.target.y : 0; width: spots.target ? parent.width - (spots.target.x + spots.target.w) : 0; height: spots.target ? spots.target.h : 0 }
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
            visible: !spots.isHidden(modelData.id)
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
            Accessible.description: "Press Menu for more choices"
            Accessible.onPressAction: dot.go()

            function go() { spots.pickedDot(modelData) }
            function openMenu() { spots.menuDot = dot.modelData }
            Keys.onReturnPressed: go()
            Keys.onEnterPressed: go()
            Keys.onSpacePressed: go()
            Keys.onMenuPressed: openMenu()

            // Dots wait for the sweep, then arrive one after another.
            Component.onCompleted: arrive.start()
            SequentialAnimation {
                id: arrive
                PauseAnimation { duration: Theme.reducedMotion ? 0 : spots.shimmerMs + 60 * dot.index }
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
            // What the dot is for, before anything is tapped.
            Rectangle {
                objectName: "dotTip"
                visible: dot.hot && !dot.chosen
                anchors.horizontalCenter: parent.horizontalCenter
                y: -height - 2
                width: tipText.implicitWidth + 16
                height: 24
                radius: 12
                color: Theme.surface
                border.width: 1
                border.color: Theme.line
                z: 5
                Text {
                    id: tipText
                    anchors.centerIn: parent
                    text: dot.modelData.word
                    font.family: Theme.ui
                    font.pixelSize: Theme.small
                    color: Theme.text
                }
                Accessible.ignored: true
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
            TapHandler { onTapped: dot.go(); onLongPressed: dot.openMenu() }
            TapHandler { acceptedButtons: Qt.RightButton; onTapped: dot.openMenu() }
        }
    }

    // Quick choices for one dot, without waiting for a search.
    Rectangle {
        id: menu
        objectName: "dotMenu"
        visible: spots.menuDot !== null
        readonly property var dotData: spots.menuDot
        x: dotData ? Math.max(4, Math.min(spots.width - width - 4, dotData.cx * spots.picture.width + 14)) : 0
        y: dotData ? Math.max(4, Math.min(spots.height - height - 4, dotData.cy * spots.picture.height + 14)) : 0
        width: 230
        height: menuCol.implicitHeight + 12
        radius: 6
        color: Theme.surface
        border.width: 1
        border.color: Theme.line
        z: 10
        Accessible.role: Accessible.PopupMenu
        Accessible.name: "Choices for this dot"
        onVisibleChanged: if (visible) firstChoice.forceActiveFocus()
        Keys.onEscapePressed: spots.menuDot = null
        Column {
            id: menuCol
            x: 6; y: 6
            width: parent.width - 12
            Tool {
                id: firstChoice
                objectName: "dotFind"
                width: menuCol.width
                label: "Find more like this"
                onActivated: { var d = menu.dotData; spots.menuDot = null; spots.pickedDot(d) }
            }
            Tool {
                objectName: "dotHide"
                width: menuCol.width
                label: "Hide this dot"
                onActivated: spots.hide(menu.dotData.id)
            }
            Tool {
                objectName: "dotShowAll"
                width: menuCol.width
                label: "Show hidden dots again"
                visible: spots.hidden.length > 0
                height: visible ? implicitHeight : 0
                onActivated: { spots.hidden = []; spots.menuDot = null }
            }
        }
    }
}
