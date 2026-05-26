/*
 * contents/config/ConfigAdvanced.qml — Advanced settings: OpenObserve, token limits.
 *
 * All fields bound to Plasmoid.configuration for persistence.
 */

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.plasmoid

Item {
    id: configAdvancedRoot
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: 0

            // ════════════════════════════════════════
            // Token Limits
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Token Limits")
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Max Input Tokens:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.SpinBox {
                        id: maxInputTokens
                        from: 10000
                        to: 200000
                        stepSize: 10000
                        value: plasmoid.configuration.maxInputTokens || 100000
                        onValueChanged: plasmoid.configuration.maxInputTokens = value
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Max Output Tokens:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.SpinBox {
                        id: maxOutputTokens
                        from: 1024
                        to: 32768
                        stepSize: 1024
                        value: plasmoid.configuration.maxOutputTokens || 8192
                        onValueChanged: plasmoid.configuration.maxOutputTokens = value
                        Layout.fillWidth: true
                    }
                }
            }

            // ════════════════════════════════════════
            // OpenObserve
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Observability (OpenObserve)")
                }

                Label {
                    text: i18n("Stream agent events (tool calls, LLM responses, errors) to an OpenObserve instance for real-time monitoring and dashboards.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Endpoint:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: ooEndpointField
                        text: plasmoid.configuration.ooEndpoint || ""
                        placeholderText: "http://localhost:5080"
                        Layout.fillWidth: true
                        onTextChanged: plasmoid.configuration.ooEndpoint = text
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Stream Name:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: ooStreamField
                        text: plasmoid.configuration.ooStream || "ai-agent-events"
                        placeholderText: "ai-agent-events"
                        Layout.fillWidth: true
                        onTextChanged: plasmoid.configuration.ooStream = text
                    }
                }

                Label {
                    text: i18n("Leave endpoint empty to disable observability streaming.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            // ════════════════════════════════════════
            // Agent Limits
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Agent Limits")
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Max Iterations:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.SpinBox {
                        id: maxIterations
                        from: 5
                        to: 100
                        stepSize: 5
                        value: plasmoid.configuration.maxIterations || 50
                        onValueChanged: plasmoid.configuration.maxIterations = value
                        Layout.fillWidth: true
                    }
                }

                Label {
                    text: i18n("Maximum number of thinking-acting loops before the agent stops. Higher values allow more complex tasks.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
