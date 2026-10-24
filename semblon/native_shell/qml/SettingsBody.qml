import QtQuick

// Everything adjustable, in plain words. Scrolls when the window is small.
Flickable {
    id: body
    clip: true
    contentWidth: width
    contentHeight: col.implicitHeight + 12
    boundsBehavior: Flickable.StopAtBounds

    function spoken(row) {
        var id = row ? String(row.itemId || row.id || "") : ""
        var known = {
            "region_pack": ["Finding a similar look", "The extra that matches a detail you point at is not on this computer yet. Colour matching still works."],
            "object_pack": ["Things in pictures", "Semblon cannot name things in pictures until this extra is added. It never decides who someone is."],
            "vlm_local": ["Describing a picture", "A local description is not ready. Semblon will not download it on its own."],
            "ocr": ["Words in pictures", "Reading words inside pictures is not ready on this computer."],
            "clip": ["A broader sense of the picture", "This optional extra is not added. Semblon will not fetch it by itself."],
            "face_pack": ["Recognising faces", "The files used to notice faces are not on this computer yet. Semblon does not download them. Naming someone stays your decision."],
            "opencv_load": ["Reading pictures", "Semblon could not open its picture reader on this computer."],
            "architecture": ["This computer", "Semblon is not running the build made for this computer, so some work may be slower."],
            "authenticode": ["A signed installer", "This copy is not signed. That does not change the pictures already here."],
            "model_licence": ["Permission to include extras", "Some extras stay ones you add yourself."],
            "preflight": ["Setup check", "The check could not finish. Your pictures were not changed."]
        }
        if (known[id])
            return { title: known[id][0], body: known[id][1] }
        return { title: row && row.name ? String(row.name) : "Something extra", body: row && row.detail ? String(row.detail) : "" }
    }

    component Label: Text {
        width: col.width
        wrapMode: Text.WordWrap
        font.family: Theme.ui
        font.pixelSize: Theme.small
        color: Theme.muted
    }
    component Heading: Text {
        font.family: Theme.display
        font.pixelSize: Theme.lead
        color: Theme.text
        topPadding: 6
    }

    Column {
        id: col
        width: body.width - 12
        spacing: Theme.gap

        Heading { text: "Look" }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { label: "Darkroom"; selected: !shell.lightPalette; onActivated: shell.setAtmosphere("mica_dark") }
            Tool { label: "Daylight"; selected: shell.lightPalette; onActivated: shell.setAtmosphere("light") }
        }

        Heading { text: "Your photos" }
        Label { text: shell.archiveSummary }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { label: "Add a folder"; onActivated: shell.addFolder() }
            Tool { label: "Check for new photos"; onActivated: shell.rescanFolder() }
            Tool { label: "Check everything is in place"; onActivated: shell.libraryHealth() }
            Tool { label: "Recent activity"; onActivated: shell.showActivity() }
            Tool { label: "Things you have named"; onActivated: shell.openNamedItems() }
        }
        Label { visible: shell.resultText !== ""; text: shell.resultText; color: Theme.text }

        Heading { text: "How much detail to show" }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { objectName: "primaryModeButton"; label: "Everyday"; selected: shell.mode === "primary"; onActivated: shell.setMode("primary") }
            Tool { objectName: "advancedModeButton"; label: "More detail"; selected: shell.mode === "advanced"; onActivated: shell.setMode("advanced") }
        }

        Heading { text: "How hard to look" }
        Label { text: "Search quality is " + shell.searchQualityLabel + "." }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { label: "Quick"; selected: shell.searchQuality === "fast"; onActivated: shell.setSearchQuality("fast") }
            Tool { label: "Balanced"; selected: shell.searchQuality === "balanced"; onActivated: shell.setSearchQuality("balanced") }
            Tool { label: "Thorough"; selected: shell.searchQuality === "max"; onActivated: shell.setSearchQuality("max") }
        }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { label: "Use the graphics chip"; onActivated: shell.setGpuPreference("auto") }
            Tool { label: "Do not use it"; onActivated: shell.setGpuPreference("off") }
        }

        Heading { text: "Extras" }
        Repeater {
            objectName: "preflightRepeater"
            model: shell.preflightRows
            delegate: Column {
                width: col.width
                spacing: 4
                readonly property var words: body.spoken(modelData)
                Text { width: parent.width; wrapMode: Text.WordWrap; text: words.title; font.family: Theme.ui; font.pixelSize: Theme.body; font.weight: Font.Medium; color: Theme.text }
                Label { text: words.body }
                Tool { objectName: "preflightInstall"; label: "Add"; visible: modelData.installable === true; onActivated: shell.installPreflight(modelData.itemId) }
            }
        }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { label: "Add face files you downloaded"; onActivated: shell.chooseKnowledgePack() }
            Tool { label: "Add an extra you downloaded"; onActivated: shell.chooseModelInstall() }
        }

        Heading { text: "Starting over" }
        Label { text: "Your photo files are never touched by either button." }
        Flow {
            width: parent.width; spacing: Theme.gap
            Tool { label: "Reset settings"; onActivated: shell.resetDefaults() }
            Tool { label: "Forget what Semblon learned"; onActivated: shell.clearLibrary() }
        }
    }
}
