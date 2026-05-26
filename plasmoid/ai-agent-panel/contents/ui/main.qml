/*
 * contents/ui/main.qml — Root panel for the AI Agent Plasmoid.
 *
 * Persistent right-side panel that docks into the Plasma desktop.
 * Connects to the Python backend via Plasma5Support.DataSource (executable engine).
 * Passes signals to child components: ChatView, TaskInput, FileTree, StatusBar.
 *
 * Pattern: JARVIS main.qml layout + end4's streaming signal handling
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support

PlasmoidItem {
    id: root

    // ──────────────────────────────────────────────
    // Layout: compact in panel, expanded on desktop
    // ──────────────────────────────────────────────

    // ──────────────────────────────────────────────
    // D-Bus Connection via Plasma5Support.DataSource
    // ──────────────────────────────────────────────
    property var dbusAgent: null
    property bool agentConnected: false
    property string agentStatus: "idle"
    property var chatMessages: []
    property var contextFiles: []

    // Plasma5Support DataSource for executable calls
    Plasma5Support.DataSource {
        id: dbusSource
        engine: "executable"
        onNewData: function(sourceName, data) {
            console.log("[AI Panel] Data received from", sourceName, ":", data)
            if (data.status === "complete") {
                var output = data.output || ""
                if (output.startsWith("STATUS:")) {
                    var statusData = JSON.parse(output.substring(7).trim())
                    agentStatus = statusData.status || "idle"
                    console.log("[AI Panel] Status updated:", agentStatus)
                } else if (output.startsWith("OK:")) {
                    console.log("[AI Panel] Command result:", output)
                }
            } else if (data.status === "error") {
                console.log("[AI Panel] Error:", data.error)
            }
        }
    }

    Component.onCompleted: {
        agentConnected = true
        console.log("[AI Panel] Agent connected via D-Bus helper")
    }

    function runTask(task, files) {
        if (!agentConnected) return false
        var filesJson = JSON.stringify(files || [])
        var cmd = "/usr/bin/python3 /home/neo/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel/contents/ui/dbus_helper.py run_task '" + task + "' '" + filesJson + "'"
        dbusSource.connectSource("python3", cmd)
        console.log("[AI Panel] Running task:", task)
        return true
    }

    function stopTask() {
        if (!agentConnected) return
        var cmd = "/usr/bin/python3 /home/neo/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel/contents/ui/dbus_helper.py stop_task"
        dbusSource.connectSource("python3", cmd)
        console.log("[AI Panel] Stopping task")
    }

    function provideUserResponse(response) {
        if (!agentConnected) return
        var cmd = "/usr/bin/python3 /home/neo/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel/contents/ui/dbus_helper.py provide_response '" + response + "'"
        dbusSource.connectSource("python3", cmd)
        console.log("[AI Panel] Providing response:", response)
    }

    // ──────────────────────────────────────────────
    // Signal Handlers (route to child components)
    // ──────────────────────────────────────────────
    function onStatusChanged(status, data) {
        agentStatus = status
        console.log("[AI Panel] Status:", status)
    }

    function onTokenStream(content, msgType) {
        chatMessages.push({
            type: msgType || "thought",
            content: content,
            timestamp: Date.now()
        })
        chatMessagesChanged()
    }

    function onToolCallStarted(toolName, inputJson, iteration) {
        chatMessages.push({
            type: "tool_call",
            toolName: toolName,
            content: "Calling: " + toolName + "\n" + inputJson,
            iteration: parseInt(iteration) || 0,
            timestamp: Date.now()
        })
        chatMessagesChanged()
    }

    function onToolCallResult(toolName, output, success, error) {
        chatMessages.push({
            type: "tool_result",
            toolName: toolName,
            content: output,
            success: success,
            error: error,
            timestamp: Date.now()
        })
        chatMessagesChanged()
    }

    function onTaskComplete(data) {
        agentStatus = "complete"
        console.log("[AI Panel] Task complete:", data)
    }

    function onErrorOccurred(error) {
        agentStatus = "error"
        chatMessages.push({
            type: "error",
            content: error,
            timestamp: Date.now()
        })
        chatMessagesChanged()
    }

    function onQuestionAsked(question, optionsJson) {
        agentStatus = "waiting_user"
        chatMessages.push({
            type: "question",
            content: question,
            options: JSON.parse(optionsJson || "[]"),
            timestamp: Date.now()
        })
        chatMessagesChanged()
    }

    // ──────────────────────────────────────────────
    // Compact Representation — shown in panel
    // Launches the side panel window
    // ──────────────────────────────────────────────
    compactRepresentation: PlasmaComponents.Button {
        icon.name: "assistant"
        text: "AI Agent"
        onClicked: {
            // Launch side panel window via D-Bus helper
            var cmd = "/usr/bin/python3 " + plasmoid.file("ui", "dbus_helper.py") + " launch_panel"
            dbusSource.connectSource("python3", cmd)
        }

        PlasmaCore.ToolTipArea {
            anchors.fill: parent
            mainText: "AI Agent Panel"
            subText: "Status: " + root.agentStatus
        }
    }

    // ──────────────────────────────────────────────
    // Full Representation — the full side panel
    // ──────────────────────────────────────────────
    fullRepresentation: Kirigami.Page {
        title: "AI Agent"

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Chat View (scrollable, takes most space) ──
            ChatView {
                id: chatView
                Layout.fillWidth: true
                Layout.fillHeight: true
                messages: root.chatMessages
            }

            Kirigami.Separator {
                Layout.fillWidth: true
            }

            // ── Context File Chips ──
            Flow {
                id: contextChips
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing
                visible: root.contextFiles.length > 0

                Repeater {
                    model: root.contextFiles
                    delegate: PlasmaComponents.ToolButton {
                        text: modelData
                        icon.name: "text-plain"
                        display: PlasmaComponents.ToolButton.TextBesideIcon
                        onClicked: {
                            root.contextFiles = root.contextFiles.filter(function(f) { return f !== modelData })
                            root.contextFilesChanged()
                        }
                    }
                }
            }

            // ── Task Input ──
            TaskInput {
                id: taskInput
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing

                onSendTask: function(task) {
                    if (root.agentConnected) {
                        root.runTask(task, root.contextFiles)
                        taskInput.clear()
                    }
                }

                onAddFile: function(filePath) {
                    if (root.contextFiles.indexOf(filePath) === -1) {
                        root.contextFiles.push(filePath)
                        root.contextFilesChanged()
                    }
                }

                enabled: root.agentStatus !== "thinking" && root.agentStatus !== "executing"
            }

            Kirigami.Separator {
                Layout.fillWidth: true
            }

            // ── Status Bar ──
            StatusBar {
                id: statusBar
                Layout.fillWidth: true
                agentStatus: root.agentStatus
                agentConnected: root.agentConnected

                onRunClicked: root.runTask(taskInput.text, root.contextFiles)
                onStopClicked: root.stopTask()
                onClearClicked: {
                    root.chatMessages = []
                    root.chatMessagesChanged()
                }
                onToggleFileTree: fileTreeDrawer.open()
            }
        }

        // ── File Tree Drawer ──
        Kirigami.OverlayDrawer {
            id: fileTreeDrawer
            edge: Qt.RightEdge
            width: Kirigami.Units.gridUnit * 14
            height: parent.height

            FileTree {
                id: fileTree
                anchors.fill: parent
                workingDir: plasmoid.configuration.workingDir || "~"

                onFileSelected: function(filePath) {
                    taskInput.addFileContext(filePath)
                }

                onFilesSelected: function(filePaths) {
                    for (var i = 0; i < filePaths.length; i++) {
                        if (root.contextFiles.indexOf(filePaths[i]) === -1) {
                            root.contextFiles.push(filePaths[i])
                        }
                    }
                    root.contextFilesChanged()
                    fileTreeDrawer.close()
                }
            }
        }
    }
}
