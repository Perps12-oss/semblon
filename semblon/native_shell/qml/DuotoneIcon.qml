import QtQuick

// Soft-fill duotone glyph: solid rounded shape + cutout punched to cutoutColor.
Canvas {
    id: root
    width: 18
    height: 18
    antialiasing: true

    property string icon: "grid"
    property color fillColor: "#8A8D93"
    property color cutoutColor: "#1c1d21"

    onIconChanged: requestPaint()
    onFillColorChanged: requestPaint()
    onCutoutColorChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    Component.onCompleted: requestPaint()

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        var w = width
        var h = height
        var f = String(fillColor)
        var c = String(cutoutColor)
        ctx.fillStyle = f

        function roundRect(x, y, rw, rh, r) {
            r = Math.min(r, rw / 2, rh / 2)
            ctx.beginPath()
            ctx.moveTo(x + r, y)
            ctx.lineTo(x + rw - r, y)
            ctx.quadraticCurveTo(x + rw, y, x + rw, y + r)
            ctx.lineTo(x + rw, y + rh - r)
            ctx.quadraticCurveTo(x + rw, y + rh, x + rw - r, y + rh)
            ctx.lineTo(x + r, y + rh)
            ctx.quadraticCurveTo(x, y + rh, x, y + rh - r)
            ctx.lineTo(x, y + r)
            ctx.quadraticCurveTo(x, y, x + r, y)
            ctx.closePath()
            ctx.fill()
        }

        function punchCircle(cx, cy, r) {
            ctx.fillStyle = c
            ctx.beginPath()
            ctx.arc(cx, cy, r, 0, Math.PI * 2)
            ctx.fill()
            ctx.fillStyle = f
        }

        function punchRect(x, y, rw, rh, r) {
            ctx.fillStyle = c
            r = Math.min(r || 0, rw / 2, rh / 2)
            ctx.beginPath()
            if (r <= 0) {
                ctx.rect(x, y, rw, rh)
            } else {
                ctx.moveTo(x + r, y)
                ctx.lineTo(x + rw - r, y)
                ctx.quadraticCurveTo(x + rw, y, x + rw, y + r)
                ctx.lineTo(x + rw, y + rh - r)
                ctx.quadraticCurveTo(x + rw, y + rh, x + rw - r, y + rh)
                ctx.lineTo(x + r, y + rh)
                ctx.quadraticCurveTo(x, y + rh, x, y + rh - r)
                ctx.lineTo(x, y + r)
                ctx.quadraticCurveTo(x, y, x + r, y)
                ctx.closePath()
            }
            ctx.fill()
            ctx.fillStyle = f
        }

        var ic = icon
        if (ic === "grid" || ic === "library") {
            // Stacked photo rectangles.
            roundRect(2, 4, 12, 11, 2)
            punchRect(4, 6, 8, 5, 1)
            ctx.fillStyle = f
            roundRect(5, 2, 11, 3, 1.5)
        } else if (ic === "people") {
            ctx.beginPath()
            ctx.arc(9, 6.2, 3.2, 0, Math.PI * 2)
            ctx.fill()
            ctx.beginPath()
            ctx.moveTo(2.5, 16)
            ctx.quadraticCurveTo(9, 10.5, 15.5, 16)
            ctx.lineTo(2.5, 16)
            ctx.closePath()
            ctx.fill()
            punchCircle(9, 6.2, 1.4)
        } else if (ic === "search") {
            ctx.beginPath()
            ctx.arc(7.5, 7.5, 5.2, 0, Math.PI * 2)
            ctx.fill()
            punchCircle(7.5, 7.5, 3.1)
            ctx.fillStyle = f
            ctx.save()
            ctx.translate(12.2, 12.2)
            ctx.rotate(0.7)
            roundRect(-1.2, -1.2, 5.8, 2.4, 1.1)
            ctx.restore()
        } else if (ic === "plus" || ic === "addFolder") {
            // Folder body + accent-like plus badge (badge uses fill; cutout for +).
            roundRect(1.5, 5, 15, 11, 2)
            ctx.fillStyle = f
            roundRect(1.5, 3.5, 7, 3, 1.5)
            punchRect(4, 8, 10, 5, 1)
            // Plus badge
            ctx.fillStyle = f
            roundRect(10, 1, 7, 7, 2)
            punchRect(12.9, 2.4, 1.2, 4.2, 0.5)
            punchRect(11.4, 3.9, 4.2, 1.2, 0.5)
        } else if (ic === "gear" || ic === "settings") {
            ctx.beginPath()
            ctx.arc(9, 9, 7.2, 0, Math.PI * 2)
            ctx.fill()
            // Simple tooth notches via cutout ring + center hole
            punchCircle(9, 9, 5.4)
            ctx.fillStyle = f
            ctx.beginPath()
            ctx.arc(9, 9, 3.8, 0, Math.PI * 2)
            ctx.fill()
            punchCircle(9, 9, 1.8)
        } else if (ic === "folder") {
            roundRect(1.5, 5, 15, 11, 2)
            roundRect(1.5, 3.5, 7, 3, 1.5)
            punchRect(4, 8, 10, 5, 1)
        } else if (ic === "media" || ic === "sheets") {
            roundRect(4, 2, 11, 13, 2)
            ctx.globalAlpha = 0.85
            roundRect(2, 4, 11, 13, 2)
            ctx.globalAlpha = 1
            punchRect(4.5, 7, 6, 4, 1)
        } else if (ic === "tag" || ic === "moments") {
            ctx.beginPath()
            ctx.moveTo(2, 7)
            ctx.lineTo(10, 2)
            ctx.lineTo(16, 8)
            ctx.lineTo(8, 16)
            ctx.closePath()
            ctx.fill()
            punchCircle(11.5, 6.5, 1.5)
        } else if (ic === "similar" || ic === "spark") {
            // Two overlapping rounded cards.
            roundRect(2, 5, 9, 10, 2)
            roundRect(7, 3, 9, 10, 2)
            punchRect(9, 6, 5, 4, 1)
        } else if (ic === "calendar" || ic === "years") {
            roundRect(2, 3, 14, 13, 2)
            punchRect(3.5, 7, 11, 7, 1)
            ctx.fillStyle = f
            roundRect(2, 3, 14, 4, 2)
            punchRect(5, 1.5, 1.6, 3.5, 0.6)
            punchRect(11.4, 1.5, 1.6, 3.5, 0.6)
        } else {
            roundRect(3, 3, 12, 12, 3)
            punchRect(6, 6, 6, 6, 1)
        }
    }
}
