/*
 * contents/ui/StatusBar.qml — Bottom status bar for the AI Agent panel.
 *
 * Shows:
 *   • Status indicator: idle / thinking / executing / complete / error
 *   • Connection status to backend
 *   • Action buttons: Run, Stop, Clear, Open Terminal, Open File
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents

RowLayout {
    id: statusBarRoot
    spacing: Kirigami.Units.smallSpacing
    height: Kirigami.Units.gridUnit * 2.5

    property string agentStatus: "idle"
    property bool agentConnected: false

    signal runClicked()
    signal stopClicked()
    signal clearClicked()
    signal toggleFileTree()

    // ── Status indicator ──
    RowLayout {
        spacing: 4

        // Status dot
        Rectangle {
            width: 8
            height: 8
            radius: 4
            color: {
                switch (agentStatus) {
                    case "idle":       return "#639922"  // green
                    case "thinking":   return "#3DAEE9"  // blue
                    case "executing":  return "#EF9F27"  // amber
                    case "complete":   return "#639922"  // green
                    case "error":      return "#E24B4A"  // red
                    case "waiting_user": return "#3DAEE9" // blue
                    default:           return Kirigami.Theme.disabledTextColor
                }
            }

            // Pulsing animation for thinking/executing
            SequentialAnimation on opacity {
                running: agentStatus === "thinking" || agentStatus === "executing"
                loops: Animation.Infinite
                NumberAnimation { from: 1.0; to: 0.3; duration: 500 }
                NumberAnimation { from: 0.3; to: 1.0; duration: 500 }
            }
        }

        Label {
            text: {
                switch (agentStatus) {
                    case "idle":         return "Ready"
                    case "thinking":     return "Thinking..."
                    case "executing":    return "Executing..."
                    case "complete":     return "Complete"
                    case "error":        return "Error"
                    case "waiting_user": return "Waiting for input"
                    default:             return agentStatus
                }
            }
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: Kirigami.Theme.disabledTextColor
        }
    }

    // ── Connection indicator ──
    Kirigami.Icon {
        source: agentConnected ? "network-connect" : "network-disconnect"
        implicitWidth: Kirigami.Units.iconSizes.small
        implicitHeight: Kirigami.Units.iconSizes.small

        PlasmaComponents.ToolTip {
            text: agentConnected ? "Connected to agent" : "Agent not connected"
        }
    }

    Item { Layout.fillWidth: true }  // Spacer

    // ── Action buttons ──
    PlasmaComponents.ToolButton {
        icon.name: "media-playback-start"
        text: "Run"
        display: PlasmaComponents.Button.IconOnly
        enabled: agentStatus === "idle" || agentStatus === "complete" || agentStatus === "error"
        onClicked: statusBarRoot.runClicked()

        PlasmaComponents.ToolTip {
            text: "Run Task"
        }
    }

    PlasmaComponents.ToolButton {
        icon.name: "media-playback-stop"
        text: "Stop"
        display: PlasmaComponents.Button.IconOnly
        enabled: agentStatus === "thinking" || agentStatus === "executing"
        onClicked: statusBarRoot.stopClicked()

        PlasmaComponents.ToolTip {
            text: "Stop Task"
        }
    }

    PlasmaComponents.ToolButton {
        icon.name: "edit-clear-history"
        text: "Clear"
        display: PlasmaComponents.Button.IconOnly
        onClicked: statusBarRoot.clearClicked()

        PlasmaComponents.ToolTip {
            text: "Clear Chat"
        }
    }

    PlasmaComponents.ToolButton {
        icon.name: "utilities-terminal"
        text: "Terminal"
        display: PlasmaComponents.Button.IconOnly

        PlasmaComponents.ToolTip {
            text: "Open Terminal in Working Directory"
        }
    }

    PlasmaComponents.ToolButton {
        icon.name: "document-open"
        text: "Files"
        display: PlasmaComponents.Button.IconOnly
        onClicked: statusBarRoot.toggleFileTree()

        PlasmaComponents.ToolTip {
            text: "Context Files"
        }
    }
}
