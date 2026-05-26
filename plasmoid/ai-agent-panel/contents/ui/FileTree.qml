/*
 * contents/ui/FileTree.qml — Real file browser with directory tree.
 *
 * Uses Plasma5Support.DataSource (executable engine) to call
 * filetree_helper.py for directory listings. Supports:
 *   • Directory tree navigation (click to enter, back button)
 *   • File selection for agent context
 *   • Filter/search by filename
 *   • Breadcrumb navigation
 *   • Sorting: folders first, then files alphabetically
 *
 * Pattern: Plasma5Support.DataSource executable engine (same as main.qml)
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as Plasma5Support

ColumnLayout {
    id: fileTreeRoot
    spacing: 0

    property string workingDir: plasmoid ? plasmoid.configuration.workingDir || "~" : "~"
    property string currentDir: workingDir
    property var selectedFiles: []
    property var history: []
    property string filterText: ""

    signal fileSelected(string filePath)
    signal filesSelected(var filePaths)

    // ── DataSource for directory listing ──
    Plasma5Support.DataSource {
        id: dirSource
        engine: "executable"
        onNewData: function(sourceName, data) {
            if (data.status === "complete") {
                var output = data.output || ""
                try {
                    var result = JSON.parse(output)
                    if (result.error) {
                        console.warn("[FileTree] Error:", result.error)
                        return
                    }
                    fileTreeModel.clear()
                    for (var i = 0; i < result.items.length; i++) {
                        var item = result.items[i]
                        fileTreeModel.append({
                            name: item.name,
                            path: item.path,
                            isDir: item.isDir,
                            isLink: item.isLink,
                            size: item.size,
                            mtime: item.mtime,
                            checked: false
                        })
                    }
                    currentDir = result.realPath || result.path
                    updateBreadcrumb(result.realPath || result.path)
                    loadingIndicator.visible = false
                } catch (e) {
                    console.warn("[FileTree] Parse error:", e)
                }
            } else if (data.status === "error") {
                console.warn("[FileTree] Error:", data.error)
                loadingIndicator.visible = false
            }
        }
    }

    // ── Breadcrumb model ──
    ListModel { id: breadcrumbModel }

    function updateBreadcrumb(path) {
        breadcrumbModel.clear()
        var parts = path.split("/")
        var accumulated = ""
        for (var i = 0; i < parts.length; i++) {
            if (parts[i] === "") continue
            accumulated += "/" + parts[i]
            breadcrumbModel.append({
                label: parts[i],
                fullPath: accumulated
            })
        }
    }

    // ── File model ──
    ListModel { id: fileTreeModel }

    // ── Visible (filtered) model ──
    ListModel { id: visibleModel; dynamicRoles: true }

    function rebuildVisibleModel() {
        visibleModel.clear()
        var folders = []
        var files = []
        for (var i = 0; i < fileTreeModel.count; i++) {
            var item = fileTreeModel.get(i)
            if (filterText !== "" && item.name.toLowerCase().indexOf(filterText) === -1) continue
            var entry = {
                name: item.name,
                path: item.path,
                isDir: item.isDir,
                isLink: item.isLink,
                size: item.size,
                mtime: item.mtime,
                checked: item.checked,
                sourceIndex: i
            }
            if (item.isDir) folders.push(entry)
            else files.push(entry)
        }
        for (var f = 0; f < folders.length; f++) visibleModel.append(folders[f])
        for (var g = 0; g < files.length; g++) visibleModel.append(files[g])
    }

    onFilterTextChanged: rebuildVisibleModel()

    Connections {
        target: fileTreeModel
        onRowsInserted: rebuildVisibleModel()
        onRowsRemoved: rebuildVisibleModel()
        onModelReset: rebuildVisibleModel()
        onDataChanged: rebuildVisibleModel()
    }

    // ── Load directory ──
    function loadDirectory(dirPath) {
        if (!dirPath || dirPath === "") return
        loadingIndicator.visible = true
        var cmd = "/usr/bin/python3 " + plasmoid.file("ui", "filetree_helper.py") + " list '" + dirPath + "'"
        dirSource.connectSource("python3", cmd)
    }

    // ── Navigate into directory ──
    function enterDir(dirPath) {
        history.push(currentDir)
        loadDirectory(dirPath)
    }

    // ── Navigate back ──
    function goBack() {
        if (history.length > 0) {
            var prev = history.pop()
            loadDirectory(prev)
        }
    }

    // ── Navigate to breadcrumb ──
    function navigateTo(path) {
        history = []
        loadDirectory(path)
    }

    // ── Toggle file selection ──
    function toggleFile(sourceIndex) {
        var item = fileTreeModel.get(sourceIndex)
        item.checked = !item.checked
        fileTreeModel.set(sourceIndex, { checked: item.checked })
        if (item.checked) {
            if (selectedFiles.indexOf(item.path) === -1) {
                selectedFiles.push(item.path)
            }
        } else {
            selectedFiles = selectedFiles.filter(function(f) { return f !== item.path })
        }
        selectedFilesChanged()
    }

    // ════════════════════════════════════════════
    // UI
    // ════════════════════════════════════════════

    // ── Header with title and navigation ──
    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing

        PlasmaComponents.ToolButton {
            icon.name: "go-previous"
            enabled: fileTreeRoot.history.length > 0
            onClicked: fileTreeRoot.goBack()

            PlasmaComponents.ToolTip {
                text: "Go Back"
            }
        }

        PlasmaComponents.ToolButton {
            icon.name: "go-home"
            onClicked: fileTreeRoot.navigateTo(fileTreeRoot.workingDir)

            PlasmaComponents.ToolTip {
                text: "Home: " + fileTreeRoot.workingDir
            }
        }

        Kirigami.Heading {
            Layout.fillWidth: true
            level: 3
            text: "Context Files"
            elide: Text.ElideRight
        }

        PlasmaComponents.ToolButton {
            icon.name: "dialog-close"
            onClicked: {
                if (typeof fileTreeDrawer !== 'undefined') {
                    fileTreeDrawer.close()
                }
            }

            PlasmaComponents.ToolTip {
                text: "Close"
            }
        }
    }

    // ── Breadcrumb bar ──
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.smallSpacing
        Layout.rightMargin: Kirigami.Units.smallSpacing
        spacing: 2
        visible: breadcrumbModel.count > 0

        Repeater {
            model: breadcrumbModel
            delegate: RowLayout {
                spacing: 2

                PlasmaComponents.ToolButton {
                    text: model.label
                    flat: true
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    implicitHeight: Kirigami.Units.gridUnit * 1.5
                    onClicked: fileTreeRoot.navigateTo(model.fullPath)
                }

                Label {
                    text: "›"
                    color: Kirigami.Theme.disabledTextColor
                    visible: index < breadcrumbModel.count - 1
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }
        }
    }

    Kirigami.Separator {
        Layout.fillWidth: true
    }

    // ── Search / filter field ──
    PlasmaComponents.TextField {
        id: searchField
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        placeholderText: "Filter files..."
        clearButtonShown: true
        onTextChanged: fileTreeRoot.filterText = text.toLowerCase()
    }

    // ── Loading indicator ──
    PlasmaComponents.BusyIndicator {
        id: loadingIndicator
        Layout.alignment: Qt.AlignHCenter
        visible: false
        running: visible
    }

    // ── File list ──
    PlasmaExtras.ScrollArea {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true

        ListView {
            id: fileListView
            anchors.fill: parent
            model: visibleModel
            currentIndex: -1
            boundsBehavior: Flickable.StopAtBounds

            delegate: ItemDelegate {
                id: fileDelegate
                width: fileListView.width
                height: Kirigami.Units.gridUnit * 2
                highlighted: false

                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    // Checkbox for selection
                    PlasmaComponents.CheckBox {
                        id: fileCheckbox
                        checked: model.checked
                        visible: !model.isDir
                        Layout.alignment: Qt.AlignVCenter
                        onCheckedChanged: {
                            fileTreeRoot.toggleFile(model.sourceIndex)
                        }
                    }

                    // Icon
                    Kirigami.Icon {
                        source: {
                            if (model.isLink) return "emblem-symbolic-link"
                            if (model.isDir) return "folder"
                            var ext = model.name.split('.').pop().toLowerCase()
                            switch (ext) {
                                case "qml": return "text-x-qml"
                                case "py": return "text-x-python"
                                case "js": return "text-x-javascript"
                                case "ts": return "text-x-typescript"
                                case "json": return "text-x-json"
                                case "md": return "text-x-markdown"
                                case "cpp": case "cxx": case "cc": return "text-x-cpp"
                                case "h": case "hpp": return "text-x-header"
                                case "go": return "text-x-go"
                                case "rust": case "rs": return "text-x-rust"
                                case "sh": return "text-x-shellscript"
                                case "yaml": case "yml": return "text-x-yaml"
                                case "toml": return "text-x-toml"
                                case "cmake": return "text-x-cmake"
                                case "xml": return "text-x-xml"
                                case "svg": return "image-x-svg"
                                case "png": case "jpg": case "jpeg": case "gif": return "image-x-generic"
                                default: return "text-plain"
                            }
                        }
                        implicitWidth: Kirigami.Units.iconSizes.smallMedium
                        implicitHeight: Kirigami.Units.iconSizes.smallMedium
                        color: model.isLink ? Kirigami.Theme.linkColor : Kirigami.Theme.textColor
                    }

                    // Filename
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Label {
                            Layout.fillWidth: true
                            text: model.name
                            elide: Text.ElideLeft
                            font.bold: model.isDir
                            color: {
                                if (model.isLink) return Kirigami.Theme.linkColor
                                return Kirigami.Theme.textColor
                            }
                        }

                        // File details (size + date)
                        Label {
                            Layout.fillWidth: true
                            visible: !model.isDir
                            text: {
                                var sizeStr = ""
                                var size = model.size
                                if (size < 1024) sizeStr = size + " B"
                                else if (size < 1048576) sizeStr = (size / 1024).toFixed(1) + " KB"
                                else sizeStr = (size / 1048576).toFixed(1) + " MB"

                                var date = new Date(model.mtime * 1000)
                                var dateStr = date.toLocaleDateString(Qt.locale(), Locale.ShortFormat)
                                return sizeStr + "  •  " + dateStr
                            }
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            color: Kirigami.Theme.disabledTextColor
                        }
                    }

                    // Arrow indicator for directories
                    Kirigami.Icon {
                        source: "go-next"
                        visible: model.isDir
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: Kirigami.Units.iconSizes.small
                        color: Kirigami.Theme.disabledTextColor
                    }
                }

                onClicked: {
                    if (model.isDir) {
                        fileTreeRoot.enterDir(model.path)
                    } else {
                        fileTreeRoot.fileSelected(model.path)
                    }
                }

                // Double-click to select file
                onDoubleClicked: {
                    if (!model.isDir) {
                        fileTreeRoot.toggleFile(model.sourceIndex)
                    }
                }

                background: Rectangle {
                    color: {
                        if (fileDelegate.down) return Kirigami.Theme.highlightColor
                        if (model.checked) return Qt.rgba(0.24, 0.68, 0.91, 0.1)
                        if (fileDelegate.hovered) return Kirigami.Theme.hoverColor
                        return "transparent"
                    }
                    radius: Kirigami.Units.smallSpacing / 2
                }
            }

            // ── Empty state ──
            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: fileListView.count === 0 && !loadingIndicator.visible
                text: "No files"
                explanation: "The directory is empty or inaccessible."
                icon.name: "folder"
            }
        }
    }

    // ── Bottom bar: selected count + add button ──
    Kirigami.Separator {
        Layout.fillWidth: true
    }

    RowLayout {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing

        Label {
            text: selectedFiles.length === 0
                ? "Select files for context"
                : selectedFiles.length + " file(s) selected"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: Kirigami.Theme.disabledTextColor
            Layout.fillWidth: true
        }

        PlasmaComponents.Button {
            text: "Add Selected"
            icon.name: "list-add"
            enabled: selectedFiles.length > 0
            onClicked: {
                fileTreeRoot.filesSelected(selectedFiles)
                if (typeof fileTreeDrawer !== 'undefined') {
                    fileTreeDrawer.close()
                }
            }
        }
    }

    Component.onCompleted: {
        loadDirectory(currentDir)
    }
}
