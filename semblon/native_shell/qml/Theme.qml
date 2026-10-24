pragma Singleton
import QtQuick

// Every colour, size and motion value the Light Table uses lives here.
QtObject {
    id: theme

    property bool daylight: false
    property bool reducedMotion: false

    readonly property string display: "Fraunces"
    readonly property string ui: "Inter"

    // Darkroom: warm blacks and a safelight amber. Daylight: paper and ink.
    readonly property color bg: daylight ? "#f4efe6" : "#0e0b09"
    readonly property color surface: daylight ? "#fbf8f2" : "#171310"
    readonly property color raised: daylight ? "#ffffff" : "#221c17"
    readonly property color line: daylight ? "#d6cbb7" : "#3a2f24"
    readonly property color text: daylight ? "#2a2118" : "#f3eadb"
    readonly property color muted: daylight ? "#5a4e3d" : "#b9ab95"
    readonly property color faint: daylight ? "#6f6350" : "#938672"
    readonly property color amber: daylight ? "#9a5200" : "#ffa63d"
    readonly property color amberSoft: daylight ? "#ead3b3" : "#3d2a14"
    readonly property color onAmber: daylight ? "#fffaf0" : "#1a1006"
    readonly property color danger: daylight ? "#a3261a" : "#ff8a7a"
    readonly property color ok: daylight ? "#386b1f" : "#a6d98a"
    readonly property color bgClear: Qt.rgba(bg.r, bg.g, bg.b, 0)
    readonly property color amberEdge: Qt.rgba(amber.r, amber.g, amber.b, 0.38)
    readonly property color paper: "#f3ead8"
    readonly property color paperInk: "#2a2118"
    readonly property color paperMuted: "#5a4e3d"
    readonly property color scrim: daylight ? "#cc2a2118" : "#d9080605"

    // Type scale in logical pixels. Qt scales these with the display.
    readonly property int tiny: 12
    readonly property int small: 13
    readonly property int body: 15
    readonly property int lead: 18
    readonly property int title: 28
    readonly property int hero: 52

    readonly property int gap: 8
    readonly property int pad: 16
    readonly property int radius: 10
    readonly property int pill: 999
    readonly property int edge: 60

    // Motion. Reduced motion turns every duration to zero.
    readonly property int fast: reducedMotion ? 0 : 120
    readonly property int medium: reducedMotion ? 0 : 240
    readonly property int slow: reducedMotion ? 0 : 420
    readonly property int easing: Easing.OutCubic
}
