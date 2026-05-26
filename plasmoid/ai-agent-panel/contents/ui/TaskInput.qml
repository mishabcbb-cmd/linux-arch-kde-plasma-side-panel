/*
 * contents/ui/TaskInput.qml — Multi-line task input with context file chips.
 *
 * Features:
 *   • Multi-line text input — send on Ctrl+Enter
 *   • Context file chips shown below input
 *   • Add file button to open FileTree picker
 *   • Disabled state when agent is busy
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents

ColumnLayout {
    id: taskInputRoot
    spacing: Kirigami.Units.smallSpacing

    property alias text: inputField.text
    property alias placeholderText: inputField.placeholderText
    property var contextFiles: []
    signal sendTask(string task)
    signal addFile(string filePath)
    signal removeFile(string filePath)

    // ── Input row: text area + send button ──
    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        PlasmaComponents.TextArea {
            id: inputField
            Layout.fillWidth: true
            Layout.minimumHeight: Kirigami.Units.gridUnit * 3
            Layout.maximumHeight: Kirigami.Units.gridUnit * 8
            placeholderText: "Describe your task... (Ctrl+Enter to send)"
            wrapMode: TextInput.Wrap
            selectByMouse: true

            // Ctrl+Enter to send
            Keys.onPressed: function(event) {
                if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter)
                    && (event.modifiers & Qt.ControlModifier)) {
                    event.accepted = true
                    if (inputField.text.trim() !== "") {
                        taskInputRoot.sendTask(inputField.text.trim())
                    }
                }
            }

            background: Rectangle {
                color: Kirigami.Theme.backgroundColor
                border.color: Kirigami.Theme.highlightColor
                border.width: inputField.activeFocus ? 1 : 0.5
                radius: Kirigami.Units.smallSpacing
            }
        }

        ColumnLayout {
            spacing: 2

            // Send button
            PlasmaComponents.Button {
                icon.name: "media-playback-start"
                text: "Send"
                display: PlasmaComponents.Button.IconOnly
                enabled: inputField.text.trim() !== ""
                onClicked: {
                    if (inputField.text.trim() !== "") {
                        taskInputRoot.sendTask(inputField.text.trim())
                    }
                }

                PlasmaComponents.ToolTip {
                    text: "Send Task (Ctrl+Enter)"
                }
            }

            // Add file button
            PlasmaComponents.Button {
                icon.name: "document-open"
                text: "File"
                display: PlasmaComponents.Button.IconOnly
                onClicked: taskInputRoot.openFilePicker()

                PlasmaComponents.ToolTip {
                    text: "Add Context File"
                }
            }
        }
    }

    // ── Context file chips ──
    Flow {
        Layout.fillWidth: true
        spacing: 4
        visible: contextFiles.length > 0

        Repeater {
            model: contextFiles
            delegate: PlasmaComponents.ToolButton {
                text: modelData.split('/').pop() || modelData
                icon.name: "text-plain"
                display: PlasmaComponents.ToolButton.TextBesideIcon
                flat: true

                onClicked: taskInputRoot.removeFile(modelData)

                PlasmaComponents.ToolTip {
                    text: "Remove: " + modelData
                }
            }
        }
    }

    // ── File picker dialog ──
    // Plasma-compatible file dialog (replaces QtQuick.Dialogs FileDialog)
    function openFilePicker() {
        var engine = dbusSource
        if (!engine) return
        var args = ["python3", "/home/neo/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel/contents/ui/dbus_helper.py", "pick_file"]
        dbusSource.connectToEventSource("python3", args)
    }

    // ── Public functions ──
    function clear() {
        inputField.text = ""
    }

    function addFileContext(filePath) {
        taskInputRoot.addFile(filePath)
    }

    function removeFileContext(filePath) {
        taskInputRoot.removeFile(filePath)
    }

    function focus() {
        inputField.forceActiveFocus()
    }
}
