/*
 * contents/config/ConfigApi.qml — API configuration settings page.
 *
 * Settings:
 *   • API key input (masked)
 *   • Provider toggle: Claude API ↔ Ollama
 *   • Model selector (claude-sonnet-4-20250514 / ollama model name)
 *   • Ollama host URL
 *
 * Pattern: JARVIS configGeneral.qml (Kirigami.FormLayout + separators)
 */

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents

Item {
    id: configApiRoot
    width: parent ? parent.width : 0
    height: parent ? parent.height : 0

    ScrollView {
        anchors.fill: parent
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: 0

            // ════════════════════════════════════════
            // Provider Selection
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("LLM Provider")
                }

                Label {
                    text: i18n("Choose between Anthropic's Claude API (cloud) or a local Ollama model.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }

                // Provider toggle
                RowLayout {
                    Kirigami.FormData.label: i18n("Provider:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.ButtonGroup {
                        id: providerGroup
                    }

                    PlasmaComponents.RadioButton {
                        text: i18n("Claude API")
                        checked: true
                        PlasmaComponents.ButtonGroup.group: providerGroup
                    }

                    PlasmaComponents.RadioButton {
                        text: i18n("Ollama (Local)")
                        PlasmaComponents.ButtonGroup.group: providerGroup
                    }
                }
            }

            // ════════════════════════════════════════
            // Claude API Settings
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                id: claudeSettings
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Claude API / OpenRouter / llama.cpp")
                }

                Label {
                    text: i18n("Set your API key for Claude or OpenRouter. Leave blank for local llama.cpp.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("API Key:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: apiKeyField
                        echoMode: TextInput.Password
                        placeholderText: "sk-ant-api03-... or sk-or-v1-..."
                        Layout.fillWidth: true
                    }

                    PlasmaComponents.Button {
                        icon.name: apiKeyField.echoMode === TextInput.Password ? "visibility" : "hint"
                        display: PlasmaComponents.Button.IconOnly
                        onClicked: {
                            apiKeyField.echoMode = apiKeyField.echoMode === TextInput.Password
                                ? TextInput.Normal : TextInput.Password
                        }
                    }
                }

                Label {
                    text: i18n("Anthropic: <a href='https://console.anthropic.com/'>console.anthropic.com</a>  |  OpenRouter: <a href='https://openrouter.ai/keys'>openrouter.ai/keys</a>")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    onLinkActivated: Qt.openUrlExternally(link)
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Model:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.ComboBox {
                        id: claudeModelSelector
                        model: [
                            "claude-sonnet-4-20250514",
                            "claude-3-5-sonnet-20241022",
                            "anthropic/claude-sonnet-4-20250514",
                            "openai/gpt-4o",
                            "google/gemini-2.5-flash",
                            "meta-llama/llama-4-maverick",
                        ]
                        currentIndex: 0
                        Layout.fillWidth: true
                    }
                }
            }

            // ════════════════════════════════════════
            // Local LLM Settings (Ollama / llama.cpp)
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                id: ollamaSettings
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Local LLM (Ollama / llama.cpp)")
                }

                Label {
                    text: i18n("Ollama or llama.cpp must be installed and running. Models are downloaded on first use.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Host URL:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: ollamaHostField
                        text: "http://localhost:11434"
                        placeholderText: "http://localhost:11434"
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Model Name:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: ollamaModelField
                        text: "llama3.2"
                        placeholderText: "llama3.2"
                        Layout.fillWidth: true
                    }
                }

                Label {
                    text: i18n("Popular models: llama3.2, codellama, deepseek-coder-v2, qwen2.5-coder. For llama.cpp, use the model file name (e.g. codestral-22b).")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            // ════════════════════════════════════════
            // Temperature
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("Generation Settings")
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Temperature:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.Slider {
                        id: temperatureSlider
                        from: 0.0
                        to: 1.0
                        stepSize: 0.1
                        value: 0.7
                        Layout.fillWidth: true
                    }

                    Label {
                        text: temperatureSlider.value.toFixed(1)
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 1.5
                        horizontalAlignment: Text.AlignRight
                    }
                }

                Label {
                    text: i18n("Lower = more deterministic. Higher = more creative.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }
            }

            Item { Layout.fillHeight: true }  // Bottom spacer
        }
    }
}
