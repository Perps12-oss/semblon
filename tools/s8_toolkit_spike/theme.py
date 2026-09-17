"""Semantic theme tokens. QML reads these; do not scatter hex in components."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal


class Theme(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._window_material = "mica"
        self._surface_primary = "#66FFFFFF"
        self._surface_secondary = "#33111111"
        self._surface_elevated = "#4DFFFFFF"
        self._border_subtle = "#33FFFFFF"
        self._text_primary = "#F2F2F2"
        self._text_secondary = "#B3B3B3"
        self._accent = "#4CC2FF"
        self._radius_sm = 8
        self._radius_md = 14
        self._radius_lg = 20
        self._spacing_xs = 6
        self._spacing_sm = 10
        self._spacing_md = 16
        self._spacing_lg = 24
        self._font_family = "Segoe UI"
        self._font_size_sm = 12
        self._font_size_md = 14
        self._font_size_lg = 20
        self._motion_fast = 140
        self._motion_md = 220

    def set_material(self, name: str) -> None:
        self._window_material = name
        self.changed.emit()

    @Property(str, notify=changed)
    def windowMaterial(self):
        return self._window_material

    @Property(str, notify=changed)
    def surfacePrimary(self):
        return self._surface_primary

    @Property(str, notify=changed)
    def surfaceSecondary(self):
        return self._surface_secondary

    @Property(str, notify=changed)
    def surfaceElevated(self):
        return self._surface_elevated

    @Property(str, notify=changed)
    def borderSubtle(self):
        return self._border_subtle

    @Property(str, notify=changed)
    def textPrimary(self):
        return self._text_primary

    @Property(str, notify=changed)
    def textSecondary(self):
        return self._text_secondary

    @Property(str, notify=changed)
    def accent(self):
        return self._accent

    @Property(int, notify=changed)
    def radiusSm(self):
        return self._radius_sm

    @Property(int, notify=changed)
    def radiusMd(self):
        return self._radius_md

    @Property(int, notify=changed)
    def radiusLg(self):
        return self._radius_lg

    @Property(int, notify=changed)
    def spacingXs(self):
        return self._spacing_xs

    @Property(int, notify=changed)
    def spacingSm(self):
        return self._spacing_sm

    @Property(int, notify=changed)
    def spacingMd(self):
        return self._spacing_md

    @Property(int, notify=changed)
    def spacingLg(self):
        return self._spacing_lg

    @Property(str, notify=changed)
    def fontFamily(self):
        return self._font_family

    @Property(int, notify=changed)
    def fontSizeSm(self):
        return self._font_size_sm

    @Property(int, notify=changed)
    def fontSizeMd(self):
        return self._font_size_md

    @Property(int, notify=changed)
    def fontSizeLg(self):
        return self._font_size_lg

    @Property(int, notify=changed)
    def motionFast(self):
        return self._motion_fast

    @Property(int, notify=changed)
    def motionMd(self):
        return self._motion_md
