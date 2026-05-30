/*
 * contents/ui/main.qml — AI Agent Panel plasmoid.
 *
 * Pattern: AppGrid — compact representation (tray icon) toggles
 * a standalone SidePanelWindow with slide animation.
 *
 * Toggle via Plasma shortcut (Meta+A) or tray icon click.
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

    // ── Compact representation (tray icon) ──
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

    // ── Side panel window component ──
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
}
