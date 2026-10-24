import QtQuick

// Film grain. Chrome only. Never place this over a photo.
Image {
    source: "grain.png"
    fillMode: Image.Tile
    opacity: Theme.daylight ? 0.035 : 0.06
    smooth: false
    enabled: false
    Accessible.ignored: true
}
