/*
 * A2AChatView.qml — Conversation log viewer for A2A Hub.
 *
 * Displays the full conversation history between user and agents.
 * Uses Plasma5Support.DataSource to poll Hub HTTP API.
 *
 * Properties:
 *   hubUrl: string — Hub HTTP URL (default: "http://127.0.0.1:9000")
 *   pollInterval: int — Polling interval in ms (default: 2000)
 *
 * Signals:
 *   messageClicked(task_id, message) — Emitted when a message is clicked
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as Plasma5Support

Item {
    id: root

    property string hubUrl: "http://127.0.0.1:9000"
    property int pollInterval: 2000
    property var conversations: []
    property var currentMessages: []
    property string selectedTaskId: ""
    property bool connected: false

    signal messageClicked(string taskId, var message)

    // ── Poll Hub for conversations ──
    Timer {
        id: pollTimer
        interval: root.pollInterval
        running: root.visible
        repeat: true
        onTriggered: {
            conversationsSource.connectSource("curl", [
                "-s", "-m", "5",
                root.hubUrl + "/conversations"
            ])
        }
    }

    // ── Fetch conversations ──
    Plasma5Support.DataSource {
        id: conversationsSource
        engine: "executable"
        onNewData: function(sourceName, data) {
            if (data.status === "complete") {
                try {
                    var result = JSON.parse(data.output || "{}")
                    root.conversations = result.conversations || []
                    root.connected = true
                } catch (e) {
                    root.connected = false
                }
            }
        }
    }

    // ── Fetch specific conversation ──
    function fetchConversation(taskId) {
        selectedTaskId = taskId
        conversationSource.connectSource("curl", [
            "-s", "-m", "5",
            root.hubUrl + "/conversations/" + taskId
        ])
    }

    Plasma5Support.DataSource {
        id: conversationSource
        engine: "executable"
        onNewData: function(sourceName, data) {
            if (data.status === "complete") {
                try {
                    var conv = JSON.parse(data.output || "{}")
                    root.currentMessages = conv.messages || []
                } catch (e) {
                    root.currentMessages = []
                }
            }
        }
    }

    // ── UI ──
    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        // ── Header ──
        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Icon {
                source: "view-conversation"
                implicitWidth: Kirigami.Units.iconSizes.medium
                implicitHeight: Kirigami.Units.iconSizes.medium
            }

            Label {
                text: "A2A Hub — Agent Conversations"
                font.bold: true
                font.pointSize: Kirigami.Theme.defaultFont.pointSize
                Layout.fillWidth: true
            }

            // Connection status
            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: root.connected ? "#639922" : "#E24B4A"
            }

            Label {
                text: root.connected ? "Connected" : "Disconnected"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: root.connected ? "#639922" : "#E24B4A"
            }
        }

        // ── Conversation list + messages ──
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Kirigami.Units.smallSpacing

            // ── Left: Conversation list ──
            Rectangle {
                Layout.preferredWidth: parent.width * 0.35
                Layout.fillHeight: true
                color: Kirigami.Theme.backgroundColor
                border.color: Kirigami.Theme.textColor
                border.width: 1
                radius: Kirigami.Units.smallSpacing

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.smallSpacing
                    spacing: Kirigami.Units.smallSpacing

                    Label {
                        text: "Conversations (" + root.conversations.length + ")"
                        font.bold: true
                    }

                    ListView {
                        id: conversationList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.conversations
                        spacing: Kirigami.Units.smallSpacing / 2

                        delegate: ItemDelegate {
                            width: ListView.view.width
                            padding: Kirigami.Units.smallSpacing

                            background: Rectangle {
                                color: modelData.task_id === root.selectedTaskId
                                    ? Kirigami.Theme.highlightColor
                                    : "transparent"
                                radius: Kirigami.Units.smallSpacing / 2
                            }

                            contentItem: ColumnLayout {
                                spacing: 2

                                Label {
                                    text: modelData.task_id || "unknown"
                                    font.bold: true
                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                    elide: Text.ElideMiddle
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: (modelData.messages ? modelData.messages.length : 0) + " messages"
                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                    color: Kirigami.Theme.disabledTextColor
                                    Layout.fillWidth: true
                                }

                                Label {
                                    text: modelData.updated_at || ""
                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                    color: Kirigami.Theme.disabledTextColor
                                    Layout.fillWidth: true
                                }
                            }

                            onClicked: {
                                root.fetchConversation(modelData.task_id)
                            }
                        }
                    }
                }
            }

            // ── Right: Messages ──
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: Kirigami.Theme.backgroundColor
                border.color: Kirigami.Theme.textColor
                border.width: 1
                radius: Kirigami.Units.smallSpacing

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.smallSpacing
                    spacing: Kirigami.Units.smallSpacing

                    Label {
                        text: root.selectedTaskId
                            ? "Messages: " + root.selectedTaskId
                            : "Select a conversation"
                        font.bold: true
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }

                    ListView {
                        id: messageList
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.currentMessages
                        spacing: Kirigami.Units.smallSpacing
                        verticalLayoutDirection: ListView.BottomToTop

                        delegate: ItemDelegate {
                            width: ListView.view.width
                            padding: Kirigami.Units.smallSpacing

                            background: Rectangle {
                                color: modelData.role === "user"
                                    ? Qt.rgba(0.24, 0.68, 0.91, 0.08)
                                    : Qt.rgba(0.39, 0.60, 0.13, 0.08)
                                radius: Kirigami.Units.smallSpacing / 2
                            }

                            contentItem: ColumnLayout {
                                spacing: 2

                                RowLayout {
                                    Layout.fillWidth: true

                                    Kirigami.Icon {
                                        source: modelData.role === "user" ? "user-identity" : "assistant"
                                        implicitWidth: Kirigami.Units.iconSizes.small
                                        implicitHeight: Kirigami.Units.iconSizes.small
                                    }

                                    Label {
                                        text: modelData.agent || modelData.role
                                        font.bold: true
                                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                                        Layout.fillWidth: true
                                    }

                                    Label {
                                        text: modelData.timestamp || ""
                                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                                        color: Kirigami.Theme.disabledTextColor
                                    }
                                }

                                Label {
                                    text: modelData.content || ""
                                    wrapMode: Text.Wrap
                                    textFormat: Text.PlainText
                                    font.pointSize: Kirigami.Theme.defaultFont.pointSize
                                    Layout.fillWidth: true
                                    onLinkActivated: Qt.openUrlExternally(link)
                                }

                                // Model metadata
                                Label {
                                    visible: modelData.metadata && modelData.metadata.model
                                    text: "Model: " + (modelData.metadata ? modelData.metadata.model : "")
                                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                                    color: Kirigami.Theme.disabledTextColor
                                    Layout.fillWidth: true
                                }
                            }

                            onClicked: {
                                root.messageClicked(root.selectedTaskId, modelData)
                            }
                        }
                    }
                }
            }
        }
    }
}
