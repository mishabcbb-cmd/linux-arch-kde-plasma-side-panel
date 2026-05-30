/*
 * SidePanelWindow.qml — Standalone side panel window for KDE AI Agent.
 *
 * Architecture (Plasma 6 + Wayland):
 *   • LayerShellQt::Window as an ATTACHED type (NOT a child component)
 *   • Opacity-based slide animation (x animation doesn't work on Wayland)
 *   • D-Bus signal listener via Plasma5Support.DataSource (executable engine
 *     running dbus_listener.py as subprocess — D-Bus engine was removed in Plasma 6)
 *   • Auto-show on mouse hover in top-left corner (ydotool for Wayland)
 *   • PlasmaCore.Theme integration for proper Breeze theming
 *
 * Pattern: AppGrid GridWindow — Window inside Plasma QML engine,
 * avoiding Wayland GLib re-entrancy issues from separate PyQt6 processes.
 *
 * D-Bus integration:
 *   • dbusListener — runs dbus_listener.py, parses JSON lines from D-Bus signals
 *   • dbusCall — runs dbus_helper.py for method calls (RunTask, StopTask, GetStatus)
 *   • Signals: StatusChanged, TokenStream, ToolCallStarted, ToolCallResult,
 *     TaskComplete, ErrorOccurred, QuestionAsked
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as Plasma5Support

Window {
    id: root

    // ── Properties ──
    property string agentStatus: "idle"
    property var chatMessages: []
    property var contextFiles: []
    property bool agentConnected: false

    signal closeRequested()

    readonly property int panelWidth: Kirigami.Units.gridUnit * 24  // ~380px

    // ── Window setup ──
    width: panelWidth
    height: Screen.height
    visible: false
    color: PlasmaCore.Theme.backgroundColor
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
    title: "AI Agent Panel"

    // ── LayerShell configuration via C++ plugin ──
    // Plasmoid.configureWindow() is called from main.qml after window creation.
    // The C++ plugin (AiAgentPlugin) sets up LayerShellQt for Wayland.

    // ── Slide animation (opacity-based — x animation doesn't work on Wayland) ──
    property bool panelVisible: false

    Behavior on opacity {
        NumberAnimation {
            duration: 200
            easing.type: Easing.OutCubic
        }
    }

    // ── Hide completely when opacity animation finishes ──
    onOpacityChanged: {
        if (opacity <= 0.0 && !panelVisible) {
            visible = false
        }
    }

    function showPanel() {
        panelVisible = true
        visible = true
        opacity = 1.0
        requestActivate()
        dbusListener.start()
        refreshStatus()
    }

    function hidePanel() {
        panelVisible = false
        opacity = 0.0
        dbusListener.stop()
    }

    // ── Close on Escape ──
    Shortcut {
        sequence: "Escape"
        enabled: root.visible
        onActivated: root.closeRequested()
    }

    // ── Close on focus loss (with guard) ──
    property bool closeOnDeactivate: false
    Timer {
        id: deactivateGuard
        interval: 100
        onTriggered: closeOnDeactivate = true
    }

    onActiveChanged: {
        if (!active && visible && closeOnDeactivate && panelVisible) {
            root.closeRequested()
        }
    }

    onPanelVisibleChanged: {
        if (panelVisible) {
            closeOnDeactivate = false
            deactivateGuard.start()
        }
    }

    // ── Auto-show: mouse hover in top-left corner ──
    // Uses ydotool (Wayland-compatible) instead of xdotool (X11 only)
    Timer {
        id: autoShowTimer
        interval: 300
        running: !panelVisible
        repeat: true
        onTriggered: {
            if (panelVisible) return
            cursorSource.connectSource("python3", [
                "-c",
                "import subprocess; out=subprocess.check_output(['ydotool','getmouselocation'],timeout=1).decode(); parts={}; [parts.update({k:v}) for p in out.split() if ':' in p for k,v in [p.split(':',1)]]; print(f\"{parts.get('x','-1')},{parts.get('y','-1')}\")"
            ])
        }
    }

    // ── Cursor position source ──
    Plasma5Support.DataSource {
        id: cursorSource
        engine: "executable"
        onNewData: function(sourceName, data) {
            if (data.status === "complete") {
                var output = (data.output || "").trim()
                var parts = output.split(",")
                if (parts.length === 2) {
                    var cx = parseInt(parts[0])
                    var cy = parseInt(parts[1])
                    if (!isNaN(cx) && !isNaN(cy)) {
                        if (cx >= 0 && cx <= 50 && cy >= 0 && cy <= 50) {
                            if (!panelVisible) showPanel()
                        }
                    }
                }
            }
        }
    }

    // ── D-Bus Signal Listener (runs dbus_listener.py as subprocess) ──
    // Uses the "executable" engine since Plasma 6 removed the D-Bus engine
    // from Plasma5Support.DataSource. The listener writes JSON lines to stdout.
    Plasma5Support.DataSource {
        id: dbusListener
        engine: "executable"

        property string scriptPath: ""

        function start() {
            if (scriptPath === "") {
                var path = Qt.resolvedUrl("dbus_listener.py")
                if (path.toString().startsWith("file://")) {
                    path = path.toString().substring(7)
                }
                scriptPath = path
            }
            connectSource("python3", [scriptPath])
        }

        function stop() {
            disconnectSource("python3")
        }

        onNewData: function(sourceName, data) {
            // The executable engine sends "running" status with partial output
            // as the subprocess writes to stdout, and "complete" when it exits.
            var output = data.output || ""

            if (data.status === "running" || data.status === "complete") {
                var lines = output.split("\n")
                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i].trim()
                    if (line === "") continue
                    try {
                        var msg = JSON.parse(line)
                        handleDbusSignal(msg)
                    } catch(e) {
                        // Skip non-JSON lines (e.g. debug output)
                    }
                }
            }

            // Restart listener if it exited but panel is still visible
            if (data.status === "complete" && panelVisible) {
                dbusListener.start()
            }
        }
    }

    // ── D-Bus Method Call (via dbus_helper.py) ──
    // Method calls use the executable engine since they're one-shot.
    Plasma5Support.DataSource {
        id: dbusCall
        engine: "executable"
        onNewData: function(sourceName, data) {
            if (data.status === "complete") {
                var output = (data.output || "").trim()
                if (output.startsWith("STATUS:")) {
                    try {
                        var statusData = JSON.parse(output.substring(7).trim())
                        agentStatus = statusData.status || "idle"
                    } catch(e) {}
                } else if (output.startsWith("OK:")) {
                    // Method call succeeded
                } else if (output.startsWith("ERROR:")) {
                    chatMessages.push({
                        type: "error",
                        content: output.substring(6).trim()
                    })
                    chatMessagesChanged()
                }
            }
        }
    }

    // ── D-Bus Signal Router ──
    function handleDbusSignal(msg) {
        var signalType = msg.signal || ""
        agentConnected = true

        switch (signalType) {
            case "_listener_started":
                refreshStatus()
                break

            case "StatusChanged":
                agentStatus = msg.status || "idle"
                break

            case "TokenStream":
                appendToken(msg.content || "", msg.msg_type || "thought")
                break

            case "ToolCallStarted":
                chatMessages.push({
                    type: "tool_call",
                    toolName: msg.tool_name || "Tool",
                    content: typeof msg.input === "string"
                        ? msg.input
                        : JSON.stringify(msg.input || {}, null, 2),
                    iteration: msg.iteration || "0",
                })
                chatMessagesChanged()
                agentStatus = "executing"
                break

            case "ToolCallResult":
                chatMessages.push({
                    type: "tool_result",
                    toolName: msg.tool_name || "Tool",
                    content: (msg.output || "").substring(0, 2000),
                    success: msg.success !== false,
                })
                chatMessagesChanged()
                break

            case "TaskComplete":
                chatMessages.push({
                    type: "task_complete",
                    content: "✅ Task complete",
                })
                chatMessagesChanged()
                agentStatus = "idle"
                break

            case "ErrorOccurred":
                chatMessages.push({
                    type: "error",
                    content: msg.error || "Unknown error",
                })
                chatMessagesChanged()
                agentStatus = "error"
                break

            case "QuestionAsked":
                chatMessages.push({
                    type: "question",
                    content: msg.question || "",
                    options: typeof msg.options === "string"
                        ? JSON.parse(msg.options || "[]")
                        : (msg.options || []),
                })
                chatMessagesChanged()
                agentStatus = "waiting_user"
                break

            case "_service_stopped":
                agentConnected = false
                agentStatus = "error"
                break

            case "_service_started":
                agentConnected = true
                refreshStatus()
                break
        }
    }

    // ── Streaming token append (pattern: end4 Ai.qml) ──
    function appendToken(content, msgType) {
        var last = chatMessages.length > 0 ? chatMessages[chatMessages.length - 1] : null
        if (last && last.type === msgType && last._streaming) {
            last.content += content
            chatMessagesChanged()
        } else {
            chatMessages.push({
                type: msgType,
                content: content,
                _streaming: true,
            })
            chatMessagesChanged()
        }
        agentStatus = "thinking"
    }

    // ── D-Bus helper path ──
    function dbusHelperPath() {
        var path = Qt.resolvedUrl("dbus_helper.py")
        if (path.toString().startsWith("file://")) {
            path = path.toString().substring(7)
        }
        return path
    }

    // ── Refresh agent status via D-Bus ──
    function refreshStatus() {
        dbusCall.connectSource("python3", [dbusHelperPath(), "get_status"])
    }

    // ── Send task to agent via D-Bus ──
    function sendTask(taskText) {
        if (!taskText || taskText.trim() === "") return

        chatMessages.push({
            type: "thought",
            content: "🧑 You: " + taskText,
        })
        chatMessagesChanged()

        var safeTask = taskText.replace(/'/g, "'\\''")
        var filesJson = JSON.stringify(contextFiles)

        dbusCall.connectSource("python3", [
            dbusHelperPath(), "run_task", safeTask, filesJson
        ])

        agentStatus = "thinking"
    }

    // ── Stop task via D-Bus ──
    function stopTask() {
        dbusCall.connectSource("python3", [dbusHelperPath(), "stop_task"])
        agentStatus = "idle"
    }

    // ── Provide user response via D-Bus ──
    function provideUserResponse(response) {
        dbusCall.connectSource("python3", [
            dbusHelperPath(), "provide_response", response
        ])
    }

    // ── Clear chat ──
    function clearChat() {
        chatMessages = []
        chatMessagesChanged()
    }

    // ── Main layout ──
    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ── Header ──
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 3
            color: PlasmaCore.Theme.alternateBackgroundColor

            RowLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Heading {
                    level: 3
                    text: "AI Agent"
                    color: PlasmaCore.Theme.textColor
                }

                Item { Layout.fillWidth: true }

                // Connection indicator
                Rectangle {
                    width: Kirigami.Units.smallSpacing
                    height: Kirigami.Units.smallSpacing
                    radius: Kirigami.Units.smallSpacing / 2
                    color: agentConnected
                        ? PlasmaCore.Theme.positiveTextColor
                        : PlasmaCore.Theme.negativeTextColor
                    opacity: agentConnected ? 1.0 : 0.5
                }

                // Status text
                PlasmaComponents.Label {
                    text: {
                        switch (agentStatus) {
                            case "idle": return "Ready"
                            case "thinking": return "Thinking..."
                            case "executing": return "Working..."
                            case "waiting_user": return "Waiting..."
                            case "error": return "Error"
                            default: return agentStatus
                        }
                    }
                    color: PlasmaCore.Theme.disabledTextColor
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                }

                // Close button
                PlasmaComponents.ToolButton {
                    icon.name: "window-close"
                    onClicked: root.closeRequested()
                }
            }
        }

        // ── Tab bar: Agent | A2A Hub ──
        TabBar {
            id: tabBar
            Layout.fillWidth: true
            visible: false  // Hidden by default, shown when A2A Hub is available

            TabButton {
                text: "Agent"
                icon.name: "user-identity"
            }
            TabButton {
                text: "A2A Hub"
                icon.name: "view-conversation"
            }
        }

        // ── Content area ──
        StackLayout {
            id: contentStack
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: tabBar.currentIndex

            // ── Tab 0: Agent Chat ──
            ChatView {
                id: chatView
                Layout.fillWidth: true
                Layout.fillHeight: true
                messages: chatMessages

                onProvideUserResponse: function(response) {
                    root.provideUserResponse(response)
                }
            }

            // ── Tab 1: A2A Hub Conversations ──
            A2AChatView {
                id: a2aChatView
                Layout.fillWidth: true
                Layout.fillHeight: true
                hubUrl: "http://127.0.0.1:9000"
            }
        }

        // ── Context file chips ──
        Flow {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing / 2
            spacing: Kirigami.Units.smallSpacing / 2
            visible: contextFiles.length > 0

            Repeater {
                model: contextFiles
                delegate: Rectangle {
                    height: Kirigami.Units.gridUnit * 1.5
                    width: chipText.width + Kirigami.Units.gridUnit * 2
                    radius: Kirigami.Units.smallSpacing / 2
                    color: PlasmaCore.ColorScope.backgroundColor
                    border.color: PlasmaCore.Theme.highlightColor
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: Kirigami.Units.smallSpacing / 2
                        spacing: Kirigami.Units.smallSpacing / 2

                        PlasmaComponents.Label {
                            id: chipText
                            text: modelData
                            color: PlasmaCore.Theme.highlightColor
                            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                            elide: Text.ElideMiddle
                            Layout.fillWidth: true
                        }

                        PlasmaComponents.ToolButton {
                            icon.name: "window-close"
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                            onClicked: {
                                contextFiles = contextFiles.filter(function(f) { return f !== modelData })
                            }
                        }
                    }
                }
            }
        }

        // ── Input area ──
        TaskInput {
            id: taskInput
            Layout.fillWidth: true
            contextFiles: root.contextFiles

            onSendTask: function(task) {
                root.sendTask(task)
                taskInput.clear()
            }

            onAddFile: function(filePath) {
                var idx = root.contextFiles.indexOf(filePath)
                if (idx < 0) {
                    root.contextFiles.push(filePath)
                    root.contextFilesChanged()
                }
            }

            onRemoveFile: function(filePath) {
                root.contextFiles = root.contextFiles.filter(function(f) { return f !== filePath })
            }
        }

        // ── Status bar ──
        StatusBar {
            id: statusBar
            Layout.fillWidth: true
            agentStatus: root.agentStatus
            agentConnected: root.agentConnected

            onRunClicked: { taskInput.focus() }
            onStopClicked: { root.stopTask() }
            onClearClicked: { root.clearChat() }
            onToggleFileTree: { /* file picker */ }
        }
    }
}
