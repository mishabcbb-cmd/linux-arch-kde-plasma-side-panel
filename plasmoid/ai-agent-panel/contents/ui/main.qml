/*
 * contents/ui/main.qml — Root plasmoid item for the AI Agent Panel.
 *
 * Pattern: AppGrid's GridWindow — creates a standalone Window as a child
 * component, avoiding Wayland GLib re-entrancy issues from PyQt6.
 *
 * The window is positioned on the left screen edge, frameless, using
 * LayerShellQt (Wayland) via QML attached properties for proper
 * compositor integration — no C++ plugin needed.
 *
 * Toggle via Plasma shortcut (Meta+A) or panel icon click.
 *
 * D-Bus integration:
 *   • dbusCall — calls agent methods via dbus_helper.py (executable engine)
 *   • Signals received by SidePanelWindow's dbusListener (executable engine
 *     running dbus_listener.py as subprocess)
 */

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as Plasma5Support

PlasmoidItem {
    id: kicker

    // ── Use Plasma's built-in activation (click + global shortcut) ──
    activationTogglesExpanded: false

    compactRepresentation: compactRepresentationComponent
    fullRepresentation: Item {}
    preferredRepresentation: compactRepresentation

    // ── Side panel window state ──
    property QtObject sideWindow: null
    property bool sideOpen: false

    // ── Agent state (shared with SidePanelWindow) ──
    property string agentStatus: "idle"
    property var chatMessages: []
    property var contextFiles: []

    // ── Plasma activation → toggle side window ──
    Connections {
        target: Plasmoid
        function onActivated() { kicker.toggleWindow() }
    }

    // ── Compact representation (panel icon) ──
    Component {
        id: compactRepresentationComponent
        PlasmaComponents.Button {
            icon.name: "assistant"
            text: "AI Agent"
            onClicked: kicker.toggleWindow()

            PlasmaCore.ToolTipArea {
                anchors.fill: parent
                mainText: "AI Agent Panel"
                subText: "Status: " + kicker.agentStatus
            }
        }
    }

    // ── Side panel window component (loaded from file) ──
    // SidePanelWindow is a QML file, not a registered type — use Qt.createComponent
    property var sideWindowComponent: null

    // ── Toggle window ──
    function toggleWindow() {
        if (sideOpen) {
            closeWindow()
        } else {
            openWindow()
        }
    }

    function openWindow() {
        sideOpen = true
        if (!sideWindow) {
            if (!sideWindowComponent) {
                sideWindowComponent = Qt.resolvedUrl("SidePanelWindow.qml")
            }
            var comp = Qt.createComponent(sideWindowComponent)
            if (comp.status === Component.Ready) {
                sideWindow = comp.createObject(kicker, {
                    "agentStatus": kicker.agentStatus,
                    "chatMessages": kicker.chatMessages,
                    "contextFiles": kicker.contextFiles
                })
                if (sideWindow) {
                    sideWindow.closeRequested.connect(kicker.closeWindow)
                }
            } else if (comp.status === Component.Error) {
                console.error("[main.qml] Failed to load SidePanelWindow.qml:", comp.errorString())
                sideOpen = false
                return
            }
        }
        if (sideWindow) {
            sideWindow.showPanel()
        }
    }

    function closeWindow() {
        sideOpen = false
        if (sideWindow) {
            sideWindow.hidePanel()
        }
    }

    // ── D-Bus method call helper (used for initial status check) ──
    Plasma5Support.DataSource {
        id: dbusCall
        engine: "executable"
        onNewData: function(sourceName, data) {
            if (data.status === "complete") {
                var output = (data.output || "").trim()
                if (output.startsWith("STATUS:")) {
                    try {
                        var statusData = JSON.parse(output.substring(7).trim())
                        kicker.agentStatus = statusData.status || "idle"
                    } catch(e) {}
                }
            }
        }
    }

    // ── Refresh agent status on plasmoid ready ──
    Component.onCompleted: {
        // Check agent status via dbus_helper.py
        var helperPath = Qt.resolvedUrl("dbus_helper.py")
        if (helperPath.toString().startsWith("file://")) {
            helperPath = helperPath.toString().substring(7)
        }
        dbusCall.connectSource("python3", [helperPath, "get_status"])
    }
}
