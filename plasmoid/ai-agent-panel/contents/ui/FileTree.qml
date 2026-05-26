/*
 * contents/ui/FileTree.qml — File context picker with tree browser.
 *
 * Shows the project directory tree with checkboxes for selecting
 * context files. Selected files are emitted via fileSelected signal.
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents

ColumnLayout {
    id: fileTreeRoot
    spacing: 0

    property string workingDir: ""
    property var selectedFiles: []
    signal fileSelected(string filePath)

    // ── Header ──
    Kirigami.Heading {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        level: 3
        text: "Context Files"
    }

    Kirigami.Separator {
        Layout.fillWidth: true
    }

    // ── Search field ──
    PlasmaComponents.TextField {
        id: searchField
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        placeholderText: "Filter files..."
        clearButtonShown: true
    }

    // ── File tree ──
    ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true

        ListView {
            id: fileListView
            anchors.fill: parent

            model: ListModel {
                id: fileModel
            }

            delegate: ItemDelegate {
                width: fileListView.width
                height: Kirigami.Units.gridUnit * 1.5

                contentItem: RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    Kirigami.Icon {
                        source: model.isDir ? "folder" : "text-plain"
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: Kirigami.Units.iconSizes.small
                    }

                    Label {
                        Layout.fillWidth: true
                        text: model.name
                        elide: Text.ElideLeft
                    }
                }

                onClicked: {
                    if (!model.isDir) {
                        fileTreeRoot.fileSelected(model.path)
                    }
                }
            }
        }
    }

    // ── Quick paths ──
    Kirigami.Separator {
        Layout.fillWidth: true
    }

    Flow {
        Layout.fillWidth: true
        Layout.margins: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing

        Repeater {
            model: [
                { name: "~/", path: "" },
                { name: "src/", path: "src" },
                { name: "tests/", path: "tests" },
                { name: "config/", path: "config" },
            ]
            delegate: PlasmaComponents.ToolButton {
                text: modelData.name
                flat: true
                onClicked: {
                    // Would navigate to directory
                }
            }
        }
    }

    // ── Load directory contents ──
    function loadDirectory(dirPath) {
        fileModel.clear()
        // This would use a C++ model or FilesystemModel in production
        // For now, placeholder
    }

    Component.onCompleted: {
        loadDirectory(workingDir || "~")
    }
}
