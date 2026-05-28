/*
 * A2AHubWindow.qml — Standalone window for A2A Hub conversation log.
 *
 * Usage: qmlscene A2AHubWindow.qml
 * Or integrate into existing SidePanelWindow as a tab.
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.plasma5support as Plasma5Support

Kirigami.ApplicationWindow {
    id: root
    title: "A2A Hub — Agent Conversations"
    width: 800
    height: 600
    visible: true

    property string hubUrl: "http://127.0.0.1:9000"
    property var conversations: []
    property var currentMessages: []
    property string selectedTaskId: ""
    property bool connected: false

    // ── Poll Hub ──
    Timer {
        id: pollTimer
        interval: 2000
        running: true
        repeat: true
        onTriggered: {
            convSource.connectSource("curl", ["-s", "-m", "5", hubUrl + "/conversations"])
        }
    }

    Plasma5Support.DataSource {
        id: convSource
        engine: "executable"
        onNewData: function(src, data) {
            if (data.status === "complete") {
                try {
                    var r = JSON.parse(data.output || "{}")
                    conversations = r.conversations || []
                    connected = true
                } catch(e) { connected = false }
            }
        }
    }

    function fetchConversation(taskId) {
        selectedTaskId = taskId
        msgSource.connectSource("curl", ["-s", "-m", "5", hubUrl + "/conversations/" + taskId])
    }

    Plasma5Support.DataSource {
        id: msgSource
        engine: "executable"
        onNewData: function(src, data) {
            if (data.status === "complete") {
                try {
                    var conv = JSON.parse(data.output || "{}")
                    currentMessages = conv.messages || []
                } catch(e) { currentMessages = [] }
            }
        }
    }

    // ── Main layout ──
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // ── Left: Conversation list ──
        Rectangle {
            Layout.preferredWidth: parent.width * 0.35
            Layout.fillHeight: true
            color: Kirigami.Theme.backgroundColor
            border.color: Kirigami.Theme.textColor
            border.width: 1

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    Label { text: "Conversations"; font.bold: true; Layout.fillWidth: true }
                    Rectangle { width: 8; height: 8; radius: 4; color: connected ? "#639922" : "#E24B4A" }
                    Label { text: connected ? "●" : "○"; color: connected ? "#639922" : "#E24B4A" }
                }

                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: conversations
                    spacing: 4

                    delegate: Rectangle {
                        width: ListView.view.width
                        height: 60
                        color: modelData.task_id === selectedTaskId ? Kirigami.Theme.highlightColor : Kirigami.Theme.backgroundColor
                        border.color: Kirigami.Theme.textColor
                        border.width: 1
                        radius: 4

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 4
                            spacing: 2

                            Label {
                                text: modelData.task_id || "unknown"
                                font.bold: true
                                font.pointSize: 10
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }
                            Label {
                                text: (modelData.messages ? modelData.messages.length : 0) + " msgs"
                                font.pointSize: 9
                                color: Kirigami.Theme.disabledTextColor
                                Layout.fillWidth: true
                            }
                            Label {
                                text: modelData.updated_at || ""
                                font.pointSize: 8
                                color: Kirigami.Theme.disabledTextColor
                                Layout.fillWidth: true
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: fetchConversation(modelData.task_id)
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

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 8
                spacing: 8

                Label {
                    text: selectedTaskId ? "Messages: " + selectedTaskId : "Select a conversation →"
                    font.bold: true
                    elide: Text.ElideMiddle
                    Layout.fillWidth: true
                }

                ListView {
                    id: msgList
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    model: currentMessages
                    spacing: 4
                    verticalLayoutDirection: ListView.BottomToTop

                    delegate: Rectangle {
                        width: ListView.view.width
                        color: modelData.role === "user" ? Qt.rgba(0.24, 0.68, 0.91, 0.1) : Qt.rgba(0.39, 0.60, 0.13, 0.1)
                        border.color: modelData.role === "user" ? "#3DAEE9" : "#639922"
                        border.width: 1
                        radius: 4

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: 6
                            spacing: 2

                            RowLayout {
                                Layout.fillWidth: true
                                Label {
                                    text: modelData.role === "user" ? "👤" : "🤖"
                                    font.pointSize: 12
                                }
                                Label {
                                    text: modelData.agent || modelData.role
                                    font.bold: true
                                    font.pointSize: 10
                                    Layout.fillWidth: true
                                }
                                Label {
                                    text: modelData.timestamp || ""
                                    font.pointSize: 8
                                    color: Kirigami.Theme.disabledTextColor
                                }
                            }

                            Label {
                                text: modelData.content || ""
                                wrapMode: Text.Wrap
                                textFormat: Text.PlainText
                                font.pointSize: 10
                                Layout.fillWidth: true
                            }

                            Label {
                                visible: modelData.metadata && modelData.metadata.model
                                text: "Model: " + (modelData.metadata ? modelData.metadata.model : "")
                                font.pointSize: 8
                                color: Kirigami.Theme.disabledTextColor
                                Layout.fillWidth: true
                            }
                        }
                    }
                }
            }
        }
    }
}
