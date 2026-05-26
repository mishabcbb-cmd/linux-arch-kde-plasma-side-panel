/*
 * contents/config/ConfigApi.qml — API configuration settings page.
 *
 * All fields are bound to Plasmoid.configuration for persistence.
 *
 * Pattern: JARVIS configGeneral.qml (Kirigami.FormLayout + separators)
 */

import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.plasma.plasmoid

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
                        checked: plasmoid.configuration.apiProvider === "claude"
                        PlasmaComponents.ButtonGroup.group: providerGroup
                        onClicked: plasmoid.configuration.apiProvider = "claude"
                    }

                    PlasmaComponents.RadioButton {
                        text: i18n("Ollama (Local)")
                        checked: plasmoid.configuration.apiProvider === "ollama"
                        PlasmaComponents.ButtonGroup.group: providerGroup
                        onClicked: plasmoid.configuration.apiProvider = "ollama"
                    }

                    PlasmaComponents.RadioButton {
                        text: i18n("OpenRouter")
                        checked: plasmoid.configuration.apiProvider === "openrouter"
                        PlasmaComponents.ButtonGroup.group: providerGroup
                        onClicked: plasmoid.configuration.apiProvider = "openrouter"
                    }

                    PlasmaComponents.RadioButton {
                        text: i18n("OpenAI")
                        checked: plasmoid.configuration.apiProvider === "openai"
                        PlasmaComponents.ButtonGroup.group: providerGroup
                        onClicked: plasmoid.configuration.apiProvider = "openai"
                    }
                }
            }

            // ════════════════════════════════════════
            // API Settings
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                id: apiSettings
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("API Settings")
                }

                Label {
                    text: i18n("Set your API key for Claude or OpenRouter. Leave blank for local Ollama/llama.cpp.")
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
                        text: plasmoid.configuration.apiKey || ""
                        onTextChanged: plasmoid.configuration.apiKey = text
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
                        id: modelSelector
                        editable: true
                        model: [
                            "claude-sonnet-4-20250514",
                            "claude-3-5-sonnet-20241022",
                            "anthropic/claude-sonnet-4-20250514",
                            "openai/gpt-4o",
                            "google/gemini-2.5-flash",
                            "meta-llama/llama-4-maverick",
                        ]
                        currentIndex: {
                            var idx = model.indexOf(plasmoid.configuration.model || "claude-sonnet-4-20250514")
                            return idx >= 0 ? idx : 0
                        }
                        onCurrentTextChanged: plasmoid.configuration.model = currentText
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
                        text: plasmoid.configuration.ollamaHost || "http://localhost:11434"
                        placeholderText: "http://localhost:11434"
                        Layout.fillWidth: true
                        onTextChanged: plasmoid.configuration.ollamaHost = text
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Model Name:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: ollamaModelField
                        text: plasmoid.configuration.ollamaModel || "llama3.2"
                        placeholderText: "llama3.2"
                        Layout.fillWidth: true
                        onTextChanged: plasmoid.configuration.ollamaModel = text
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
                        value: plasmoid.configuration.temperature || 0.7
                        Layout.fillWidth: true
                        onValueChanged: plasmoid.configuration.temperature = value
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

            // ════════════════════════════════════════
            // MCP Server Configuration
            // ════════════════════════════════════════
            Kirigami.FormLayout {
                id: mcpSettings
                Layout.fillWidth: true

                Kirigami.Separator {
                    Kirigami.FormData.isSection: true
                    Kirigami.FormData.label: i18n("External MCP Servers")
                }

                Label {
                    text: i18n("Connect the agent to external MCP servers (lean-ctx, engram, codebase-memory, searxng, etc.). Servers provide additional tools for the agent.")
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                    color: Kirigami.Theme.disabledTextColor
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                }

                // ── MCP Server List ──
                PlasmaComponents.ScrollView {
                    Layout.fillWidth: true
                    Layout.minimumHeight: Kirigami.Units.gridUnit * 6
                    Layout.maximumHeight: Kirigami.Units.gridUnit * 12
                    clip: true

                    ListView {
                        id: mcpServerList
                        model: mcpServerModel
                        spacing: 2
                        currentIndex: -1

                        delegate: PlasmaComponents.ItemDelegate {
                            width: ListView.view.width
                            height: Kirigami.Units.gridUnit * 2.5

                            contentItem: RowLayout {
                                spacing: Kirigami.Units.smallSpacing

                                Kirigami.Icon {
                                    source: model.transport === "sse" ? "network-connect" : "utilities-terminal"
                                    implicitWidth: Kirigami.Units.iconSizes.small
                                    implicitHeight: Kirigami.Units.iconSizes.small
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 0

                                    Label {
                                        text: model.name
                                        font.bold: true
                                        elide: Text.ElideRight
                                    }

                                    Label {
                                        text: model.transport + "  •  " + (model.toolCount || 0) + " tools"
                                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                                        color: Kirigami.Theme.disabledTextColor
                                    }
                                }

                                PlasmaComponents.ToolButton {
                                    icon.name: "edit-delete"
                                    display: PlasmaComponents.Button.IconOnly
                                    onClicked: removeMcpServer(index)

                                    PlasmaComponents.ToolTip {
                                        text: "Remove " + model.name
                                    }
                                }
                            }
                        }

                        // Empty state
                        Kirigami.PlaceholderMessage {
                            anchors.centerIn: parent
                            visible: mcpServerList.count === 0
                            text: "No MCP servers configured"
                            explanation: "Add servers to provide the agent with additional tools"
                            icon.name: "network-server"
                        }
                    }
                }

                // ── Add MCP Server Form ──
                Kirigami.Separator {
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.smallSpacing
                }

                Label {
                    text: i18n("Add MCP Server")
                    font.bold: true
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Name:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: newServerName
                        placeholderText: "e.g. my-custom-server"
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Transport:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.ComboBox {
                        id: newServerTransport
                        model: ["stdio", "sse"]
                        currentIndex: 0
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Command:")
                    spacing: Kirigami.Units.smallSpacing
                    visible: newServerTransport.currentText === "stdio"

                    PlasmaComponents.TextField {
                        id: newServerCommand
                        placeholderText: "/usr/bin/my-mcp-server"
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Arguments:")
                    spacing: Kirigami.Units.smallSpacing
                    visible: newServerTransport.currentText === "stdio"

                    PlasmaComponents.TextField {
                        id: newServerArgs
                        placeholderText: "--flag --option value"
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("URL:")
                    spacing: Kirigami.Units.smallSpacing
                    visible: newServerTransport.currentText === "sse"

                    PlasmaComponents.TextField {
                        id: newServerUrl
                        placeholderText: "http://localhost:8765/sse"
                        Layout.fillWidth: true
                    }
                }

                RowLayout {
                    Kirigami.FormData.label: i18n("Auto-approve:")
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.TextField {
                        id: newServerAutoApprove
                        placeholderText: "tool1, tool2"
                        Layout.fillWidth: true
                    }

                    PlasmaComponents.ToolButton {
                        icon.name: "help-about"
                        PlasmaComponents.ToolTip {
                            text: "Comma-separated tool names that the agent can call without confirmation"
                        }
                    }
                }

                PlasmaComponents.Button {
                    text: i18n("Add Server")
                    icon.name: "list-add"
                    Layout.alignment: Qt.AlignRight
                    enabled: newServerName.text.trim() !== ""
                    onClicked: addMcpServer()
                }
            }

            Item { Layout.fillHeight: true }  // Bottom spacer
        }
    }

    // ── MCP Server Model ──
    ListModel {
        id: mcpServerModel
    }

    // ── Load MCP servers from config ──
    function loadMcpServers() {
        mcpServerModel.clear()
        var json = plasmoid.configuration.mcpServersJson || "[]"
        try {
            var servers = JSON.parse(json)
            for (var i = 0; i < servers.length; i++) {
                mcpServerModel.append(servers[i])
            }
        } catch (e) {
            console.warn("[ConfigApi] Failed to parse MCP servers:", e)
        }
    }

    // ── Save MCP servers to config ──
    function saveMcpServers() {
        var servers = []
        for (var i = 0; i < mcpServerModel.count; i++) {
            servers.push(mcpServerModel.get(i))
        }
        plasmoid.configuration.mcpServersJson = JSON.stringify(servers)
    }

    // ── Add MCP server ──
    function addMcpServer() {
        var name = newServerName.text.trim()
        if (!name) return

        var transport = newServerTransport.currentText
        var server = {
            name: name,
            transport: transport,
            toolCount: 0,
        }

        if (transport === "stdio") {
            server.command = newServerCommand.text.trim()
            server.args = newServerArgs.text.trim()
                ? newServerArgs.text.trim().split(/\s+/)
                : []
            server.auto_approve = newServerAutoApprove.text.trim()
                ? newServerAutoApprove.text.trim().split(/\s*,\s*/)
                : []
        } else {
            server.url = newServerUrl.text.trim()
            server.auto_approve = newServerAutoApprove.text.trim()
                ? newServerAutoApprove.text.trim().split(/\s*,\s*/)
                : []
        }

        mcpServerModel.append(server)
        saveMcpServers()

        // Clear form
        newServerName.text = ""
        newServerCommand.text = ""
        newServerArgs.text = ""
        newServerUrl.text = ""
        newServerAutoApprove.text = ""
    }

    // ── Remove MCP server ──
    function removeMcpServer(index) {
        mcpServerModel.remove(index)
        saveMcpServers()
    }

    Component.onCompleted: {
        loadMcpServers()
    }
}
