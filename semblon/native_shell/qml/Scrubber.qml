import QtQuick

// Chronological navigation strip (Phase 1 + Phase 2 density lens + Phase 3 loupe).
// Calendar time and Roll contentY are different metric spaces — reconciled only
// through geometry snapshots (time_for_offset / offset_for_year on the bridge).
// Modes stay Phase 1: idle | armed | tracking | settling.
// Phase 3 maps: HOVER = idle+gutter; DRAGGING = tracking; SETTLING unchanged.
// Loupe visualises the drag destination — never a second navigation controller.
Item {
    id: edge
    property var roll
    property int armThreshold: 6
    property string mode: "idle"   // idle | armed | tracking | settling
    property var snapshot: null
    property var passiveGeometry: null
    property int snapshotGen: -1
    property real pressY: 0
    property real pressX: 0
    property real pointerY: -1
    property real pointerX: 0
    property int destinationYear: -1
    property bool destinationUndated: false
    property var frozenSegment: null
    property real hoverY: -1
    property real hoverX: -1

    // Phase 2 ribbon — density-aware cells (cached; invalidated with geometry).
    property var yearRibbon: []
    property int lensYear: -1
    property string lensMonth: ""   // "YYYY-MM" or ""
    property string lensDay: ""     // "YYYY-MM-DD" or ""
    property var lensMonths: []
    property var lensDays: []
    property real lensAnchorY: 0
    property real lensAnchorH: 0
    // Click target captured at press (before drag threshold) so a click can
    // navigate to the magnified period without ever having moved the archive.
    property string pressPeriodKind: ""   // year | month | day | undated | ""
    property string pressPeriodKey: ""

    // Phase 3 — loupe presentation (ephemeral). Flag from bridge; default on.
    property bool loupeEnabled: shell ? shell.loupeEnabled : true
    property bool gutterHover: false
    property int hoverReadoutYear: -1
    property int hoverReadoutCount: 0
    property real pointerYearFrac: -1
    property int pointerCalendarYear: -1   // authoritative empty-year label (not a detent)
    property bool pointerOverEmpty: false
    property bool loupeVisible: loupeEnabled && (mode === "tracking" || mode === "settling")

    readonly property bool dragging: mode === "armed" || mode === "tracking"
    readonly property bool hovered: seek.containsMouse || dragging
    // Spatial exclusivity: gutter → Phase 3 HOVER; ribbon → Phase 2 lens. Never both.
    readonly property bool lensOpen: mode === "idle" && lensYear >= 0 && !gutterHover
    readonly property bool phase3Hover: loupeEnabled && mode === "idle" && gutterHover
    readonly property real innerTop: 14
    // Chronological dated track occupies the full inner strip. Undated lives in
    // the terminal padding below — outside the dated calendar coordinate system —
    // so its presence cannot rescale dated year positions.
    readonly property real innerH: Math.max(1, height - 28)
    readonly property real undatedZoneTop: innerTop + innerH
    readonly property real undatedZoneH: Math.max(0, height - undatedZoneTop - 2)
    readonly property int total: roll ? roll.count : 0
    readonly property real railW: 5
    readonly property real gutterHitW: Theme.loupeGutterW

    width: Theme.edge
    z: 5
    objectName: "scrubber"
    property string accessNote: ""
    Accessible.role: Accessible.Slider
    Accessible.name: "Time strip. Arrow keys move year by year among years that have photographs."
    Accessible.description: accessNote
    activeFocusOnTab: true
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    Keys.onPressed: function (event) {
        // During DRAGGING (armed/tracking), only Escape is handled — ignore arrows/Tab.
        if (mode === "armed" || mode === "tracking") {
            if (event.key === Qt.Key_Escape) {
                abortGesture(true)
                event.accepted = true
            } else {
                event.accepted = true
            }
            return
        }
        // Keyboard contract (production): arrows / Home / End step among populated
        // years; Escape cancels armed/tracking/settling. Loupe follows settling.
        if (event.key === Qt.Key_Up) { stepYear(-1); event.accepted = true }
        else if (event.key === Qt.Key_Down) { stepYear(1); event.accepted = true }
        else if (event.key === Qt.Key_Home) { stepToEnd(true); event.accepted = true }
        else if (event.key === Qt.Key_End) { stepToEnd(false); event.accepted = true }
        else if (event.key === Qt.Key_Escape && mode !== "idle") {
            abortGesture(true)
            event.accepted = true
        }
    }

    Connections {
        target: shell
        function onLoupeChanged() { edge.loupeEnabled = shell.loupeEnabled }
    }

    function refreshAccessNote() {
        if (loupeVisible && temporalLoupe && temporalLoupe.accessAnnounce) {
            accessNote = temporalLoupe.accessAnnounce
            return
        }
        if (mode === "tracking" || mode === "settling") {
            if (destinationUndated)
                accessNote = "Destination: undated photographs"
            else if (destinationYear >= 0)
                accessNote = "Destination: " + destinationYear
            else
                accessNote = ""
            return
        }
        if (phase3Hover && hoverReadoutYear >= 0) {
            accessNote = "Year " + hoverReadoutYear
                    + (hoverReadoutCount > 0 ? (", " + hoverReadoutCount + " photographs") : "")
            return
        }
        var seg = liveSegment()
        if (!seg) {
            accessNote = roll && roll.heading !== "" ? roll.heading : ""
            return
        }
        if (seg.kind === "undated")
            accessNote = "Viewport: undated photographs"
        else if (seg.kind === "mixed")
            accessNote = "Viewport: " + Math.floor(seg.timeLo) + " to " + Math.floor(seg.timeHi) + ", plus undated"
        else if (seg.kind === "dated")
            accessNote = "Viewport: " + Math.floor(seg.timeLo) + " to " + Math.floor(seg.timeHi)
        else
            accessNote = roll && roll.heading !== "" ? roll.heading : ""
    }

    function refreshSnapshot() {
        if (!roll || !roll.layoutReady)
            return null
        var g = shell.temporalNavGeometry(
            roll.columns, !roll.matchMode, roll.dayBreaks,
            roll.cellW, roll.monthH, roll.dayH
        )
        return g
    }

    function ensureGeometry() {
        if (mode !== "idle")
            return snapshot
        if (!passiveGeometry)
            passiveGeometry = refreshSnapshot()
        return passiveGeometry
    }

    function invalidateGeometry() {
        passiveGeometry = null
        if (mode === "idle")
            snapshot = null
        yearRibbon = []
        clearLens()
        ribbonRefresh.restart()
    }

    function clearLens() {
        cancelLensLeave()
        lensHover = false
        lensYear = -1
        lensMonth = ""
        lensDay = ""
        lensMonths = []
        lensDays = []
        lensAnchorY = 0
        lensAnchorH = 0
    }

    function refreshYearRibbon() {
        if (!roll || !roll.layoutReady)
            return
        try {
            yearRibbon = shell.ribbonYearCells() || []
        } catch (e) {
            yearRibbon = []
        }
    }

    function colorForYear(year) {
        for (var i = 0; i < yearRibbon.length; i++) {
            if (yearRibbon[i].year === year && yearRibbon[i].color)
                return yearRibbon[i].color
        }
        return ""
    }

    function slotForYear(year) {
        var items = slots.items || []
        for (var i = 0; i < items.length; i++) {
            if (items[i].kind === "year" && items[i].year === year)
                return items[i]
        }
        return null
    }

    function yearAtY(y) {
        var g = ensureGeometry()
        if (!g)
            return -1
        if (g.undated && y >= undatedZoneTop - 0.5)
            return -1
        var t = stripT(y)
        var at = yearFracAtT(g, t)
        if (!at)
            return -1
        var year = nearestDetent(g, at.yearFrac)
        return year === null ? -1 : year
    }

    function isGutterX(x) {
        return x >= 0 && x < gutterHitW
    }

    function updateGutterHover(x, y) {
        if (!loupeEnabled || mode !== "idle") {
            gutterHover = false
            hoverReadoutYear = -1
            hoverReadoutCount = 0
            return
        }
        if (!isGutterX(x) || y < 0) {
            gutterHover = false
            hoverReadoutYear = -1
            hoverReadoutCount = 0
            return
        }
        // Gutter HOVER — calendar year under pointer (empty years stay empty, count 0).
        // Never show Phase 2 preview simultaneously.
        clearLens()
        gutterHover = true
        var r = resolveAtY(y)
        if (r.undated || r.pointerYear < 0) {
            hoverReadoutYear = -1
            hoverReadoutCount = 0
            return
        }
        hoverReadoutYear = r.pointerYear
        hoverReadoutCount = 0
        if (!r.empty) {
            for (var i = 0; i < yearRibbon.length; i++) {
                if (yearRibbon[i].year === r.pointerYear) {
                    hoverReadoutCount = yearRibbon[i].photoCount || 0
                    break
                }
            }
        }
    }

    // Local temporal lens: pointer stays on the strip. The hovered year's slot is
    // subdivided into months (then days) without moving other years' calendar
    // positions. Never touches contentY.
    function updateLensFromHover(y) {
        if (mode !== "idle")
            return
        // Gutter owns Phase 3 HOVER; ribbon owns Phase 2 lens.
        if (loupeEnabled && gutterHover)
            return
        if (y < 0) {
            clearLens()
            return
        }
        var year = yearAtY(y)
        if (year < 0) {
            clearLens()
            return
        }
        var slot = slotForYear(year)
        if (!slot || !slot.populated) {
            clearLens()
            return
        }
        if (year !== lensYear) {
            lensYear = year
            lensMonth = ""
            lensDay = ""
            lensDays = []
            lensAnchorY = slot.y
            lensAnchorH = slot.h
            try {
                lensMonths = shell.ribbonMonthCells(year) || []
            } catch (e) {
                lensMonths = []
            }
        } else {
            lensAnchorY = slot.y
            lensAnchorH = slot.h
        }
        if (!lensMonths.length) {
            lensMonth = ""
            lensDay = ""
            lensDays = []
            return
        }
        // Subdivide this year slot only — local expansion, not a global rescale.
        var local = y - slot.y
        var monthH = slot.h / lensMonths.length
        var idx = Math.max(0, Math.min(lensMonths.length - 1, Math.floor(local / Math.max(1e-6, monthH))))
        var cell = lensMonths[idx]
        if (!cell)
            return
        if (cell.key !== lensMonth) {
            lensMonth = cell.key
            lensDay = ""
            try {
                lensDays = shell.ribbonDayCells(cell.key) || []
            } catch (e) {
                lensDays = []
            }
        }
        if (!lensDays.length) {
            lensDay = ""
            return
        }
        var dayLocal = local - idx * monthH
        var dayH = monthH / lensDays.length
        var di = Math.max(0, Math.min(lensDays.length - 1, Math.floor(dayLocal / Math.max(1e-6, dayH))))
        lensDay = lensDays[di] ? lensDays[di].key : ""
    }

    function capturePressPeriod(y) {
        pressPeriodKind = ""
        pressPeriodKey = ""
        if (lensDay !== "") {
            pressPeriodKind = "day"
            pressPeriodKey = lensDay
            return
        }
        if (lensMonth !== "") {
            pressPeriodKind = "month"
            pressPeriodKey = lensMonth
            return
        }
        var year = yearAtY(y)
        if (year >= 0) {
            pressPeriodKind = "year"
            pressPeriodKey = String(year)
            return
        }
        var g = ensureGeometry()
        if (g && g.undated && y >= undatedZoneTop - 0.5) {
            pressPeriodKind = "undated"
            pressPeriodKey = "undated"
        }
    }

    function navigateToPressPeriod() {
        if (!roll)
            return false
        if (pressPeriodKind === "month" && pressPeriodKey !== "") {
            mode = "settling"
            roll.navigateToMonth(pressPeriodKey)
            return true
        }
        if (pressPeriodKind === "day" && pressPeriodKey !== "") {
            var cells = lensDays
            var first = -1
            for (var i = 0; i < cells.length; i++) {
                if (cells[i].key === pressPeriodKey) {
                    first = cells[i].photoFirst
                    break
                }
            }
            if (first >= 0) {
                // Instant land on the day's first frame, then return to idle.
                roll.jumpToIndex(first)
                resetIdle()
                return true
            }
            if (pressPeriodKey.length >= 7) {
                mode = "settling"
                roll.navigateToMonth(pressPeriodKey.substring(0, 7))
                return true
            }
        }
        return false
    }

    Timer {
        id: ribbonRefresh
        interval: 40
        repeat: false
        onTriggered: edge.refreshYearRibbon()
    }
    // Pointer can leave the strip briefly while entering the lens/preview.
    // Delay clear so ribbon ↔ preview moves do not flicker the lens shut.
    property bool lensHover: false
    Timer {
        id: lensLeave
        interval: 120
        repeat: false
        onTriggered: {
            if (edge.mode === "idle" && !seek.containsMouse && !edge.lensHover)
                edge.clearLens()
        }
    }
    function scheduleLensLeave() {
        if (mode !== "idle")
            return
        lensLeave.restart()
    }
    function cancelLensLeave() {
        lensLeave.stop()
    }

    function stripT(y) {
        return Math.max(0, Math.min(1, (y - innerTop) / innerH))
    }

    function yForT(t) {
        return innerTop + Math.max(0, Math.min(1, t)) * innerH
    }

    function yearFracAtT(g, t) {
        // Dated track only — full [0,1]. Undated is selected via undatedZoneTop.
        if (!g || g.calendarFirst > g.calendarLast)
            return null
        var years = g.calendarLast - g.calendarFirst + 1
        var local = Math.max(0, Math.min(1, t))
        return { kind: "dated", yearFrac: g.calendarLast + 1 - local * years }
    }

    function tForYearFrac(g, yearFrac) {
        if (!g || g.calendarFirst > g.calendarLast)
            return 0
        var top = g.calendarLast + 1
        var bottom = g.calendarFirst
        if (top === bottom)
            return 0
        var local = (top - yearFrac) / (top - bottom)
        return Math.max(0, Math.min(1, local))
    }

    function timeForDay(day) {
        if (!day || day.length < 10)
            return { kind: "undated" }
        var year = parseInt(day.substring(0, 4))
        var month = parseInt(day.substring(5, 7))
        var dayN = parseInt(day.substring(8, 10))
        if (!(year > 0) || !(month >= 1 && month <= 12) || !(dayN >= 1 && dayN <= 31))
            return { kind: "undated" }
        var frac = (month - 1) / 12.0 + (Math.min(dayN, 28) - 1) / (12.0 * 28.0)
        return { kind: "dated", yearFrac: year + frac }
    }

    function nearestDetent(g, yearFrac) {
        var detents = g && g.detents ? g.detents : []
        if (!detents.length)
            return null
        var best = detents[0], bestD = Math.abs((best + 0.5) - yearFrac)
        for (var i = 1; i < detents.length; i++) {
            var d = Math.abs((detents[i] + 0.5) - yearFrac)
            if (d < bestD) { best = detents[i]; bestD = d }
        }
        return best
    }

    function offsetForYear(g, year) {
        if (!g || !g.years)
            return null
        for (var i = 0; i < g.years.length; i++) {
            var y = g.years[i]
            if (y.year === year)
                return y.populated ? y.contentStart : null
        }
        return null
    }

    function timeForOffset(g, contentY) {
        if (!g)
            return { kind: "undated" }
        if (g.undated && contentY >= g.undated.contentStart - 1e-6)
            return { kind: "undated" }
        var populated = []
        for (var i = 0; i < (g.years || []).length; i++)
            if (g.years[i].populated)
                populated.push(g.years[i])
        if (!populated.length)
            return { kind: "undated" }
        if (contentY <= g.datedContentStart)
            return { kind: "dated", yearFrac: populated[populated.length - 1].year + 1 }
        if (contentY >= g.datedContentEnd - 1e-6)
            return { kind: "dated", yearFrac: populated[0].year }
        for (var j = populated.length - 1; j >= 0; j--) {
            var e = populated[j]
            if (contentY < e.contentStart - 1e-6 || contentY > e.contentEnd + 1e-6)
                continue
            var span = Math.max(e.contentEnd - e.contentStart, 1e-9)
            var progress = (contentY - e.contentStart) / span
            progress = Math.max(0, Math.min(1, progress))
            return { kind: "dated", yearFrac: e.year + 1 - progress }
        }
        return { kind: "dated", yearFrac: populated[0].year + 0.5 }
    }

    property var viewportSeg: ({ kind: "empty" })

    function liveSegment() {
        // Freeze only while Armed/Tracking. On release (Settling/Idle) resume
        // reporting the actual viewport as contentY moves.
        if (mode === "armed" || mode === "tracking")
            return frozenSegment
        return viewportSeg
    }

    function updateViewportSeg() {
        if (mode === "armed" || mode === "tracking")
            return
        var g = mode === "settling" ? (snapshot || ensureGeometry()) : ensureGeometry()
        viewportSeg = computeSegment(g) || ({ kind: "empty" })
    }

    function computeSegment(g) {
        if (!roll || !g)
            return { kind: "empty" }
        var band = roll.visibleBand()
        var dated = []
        var undatedVisible = false
        function take(p) {
            if (!p) return
            if (p.kind === "undated") undatedVisible = true
            else if (p.yearFrac !== undefined) dated.push(p.yearFrac)
        }
        // Prefer actual visible media day keys over animation targets.
        var media = roll.visibleMediaIndices()
        if (media.top >= 0)
            take(timeForDay(shell.dayAt(media.top)))
        if (media.bottom >= 0)
            take(timeForDay(shell.dayAt(media.bottom)))
        take(timeForOffset(g, band.top))
        take(timeForOffset(g, band.bottom))
        for (var i = 0; i < (g.years || []).length; i++) {
            var y = g.years[i]
            if (!y.populated) continue
            if (y.contentStart >= band.top - 1e-6 && y.contentStart <= band.bottom + 1e-6)
                take(timeForOffset(g, y.contentStart))
            if (y.contentEnd >= band.top - 1e-6 && y.contentEnd <= band.bottom + 1e-6)
                take(timeForOffset(g, y.contentEnd))
        }
        if (g.undated) {
            var u = g.undated
            if (!(band.bottom < u.contentStart || band.top > u.contentEnd))
                undatedVisible = true
        }
        if (dated.length && undatedVisible)
            return { kind: "mixed", timeLo: Math.min.apply(null, dated), timeHi: Math.max.apply(null, dated), undatedVisible: true }
        if (dated.length)
            return { kind: "dated", timeLo: Math.min.apply(null, dated), timeHi: Math.max.apply(null, dated), undatedVisible: false }
        if (undatedVisible)
            return { kind: "undated", undatedVisible: true }
        return { kind: "empty" }
    }

    function calendarYearAtFrac(g, yearFrac) {
        if (!g || g.calendarFirst > g.calendarLast)
            return -1
        // yearFrac runs calendarLast+1 (top) → calendarFirst (bottom).
        // Exact integers are the top edge of the lower year.
        var y = (yearFrac === Math.floor(yearFrac)) ? (yearFrac - 1) : Math.floor(yearFrac)
        return Math.min(g.calendarLast, Math.max(g.calendarFirst, y))
    }

    function yearIsPopulated(g, year) {
        if (!g || !g.years)
            return false
        for (var i = 0; i < g.years.length; i++) {
            if (g.years[i].year === year)
                return !!g.years[i].populated
        }
        return false
    }

    // One authoritative resolution for display AND navigation. Loupe and
    // commitDestination both consume these fields — never recompute separately.
    function resolveAtY(y) {
        var none = {
            kind: "none", pointerYear: -1, destinationYear: -1,
            undated: false, empty: false, yearFrac: -1
        }
        var g = ensureGeometry()
        if (!g)
            return none
        if (g.undated && y >= undatedZoneTop - 0.5) {
            return {
                kind: "undated", pointerYear: -1, destinationYear: -1,
                undated: true, empty: false, yearFrac: -1
            }
        }
        var t = stripT(y)
        var at = yearFracAtT(g, t)
        if (!at)
            return none
        var pointerYear = calendarYearAtFrac(g, at.yearFrac)
        var empty = pointerYear >= 0 && !yearIsPopulated(g, pointerYear)
        var dest = nearestDetent(g, at.yearFrac)
        if (dest === null) {
            return {
                kind: "none", pointerYear: pointerYear, destinationYear: -1,
                undated: false, empty: empty, yearFrac: at.yearFrac
            }
        }
        return {
            kind: "dated", pointerYear: pointerYear, destinationYear: dest,
            undated: false, empty: empty, yearFrac: at.yearFrac
        }
    }

    function applyResolution(r) {
        destinationUndated = !!r.undated
        destinationYear = r.destinationYear
        pointerYearFrac = r.yearFrac
        pointerCalendarYear = r.pointerYear
        pointerOverEmpty = !!r.empty && !r.undated
    }

    function selectAtY(y) {
        applyResolution(resolveAtY(y))
    }

    function commitDestination() {
        var g = snapshot || ensureGeometry()
        if (!g || !roll) {
            resetIdle()
            return
        }
        if (snapshotGen >= 0 && shell.archiveGeneration() !== snapshotGen) {
            // Archive mutated under the gesture — abandon safely.
            abortGesture(true)
            return
        }
        // Consume the same destinationYear the loupe already displays.
        var offset = null
        var yearKey = ""
        if (destinationUndated && g.undated) {
            offset = g.undated.contentStart
            yearKey = ""
        } else if (destinationYear >= 0) {
            offset = offsetForYear(g, destinationYear)
            yearKey = String(destinationYear)
        }
        if (offset === null || offset === undefined) {
            resetIdle()
            return
        }
        mode = "settling"
        if (yearKey !== "")
            roll.navigateToYearOffset(offset, yearKey)
        else
            roll.navigateToOffset(offset - roll.headerHeight, "")
        updateViewportSeg()
    }

    function resetIdle() {
        mode = "idle"
        destinationYear = -1
        destinationUndated = false
        frozenSegment = null
        snapshot = null
        snapshotGen = -1
        pointerY = -1
        pointerX = 0
        hoverY = -1
        hoverX = -1
        pressX = 0
        pointerYearFrac = -1
        pointerCalendarYear = -1
        pointerOverEmpty = false
        gutterHover = false
        hoverReadoutYear = -1
        hoverReadoutCount = 0
        pressPeriodKind = ""
        pressPeriodKey = ""
        // Refresh passive geometry after a gesture so the segment matches the new layout.
        passiveGeometry = null
        // Keep lens closed after a navigate; hover will reopen without moving content.
        clearLens()
    }

    function abortGesture(cancelNav) {
        if (cancelNav && roll && roll.navigating)
            roll.cancelNavigation()
        resetIdle()
    }

    function arm(y) {
        if (mode === "settling") {
            // Second drag during settling: redirect path — reject until settled if
            // redirect is unsafe; here we cancel and re-arm on the new geometry.
            if (roll)
                roll.cancelNavigation()
            resetIdle()
        }
        // Capture magnified period before closing the lens for Phase 1 drag chrome.
        capturePressPeriod(y)
        clearLens()
        gutterHover = false
        hoverReadoutYear = -1
        hoverReadoutCount = 0
        snapshot = refreshSnapshot()
        snapshotGen = snapshot ? snapshot.generation : shell.archiveGeneration()
        frozenSegment = computeSegment(snapshot)
        // pointerX / pressX are set by the seek MouseArea (or tests) before arm().
        pressY = y
        pressX = pointerX
        pointerY = y
        hoverY = y
        hoverX = pointerX
        destinationYear = -1
        destinationUndated = false
        pointerYearFrac = -1
        pointerCalendarYear = -1
        pointerOverEmpty = false
        mode = "armed"
    }

    function track(y) {
        pointerY = y
        hoverY = y
        hoverX = pointerX
        if (mode === "armed" && Math.abs(y - pressY) < armThreshold)
            return
        if (mode === "armed") {
            mode = "tracking"
            // Drag uses Phase 1 year scrub — drop finer click target.
            pressPeriodKind = ""
            pressPeriodKey = ""
        }
        selectAtY(y)
    }

    function release(y) {
        if (mode === "idle")
            return
        pointerY = y
        hoverY = y
        hoverX = pointerX
        if (mode === "armed") {
            // Magnified period click (Phase 2) always navigates — loupe does not
            // steal month/day targets captured under the ribbon lens.
            if (navigateToPressPeriod()) {
                pressPeriodKind = ""
                pressPeriodKey = ""
                return
            }
            // Bare year-click without drag: with loupe on, require a scrub so the
            // destination surface can show landing feedback first.
            if (loupeEnabled) {
                resetIdle()
                return
            }
            selectAtY(y)
            if (destinationYear < 0 && !destinationUndated) {
                resetIdle()
                return
            }
            commitDestination()
            return
        }
        if (mode === "tracking") {
            // Phase 3: undated shows feedback but release does not commit.
            if (loupeEnabled && destinationUndated) {
                resetIdle()
                return
            }
            commitDestination()
            return
        }
    }

    function stepYear(dir) {
        var g = refreshSnapshot()
        snapshot = g
        if (!g || !g.detents || !g.detents.length || !roll)
            return
        var detents = g.detents  // newest first
        var cur = -1
        var seg = computeSegment(g)
        if (seg && seg.kind !== "undated" && seg.timeHi !== undefined)
            cur = nearestDetent(g, seg.timeHi)
        var idx = detents.indexOf(cur)
        if (idx < 0) idx = 0
        // Up = newer (toward top, lower index); Down = older.
        var next = Math.max(0, Math.min(detents.length - 1, idx + dir))
        var year = detents[next]
        var offset = offsetForYear(g, year)
        if (offset === null)
            return
        destinationYear = year
        destinationUndated = false
        frozenSegment = seg
        mode = "settling"
        roll.navigateToYearOffset(offset, String(year))
    }

    function stepToEnd(newest) {
        var g = refreshSnapshot()
        snapshot = g
        if (!g || !g.detents || !g.detents.length || !roll)
            return
        var year = newest ? g.detents[0] : g.detents[g.detents.length - 1]
        var offset = offsetForYear(g, year)
        if (offset === null)
            return
        destinationYear = year
        destinationUndated = false
        frozenSegment = computeSegment(g)
        mode = "settling"
        roll.navigateToYearOffset(offset, String(year))
    }

    // Kept for tests / bridge callers that still invoke go/step/stepTo.
    function go(my) {
        arm(my)
        selectAtY(my)
        commitDestination()
    }
    function step(d) { stepYear(d) }
    function stepTo(i) {
        var g = refreshSnapshot()
        if (!g || !g.detents || !g.detents.length) return
        var idx = Math.max(0, Math.min(g.detents.length - 1, i))
        var year = g.detents[idx]
        var offset = offsetForYear(g, year)
        if (offset === null) return
        destinationYear = year
        frozenSegment = computeSegment(g)
        mode = "settling"
        roll.navigateToYearOffset(offset, String(year))
    }

    // Slot chrome uses cached geometry only — never refresh inside a binding.
    readonly property var slots: buildLegacySlots(passiveGeometry || snapshot)
    readonly property string currentKey: roll ? roll.currentMonth : ""
    readonly property var months: roll ? roll.monthList : []
    property int linearIndex: 0
    function buildLegacySlots(g) {
        var out = { items: [], unit: 0, labelEvery: 1 }
        if (!g || g.calendarFirst > g.calendarLast)
            return out
        var years = g.calendarLast - g.calendarFirst + 1
        // Dated years always fill the full chronological track (innerH).
        var datedH = innerH
        var u = datedH / Math.max(1, years)
        out.unit = u
        out.labelEvery = u >= 14 ? 1 : (u >= 8 ? 2 : 0)
        for (var i = 0; i < years; i++) {
            var year = g.calendarLast - i
            var y = innerTop + i * u
            var populated = false
            var key = ""
            for (var j = 0; j < (g.years || []).length; j++) {
                if (g.years[j].year === year) {
                    populated = g.years[j].populated
                    break
                }
            }
            if (populated && roll && roll.monthList) {
                for (var m = 0; m < roll.monthList.length; m++) {
                    var mk = roll.monthList[m].key
                    if (mk.length >= 4 && mk.substring(0, 4) === String(year)) {
                        key = mk
                        break
                    }
                }
            }
            out.items.push({
                kind: "year",
                label: String(year),
                y: y,
                h: u,
                key: key,
                index: i,
                populated: populated,
                year: year
            })
        }
        if (g.undated) {
            out.items.push({
                kind: "undated",
                label: "Undated",
                y: undatedZoneTop,
                h: Math.max(12, undatedZoneH),
                key: "",
                index: years,
                populated: true
            })
        }
        return out
    }

    Connections {
        target: edge.roll ? edge.roll.view : null
        function onContentYChanged() {
            if (edge.roll)
                edge.linearIndex = edge.roll.topIndex()
            // Idle and Settling both report the live viewport from actual contentY.
            if (edge.mode === "idle" || edge.mode === "settling")
                viewportPulse.restart()
        }
    }
    Timer {
        id: viewportPulse
        interval: 32
        repeat: false
        onTriggered: edge.updateViewportSeg()
    }
    Connections {
        target: edge.roll
        function onNavigationFinished(completed) {
            if (edge.mode === "settling")
                edge.resetIdle()
            edge.updateViewportSeg()
        }
        function onRowsChanged() { edge.invalidateGeometry(); edge.updateViewportSeg() }
        function onCellWChanged() { edge.invalidateGeometry(); edge.updateViewportSeg() }
        function onMonthListChanged() { edge.invalidateGeometry(); edge.updateViewportSeg() }
        function onLayoutReadyChanged() { if (edge.roll.layoutReady) edge.updateViewportSeg() }
    }
    Component.onCompleted: {
        Qt.callLater(edge.updateViewportSeg)
        Qt.callLater(edge.refreshYearRibbon)
    }
    Connections {
        target: archiveModel
        function onModelReset() {
            if (edge.mode !== "idle")
                edge.abortGesture(true)
            edge.invalidateGeometry()
            edge.updateViewportSeg()
        }
        function onRowsInserted() {
            // Never navigate from a stale snapshot after archive mutation.
            if (edge.mode !== "idle")
                edge.abortGesture(true)
            else
                edge.invalidateGeometry()
            edge.updateViewportSeg()
        }
        function onRowsRemoved() {
            if (edge.mode !== "idle")
                edge.abortGesture(true)
            else
                edge.invalidateGeometry()
            edge.updateViewportSeg()
        }
    }

    // Track background.
    Rectangle {
        anchors.fill: parent
        color: edge.hovered || edge.mode !== "idle" ? Theme.line : Theme.raised
        Behavior on color { ColorAnimation { duration: Theme.fast } }
        Rectangle { width: 1; height: parent.height; color: Theme.muted }
        Rectangle { x: 1; width: edge.railW; height: parent.height; color: Theme.bg; opacity: 0.45 }
        Grain { anchors.fill: parent }
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -2
        color: "transparent"
        border.width: 2
        border.color: Theme.amber
        visible: edge.activeFocus
    }

    // Chronological year marks: populated = detent tick; empty = gap (no tick).
    // Phase 2: populated years also carry one density-aware colour wash (not per-photo marks).
    Repeater {
        model: edge.slots.items
        delegate: Item {
            id: slot
            readonly property bool isYear: modelData.kind === "year"
            readonly property bool isUndated: modelData.kind === "undated"
            readonly property bool populated: modelData.populated === true
            readonly property string yearColor: slot.isYear && slot.populated ? edge.colorForYear(modelData.year) : ""
            y: modelData.y
            width: edge.width
            height: Math.max(1, modelData.h)

            Rectangle {
                // One coherent year cell — colour from capped cached thumbs, else faint wash.
                visible: slot.isYear && slot.populated && slot.height >= 3
                x: edge.railW + 2
                width: parent.width - edge.railW - 4
                height: Math.max(2, parent.height - 2)
                y: 1
                radius: 2
                color: slot.yearColor !== "" ? slot.yearColor : Theme.amberSoft
                opacity: edge.lensYear === modelData.year ? 0.55 : (slot.yearColor !== "" ? 0.42 : 0.22)
            }
            Rectangle {
                visible: slot.isYear
                x: edge.railW + 3
                width: parent.width - edge.railW - 6
                height: 1
                color: slot.populated ? Theme.muted : Theme.faint
                opacity: slot.populated ? 1 : 0.35
            }
            Text {
                visible: slot.isYear && slot.populated && (edge.slots.labelEvery > 0)
                         && (modelData.index % Math.max(1, edge.slots.labelEvery) === 0)
                         && slot.height >= 10
                x: edge.railW + 5
                y: 1
                text: modelData.label
                font.family: Theme.ui
                font.pixelSize: 11
                font.weight: Font.DemiBold
                color: Theme.text
            }
            // Empty years: no detent mark — only the faint rule above.
            Rectangle {
                visible: slot.isYear && slot.populated
                anchors.right: parent.right
                anchors.rightMargin: 6
                anchors.verticalCenter: parent.verticalCenter
                width: 4
                height: Math.max(2, Math.min(4, slot.height - 2))
                radius: 1
                color: Theme.faint
            }
            Text {
                visible: slot.isUndated && slot.height >= 10
                x: edge.railW + 5
                anchors.verticalCenter: parent.verticalCenter
                text: "Undated"
                font.family: Theme.ui
                font.pixelSize: 10
                font.weight: Font.Medium
                color: Theme.muted
            }
        }
    }

    // Focused period's capped representatives for the contextual photo preview.
    // Day > month > year. Never more than four ids — density cannot inflate this.
    function previewSampleIds() {
        function take(cell) {
            if (!cell || !cell.sampleIds)
                return []
            var out = []
            for (var i = 0; i < cell.sampleIds.length && out.length < 4; i++) {
                var id = cell.sampleIds[i]
                if (id && String(id).indexOf("idx:") !== 0)
                    out.push(String(id))
            }
            return out
        }
        if (lensDay !== "") {
            for (var d = 0; d < lensDays.length; d++)
                if (lensDays[d].key === lensDay)
                    return take(lensDays[d])
        }
        if (lensMonth !== "") {
            for (var m = 0; m < lensMonths.length; m++)
                if (lensMonths[m].key === lensMonth)
                    return take(lensMonths[m])
        }
        for (var y = 0; y < yearRibbon.length; y++)
            if (yearRibbon[y].year === lensYear)
                return take(yearRibbon[y])
        return []
    }

    function previewTitle() {
        if (lensDay !== "")
            return lensDay
        if (lensMonth !== "")
            return lensMonth
        if (lensYear >= 0)
            return String(lensYear)
        return ""
    }

    // Local temporal lens + contextual photographic preview.
    // Overlays the hovered year without rescaling the chronological track.
    // Hover never moves the archive; click navigates; drag uses Phase 1.
    Item {
        id: lensPanel
        objectName: "temporalLens"
        visible: edge.lensOpen && edge.lensMonths.length > 0
        z: 8
        readonly property var previewIds: edge.lensOpen ? edge.previewSampleIds() : []
        readonly property real previewH: 72
        readonly property real monthBandH: {
            if (!edge.lensMonths.length)
                return 18
            var natural = Math.max(edge.lensAnchorH, edge.lensMonths.length * 16)
            return Math.max(14, Math.min(28, natural / edge.lensMonths.length))
        }
        readonly property real monthsH: Math.max(edge.lensAnchorH, edge.lensMonths.length * monthBandH)
        width: 168
        height: monthsH + previewH + 10
        // Anchor beside the strip so other years' calendar positions stay put.
        x: -width - 6
        y: {
            var top = edge.lensAnchorY + edge.lensAnchorH / 2 - height / 2
            return Math.max(2, Math.min(edge.height - height - 2, top))
        }

        Rectangle {
            anchors.fill: parent
            radius: Theme.radius
            color: Theme.raised
            border.width: 1
            border.color: Theme.line
            opacity: 0.97
        }

        Column {
            id: lensBody
            anchors.fill: parent
            anchors.margins: 4
            spacing: 4

            // Hybrid magnification: populated months for the hovered year only.
            Column {
                id: monthCol
                width: parent.width
                spacing: 1
                Repeater {
                    model: edge.lensMonths
                    delegate: Item {
                        id: monthRow
                        width: monthCol.width
                        height: lensPanel.monthBandH
                        readonly property bool active: modelData.key === edge.lensMonth
                        readonly property string wash: modelData.color || ""

                        Rectangle {
                            anchors.fill: parent
                            radius: 3
                            color: monthRow.wash !== "" ? monthRow.wash : Theme.amberSoft
                            opacity: monthRow.active ? 0.72 : 0.38
                        }
                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            text: {
                                var k = modelData.key || ""
                                if (k.length >= 7)
                                    return k.substring(5, 7) + " · " + modelData.photoCount
                                return String(modelData.photoCount || "")
                            }
                            font.family: Theme.ui
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                            color: Theme.text
                        }
                        // One mark per populated day inside the active month — never per photo.
                        Row {
                            visible: monthRow.active && edge.lensDays.length > 0 && parent.height >= 16
                            anchors.right: parent.right
                            anchors.rightMargin: 4
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 1
                            Repeater {
                                model: edge.lensDays
                                delegate: Rectangle {
                                    width: 5
                                    height: 10
                                    radius: 1
                                    color: modelData.key === edge.lensDay
                                           ? Theme.amber
                                           : (modelData.color || Theme.faint)
                                    opacity: 0.9
                                }
                            }
                        }
                    }
                }
            }

            // Contextual photographic preview — ≤4 representatives for the focused period.
            Item {
                id: previewPane
                objectName: "ribbonPreview"
                width: parent.width
                height: lensPanel.previewH

                Text {
                    id: previewLabel
                    text: edge.previewTitle()
                    font.family: Theme.ui
                    font.pixelSize: 10
                    font.weight: Font.Medium
                    color: Theme.muted
                    width: parent.width
                    elide: Text.ElideRight
                }
                Row {
                    id: previewRow
                    anchors.top: previewLabel.bottom
                    anchors.topMargin: 4
                    anchors.left: parent.left
                    anchors.right: parent.right
                    spacing: 3
                    Repeater {
                        model: lensPanel.previewIds
                        delegate: Item {
                            width: Math.floor((previewRow.width - 9) / 4)
                            height: Math.max(36, previewPane.height - previewLabel.height - 8)
                            // Hide amber shell until a cache-only frame is Ready —
                            // empty containers are not a loading affordance.
                            visible: thumb.status === Image.Ready
                            Image {
                                id: thumb
                                anchors.fill: parent
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                // Cache-only path: 96 preferred, 384 fallback; never decode.
                                source: modelData ? ("image://archive/cs/" + modelData) : ""
                            }
                            Rectangle {
                                anchors.fill: parent
                                radius: 3
                                color: "transparent"
                                border.width: 1
                                border.color: Theme.amberSoft
                                z: 1
                            }
                        }
                    }
                    // Placeholder tiles when cache has not produced sample ids yet.
                    Repeater {
                        model: Math.max(0, 4 - lensPanel.previewIds.length)
                        delegate: Rectangle {
                            width: Math.floor((previewRow.width - 9) / 4)
                            height: Math.max(36, previewPane.height - previewLabel.height - 8)
                            radius: 3
                            color: Theme.bg
                            border.width: 1
                            border.color: Theme.line
                            opacity: 0.7
                        }
                    }
                }
            }
        }

        // On top of the panel so ribbon ↔ preview moves keep the lens open.
        // Hover still must not move the archive.
        MouseArea {
            id: lensHoverArea
            anchors.fill: parent
            z: 20
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton
            cursorShape: Qt.PointingHandCursor
            onEntered: {
                edge.lensHover = true
                edge.cancelLensLeave()
            }
            onExited: {
                edge.lensHover = false
                edge.scheduleLensLeave()
            }
            onClicked: function (m) {
                edge.capturePressPeriod(edge.lensAnchorY + edge.lensAnchorH / 2)
                if (!edge.navigateToPressPeriod()) {
                    edge.pressPeriodKind = "year"
                    edge.pressPeriodKey = String(edge.lensYear)
                    edge.navigateToPressPeriod()
                }
            }
            onPositionChanged: function (m) {
                if (edge.mode !== "idle")
                    return
                var slot = edge.slotForYear(edge.lensYear)
                if (!slot)
                    return
                // Map panel Y onto the year slot so month/day subdivision stays local.
                var local = Math.max(0, Math.min(1, m.y / Math.max(1, lensPanel.monthsH)))
                edge.updateLensFromHover(slot.y + local * slot.h)
            }
        }
    }

    // Passive viewport segment (frozen only while Armed/Tracking).
    // Dense single-year viewports compress chronologically; keep a readable
    // minimum height and a soft range wash so the marker is not a lost dot.
    Item {
        id: viewportChrome
        anchors.fill: parent
        readonly property real minSegH: 16
        readonly property var seg: (edge.mode === "armed" || edge.mode === "tracking")
                                   ? edge.frozenSegment : edge.viewportSeg
        readonly property var g: (edge.mode === "armed" || edge.mode === "tracking")
                                 ? edge.snapshot : (edge.passiveGeometry || edge.snapshot)
        readonly property real segY: {
            var g = viewportChrome.g
            var s = viewportChrome.seg
            if (!g || !s || s.timeHi === undefined) return edge.innerTop
            var tHi = edge.tForYearFrac(g, s.timeHi)
            var tLo = (s.timeLo === undefined) ? tHi : edge.tForYearFrac(g, s.timeLo)
            var y0 = edge.yForT(tHi)
            var raw = Math.max(0, edge.yForT(tLo) - y0)
            if (raw < viewportChrome.minSegH)
                return Math.max(edge.innerTop, y0 - (viewportChrome.minSegH - raw) / 2)
            return y0
        }
        readonly property real segH: {
            var g = viewportChrome.g
            var s = viewportChrome.seg
            if (!g || !s || s.timeLo === undefined || s.timeHi === undefined)
                return viewportChrome.minSegH
            var raw = edge.yForT(edge.tForYearFrac(g, s.timeLo))
                      - edge.yForT(edge.tForYearFrac(g, s.timeHi))
            return Math.max(viewportChrome.minSegH, raw)
        }

        // Soft wash across the year column — same tokens, no shadow/gradient.
        Rectangle {
            id: rangeWash
            objectName: "viewportRange"
            visible: datedSeg.visible
            x: edge.railW + 2
            width: Math.max(8, edge.width - edge.railW - 5)
            y: viewportChrome.segY
            height: viewportChrome.segH
            radius: 3
            color: Theme.amberSoft
            opacity: edge.mode === "tracking" ? 0.45 : 0.85
        }
        Rectangle {
            id: datedSeg
            objectName: "scrubMarker"
            visible: viewportChrome.seg && (viewportChrome.seg.kind === "dated" || viewportChrome.seg.kind === "mixed")
                     && viewportChrome.g
            x: 1
            width: edge.railW
            radius: 2
            color: Theme.amber
            opacity: edge.mode === "tracking" ? 0.55 : 1
            y: viewportChrome.segY
            height: viewportChrome.segH
        }
        // Short whiskers at the ends of the segment so a short range still reads.
        Rectangle {
            visible: datedSeg.visible
            x: 1
            y: datedSeg.y
            width: edge.railW + 10
            height: 2
            radius: 1
            color: Theme.amber
            opacity: datedSeg.opacity
        }
        Rectangle {
            visible: datedSeg.visible
            x: 1
            y: datedSeg.y + datedSeg.height - 2
            width: edge.railW + 10
            height: 2
            radius: 1
            color: Theme.amber
            opacity: datedSeg.opacity
        }
        Rectangle {
            id: undatedMark
            objectName: "undatedIndicator"
            visible: viewportChrome.seg && (viewportChrome.seg.kind === "undated" || viewportChrome.seg.kind === "mixed")
            x: 1
            width: edge.railW
            height: 12
            radius: 2
            color: Theme.muted
            // Outside the dated track — bottom terminal zone.
            y: edge.undatedZoneTop + Math.max(0, (edge.undatedZoneH - height) / 2)
        }
    }

    // Destination pill — Tracking/Settling when loupe is off. Loupe replaces it when enabled.
    Rectangle {
        id: pill
        objectName: "destinationPill"
        visible: !edge.loupeEnabled
                 && (edge.mode === "tracking" || edge.mode === "settling")
                 && (edge.destinationYear >= 0 || edge.destinationUndated)
                 && pillText.text !== ""
        x: -width - 8
        y: Math.max(4, Math.min(edge.height - height - 4, edge.pointerY - height / 2))
        width: pillText.implicitWidth + 18
        height: pillText.implicitHeight + 10
        radius: Theme.radius
        color: Theme.amber
        Text {
            id: pillText
            anchors.centerIn: parent
            text: edge.destinationUndated ? "Undated" : (edge.destinationYear >= 0 ? String(edge.destinationYear) : "")
            font.family: Theme.ui
            font.pixelSize: Theme.small
            font.weight: Font.DemiBold
            color: Theme.onAmber
        }
        Accessible.name: pillText.text
    }

    // Phase 3 HOVER readout — gutter only; year + count; never thumbnails / jump.
    Rectangle {
        id: hoverReadout
        objectName: "loupeHoverReadout"
        visible: edge.phase3Hover && edge.hoverReadoutYear >= 0
        x: -width - 8
        y: Math.max(4, Math.min(edge.height - height - 4, edge.hoverY - height / 2))
        width: hoverReadoutText.implicitWidth + 16
        height: hoverReadoutText.implicitHeight + 10
        radius: Theme.radius
        color: Theme.raised
        border.width: 1
        border.color: Theme.line
        z: 35
        Text {
            id: hoverReadoutText
            anchors.centerIn: parent
            text: {
                if (edge.hoverReadoutYear < 0)
                    return ""
                if (edge.hoverReadoutCount > 0)
                    return edge.hoverReadoutYear + " · " + edge.hoverReadoutCount
                return String(edge.hoverReadoutYear)
            }
            font.family: Theme.ui
            font.pixelSize: Theme.tiny
            color: Theme.text
        }
        Accessible.name: hoverReadoutText.text
    }

    // Phase 3 loupe — destination feedback during tracking/settling only.
    TemporalLoupe {
        id: temporalLoupe
        objectName: "temporalLoupe"
        visible: edge.loupeVisible
                 && (edge.destinationYear >= 0 || edge.destinationUndated)
        geometry: edge.snapshot
        frozenSegment: edge.frozenSegment
        yearRibbon: edge.yearRibbon
        destinationYear: edge.destinationYear
        destinationUndated: edge.destinationUndated
        pointerYearFrac: edge.pointerYearFrac
        pointerCalendarYear: edge.pointerCalendarYear
        pointerOverEmpty: edge.pointerOverEmpty
        pointerX: edge.pointerX
        pointerY: edge.pointerY
        windowW: edge.parent ? edge.parent.width : 800
        windowH: edge.parent ? edge.parent.height : 600
        reducedMotion: Theme.reducedMotion
    }

    Timer {
        id: accessTick
        interval: 120
        running: edge.visible
        repeat: true
        onTriggered: edge.refreshAccessNote()
    }

    MouseArea {
        id: seek
        objectName: "scrubSeek"
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        // Wheel must not arm the drag state; forward to content scrolling instead.
        onPressed: function (m) {
            edge.forceActiveFocus()
            edge.pointerX = m.x
            edge.hoverX = m.x
            edge.arm(m.y)
        }
        onPositionChanged: function (m) {
            edge.pointerX = m.x
            edge.hoverX = m.x
            edge.hoverY = m.y
            if (pressed) {
                // Pointer may leave the gutter mid-drag — Phase 1 continues; loupe follows.
                edge.track(m.y)
            } else if (edge.mode === "idle") {
                if (edge.loupeEnabled && edge.isGutterX(m.x)) {
                    // Gutter → Phase 3 HOVER only.
                    edge.updateGutterHover(m.x, m.y)
                } else {
                    // Ribbon (or loupe off) → Phase 2 lens; clear gutter first.
                    if (edge.gutterHover)
                        edge.updateGutterHover(-1, -1)
                    edge.updateLensFromHover(m.y)
                }
            }
        }
        onReleased: function (m) {
            edge.pointerX = m.x
            edge.release(m.y)
        }
        onCanceled: edge.abortGesture(true)
        onEntered: edge.cancelLensLeave()
        onExited: {
            if (edge.mode === "idle") {
                edge.hoverY = -1
                edge.hoverX = -1
                edge.updateGutterHover(-1, -1)
                edge.scheduleLensLeave()
            }
            // Mid-drag exit: inherit Phase 1 — drag continues while pressed.
        }
        onWheel: function (wheel) {
            if (!edge.roll || !edge.roll.view)
                return
            // Ordinary content scroll — never enter Armed from wheel.
            var next = edge.roll.clampContentY(edge.roll.view.contentY - wheel.angleDelta.y)
            edge.roll.view.contentY = next
            wheel.accepted = true
        }
    }
}
