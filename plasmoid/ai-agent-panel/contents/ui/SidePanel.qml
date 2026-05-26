/*
 * SidePanel.qml — Standalone side panel window for KDE AI Agent.
 *
 * Loaded by agent/side_panel.py via PyQt6 QQuickView.
 * Communicates with the agent backend via agentBridge (D-Bus).
 *
 * This is a frameless window positioned on the right side of the screen.
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: sidePanel
    visible: true

    // ── Colors ──
    readonly property color bgColor: Qt.rgba(0.12, 0.12, 0.14, 1.0)
    readonly property color surfaceColor: Qt.rgba(0.16, 0.16, 0.18, 1.0)
    readonly property color accentColor: Qt.rgba(0.24, 0.68, 0.91, 1.0)
    readonly property color textColor: Qt.rgba(0.95, 0.95, 0.97, 1.0)
    readonly property color dimTextColor: Qt.rgba(0.6, 0.6, 0.65, 1.0)
    readonly property color borderColor: Qt.rgba(0.3, 0.3, 0.35, 1.0)

    // ── Agent state ──
    property string agentStatus: "idle"
    property var chatMessages: []
    property var contextFiles: []

    // ── Title bar drag area ──
    MouseArea {
        id: dragArea
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 32
        property variant previousPosition: Qt.point(0, 0)

        onPressed: {
            previousPosition = Qt.point(mouseX, mouseY)
        }

        onPositionChanged: {
            if (pressed) {
                var dx = mouseX - previousPosition.x
                var dy = mouseY - previousPosition.y
                sidePanel.x += dx
                sidePanel.y += dy
            }
        }
    }

    // ── Close button ──
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        width: 32
        height: 32
        color: "transparent"

        Text {
            anchors.centerIn: parent
            text: "✕"
            color: dimTextColor
            font.pixelSize: 14
        }

        MouseArea {
            anchors.fill: parent
            onClicked: sidePanel.close()
        }
    }

    // ── Main layout ──
    Rectangle {
        anchors.fill: parent
        color: bgColor

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Header ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 48
                color: surfaceColor

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 12
                    spacing: 8

                    Text {
                        text: "AI Agent"
                        color: textColor
                        font.pixelSize: 16
                        font.bold: true
                    }

                    Item { Layout.fillWidth: true }

                    // Status indicator
                    Rectangle {
                        width: 8
                        height: 8
                        radius: 4
                        color: {
                            switch (agentStatus) {
                                case "idle": return "#4CAF50"
                                case "thinking": return "#FFC107"
                                case "executing": return "#2196F3"
                                case "error": return "#F44336"
                                default: return "#9E9E9E"
                            }
                        }
                    }

                    Text {
                        text: agentStatus.charAt(0).toUpperCase() + agentStatus.slice(1)
                        color: dimTextColor
                        font.pixelSize: 12
                    }
                }
            }

            // ── Chat messages ──
            ListView {
                id: chatList
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.leftMargin: 8
                Layout.rightMargin: 8
                Layout.topMargin: 8
                spacing: 8
                clip: true
                model: chatMessages
                boundsBehavior: Flickable.StopAtBounds

                delegate: Rectangle {
                    width: chatList.width - 16
                    height: msgContent.height + 24
                    radius: 8
                    color: {
                        switch (modelData.type) {
                            case "thought": return Qt.rgba(0.2, 0.2, 0.25, 1.0)
                            case "tool_call": return Qt.rgba(0.15, 0.25, 0.35, 1.0)
                            case "tool_result": return Qt.rgba(0.15, 0.3, 0.2, 1.0)
                            case "error": return Qt.rgba(0.35, 0.15, 0.15, 1.0)
                            case "question": return Qt.rgba(0.3, 0.25, 0.15, 1.0)
                            default: return surfaceColor
                        }
                    }

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 4

                        Text {
                            text: {
                                switch (modelData.type) {
                                    case "thought": return "💭 Thought"
                                    case "tool_call": return "🔧 " + (modelData.toolName || "Tool Call")
                                    case "tool_result": return "📋 " + (modelData.toolName || "Result")
                                    case "error": return "❌ Error"
                                    case "question": return "❓ Question"
                                    default: return "💬 Message"
                                }
                            }
                            color: accentColor
                            font.pixelSize: 11
                            font.bold: true
                        }

                        Text {
                            id: msgContent
                            Layout.fillWidth: true
                            text: modelData.content || ""
                            color: textColor
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            maximumLineCount: 50
                        }
                    }
                }

                // Auto-scroll to bottom
                onCountChanged: {
                    if (count > 0) {
                        positionViewAtEnd()
                    }
                }
            }

            // ── Context file chips ──
            Flow {
                Layout.fillWidth: true
                Layout.leftMargin: 8
                Layout.rightMargin: 8
                Layout.bottomMargin: 4
                spacing: 4
                visible: contextFiles.length > 0

                Repeater {
                    model: contextFiles
                    delegate: Rectangle {
                        height: 24
                        width: chipText.width + 24
                        radius: 4
                        color: Qt.rgba(0.24, 0.68, 0.91, 0.2)
                        border.color: Qt.rgba(0.24, 0.68, 0.91, 0.4)
                        border.width: 1

                        RowLayout {
                            anchors.fill: parent
                            anchors.margins: 4
                            spacing: 4

                            Text {
                                id: chipText
                                text: modelData
                                color: accentColor
                                font.pixelSize: 11
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            Text {
                                text: "✕"
                                color: dimTextColor
                                font.pixelSize: 10
                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        contextFiles = contextFiles.filter(function(f) { return f !== modelData })
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── Input area ──
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                color: surfaceColor
                border.color: borderColor
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8

                    TextArea {
                        id: inputField
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        placeholderText: "Describe your task... (Ctrl+Enter to send)"
                        color: textColor
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        background: null

                        Keys.onPressed: function(event) {
                            if (event.key === Qt.Key_Return && event.modifiers & Qt.ControlModifier) {
                                sendTask()
                                event.accepted = true
                            }
                        }
                    }

                    // ── Bottom bar ──
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8

                        // Status
                        RowLayout {
                            spacing: 4
                            Layout.fillWidth: true

                            Rectangle {
                                width: 6
                                height: 6
                                radius: 3
                                color: agentStatus === "idle" ? "#4CAF50" : "#FFC107"
                            }

                            Text {
                                text: agentStatus === "idle" ? "Ready" : agentStatus
                                color: dimTextColor
                                font.pixelSize: 11
                            }
                        }

                        // Buttons
                        RowLayout {
                            spacing: 4

                            // File button
                            Rectangle {
                                width: 28
                                height: 28
                                radius: 4
                                color: "transparent"

                                Text {
                                    anchors.centerIn: parent
                                    text: "📁"
                                    font.pixelSize: 14
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        // TODO: file picker
                                    }
                                }
                            }

                            // Send button
                            Rectangle {
                                width: 28
                                height: 28
                                radius: 4
                                color: accentColor

                                Text {
                                    anchors.centerIn: parent
                                    text: "▶"
                                    color: "white"
                                    font.pixelSize: 12
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: sendTask()
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // ── Functions ──
    function sendTask() {
        var text = inputField.text.trim()
        if (text === "") return

        // Add user message to chat
        chatMessages.push({
            type: "thought",
            content: "🧑 You: " + text
        })
        chatMessagesChanged()

        // Send via bridge
        if (typeof agentBridge !== 'undefined') {
            agentBridge.runTask(text, JSON.stringify(contextFiles))
        }

        inputField.text = ""
    }

    // ── D-Bus signal handlers ──
    Connections {
        target: typeof agentBridge !== 'undefined' ? agentBridge : null

        function onStatusChanged(status) {
            agentStatus = status
        }

        function onTokenStream(content, msgType) {
            var last = chatMessages[chatMessages.length - 1]
            if (last && last.type === msgType) {
                last.content += content
                chatMessagesChanged()
            } else {
                chatMessages.push({
                    type: msgType || "thought",
                    content: content
                })
                chatMessagesChanged()
            }
        }

        function onToolCallStarted(toolName, inputJson) {
            chatMessages.push({
                type: "tool_call",
                toolName: toolName,
                content: "Calling: " + toolName + "\n" + inputJson
            })
            chatMessagesChanged()
        }

        function onToolCallResult(toolName, output, success, error) {
            chatMessages.push({
                type: "tool_result",
                toolName: toolName,
                content: output || error,
                success: success
            })
            chatMessagesChanged()
        }

        function onTaskComplete(data) {
            agentStatus = "complete"
        }

        function onErrorOccurred(error) {
            agentStatus = "error"
            chatMessages.push({
                type: "error",
                content: error
            })
            chatMessagesChanged()
        }

        function onQuestionAsked(question, optionsJson) {
            agentStatus = "waiting_user"
            chatMessages.push({
                type: "question",
                content: question,
                options: JSON.parse(optionsJson || "[]")
            })
            chatMessagesChanged()
        }
    }
}
