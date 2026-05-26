/*
 * contents/ui/ChatView.qml — Scrollable streaming chat log.
 *
 * Color-coded by message type (matching the plan spec):
 *   • LLM thought    → default text color
 *   • Tool call      → amber (#EF9F27)
 *   • Tool result    → teal (#1D9E75)
 *   • Error          → red (#E24B4A)
 *   • Task complete  → green (#639922)
 *   • Question       → blue (#3DAEE9)
 *
 * Streaming pattern from end4 (Ai.qml): tokens append to the last message
 * as they arrive via D-Bus signal, rather than creating new blocks each time.
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents

ScrollView {
    id: chatScrollView
    clip: true
    contentWidth: availableWidth

    property var messages: []
    property alias listView: messageList

    // Auto-scroll to bottom when new messages arrive
    onMessagesChanged: {
        if (messageList.count > 0) {
            messageList.positionViewAtEnd()
        }
    }

    ListView {
        id: messageList
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing
        model: ListModel {
            id: messageModel
            dynamicRoles: true
        }

        delegate: ItemDelegate {
            id: messageDelegate
            width: ListView.view.width
            padding: Kirigami.Units.smallSpacing

            contentItem: RowLayout {
                spacing: Kirigami.Units.smallSpacing
                width: parent.width

                // ── Message type icon ──
                Kirigami.Icon {
                    id: msgIcon
                    Layout.alignment: Qt.AlignTop
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: Kirigami.Units.iconSizes.small
                    source: {
                        switch (model.type) {
                            case "thought": return "user-identity"
                            case "tool_call": return "run-build"
                            case "tool_result": return "dialog-ok"
                            case "error": return "dialog-error"
                            case "task_complete": return "rating"
                            case "question": return "help-about"
                            default: return "user-identity"
                        }
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    // ── Tool name label (for tool messages) ──
                    Label {
                        visible: model.toolName !== undefined && model.toolName !== ""
                        text: model.toolName || ""
                        font.bold: true
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        color: getColor(model.type)
                    }

                    // ── Message content ──
                    Label {
                        Layout.fillWidth: true
                        text: model.content || ""
                        wrapMode: Text.Wrap
                        textFormat: Text.PlainText
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize
                        color: getColor(model.type)
                        onLinkActivated: Qt.openUrlExternally(link)
                    }

                    // ── Question options (for ask_user) ──
                    Flow {
                        visible: model.options !== undefined && model.options.length > 0
                        Layout.fillWidth: true
                        spacing: Kirigami.Units.smallSpacing

                        Repeater {
                            model: model.options || []
                            delegate: PlasmaComponents.Button {
                                text: modelData
                                onClicked: {
                                    if (typeof root !== 'undefined' && root.provideUserResponse) {
                                        root.provideUserResponse(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // ── Background tint by message type ──
            background: Rectangle {
                color: {
                    switch (model.type) {
                        case "tool_call":
                            return Qt.rgba(0.94, 0.62, 0.15, 0.06)  // amber bg
                        case "tool_result":
                            return Qt.rgba(0.11, 0.62, 0.46, 0.06)  // teal bg
                        case "error":
                            return Qt.rgba(0.89, 0.29, 0.29, 0.06)  // red bg
                        case "task_complete":
                            return Qt.rgba(0.39, 0.60, 0.13, 0.08)  // green bg
                        case "question":
                            return Qt.rgba(0.24, 0.68, 0.91, 0.06)  // blue bg
                        default:
                            return "transparent"
                    }
                }
                radius: Kirigami.Units.smallSpacing / 2
            }
        }

        // ── Empty state ──
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: messageList.count === 0
            text: "AI Agent Ready"
            explanation: "Type a task below to get started.\nThe agent can read, write, search, and test code."
            icon.name: "assistant"
        }
    }

    // ── Color helper ──
    function getColor(msgType) {
        switch (msgType) {
            case "tool_call":     return "#EF9F27"  // amber
            case "tool_result":   return "#1D9E75"  // teal
            case "error":         return "#E24B4A"  // red
            case "task_complete": return "#639922"  // green
            case "question":      return "#3DAEE9"  // blue
            default:              return Kirigami.Theme.textColor
        }
    }
}
