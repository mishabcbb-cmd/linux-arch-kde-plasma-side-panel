// KWin script: Toggle AI Agent Side Panel
// Registers a global shortcut that toggles the side panel via D-Bus.
// Shortcut is configurable in System Settings → Keyboard → Shortcuts → KWin

function togglePanel() {
    // Call our agent's D-Bus method to toggle the panel
    callDBus(
        "org.kde.aiagent",
        "/org/kde/aiagent",
        "org.kde.aiagent",
        "TogglePanel",
    );
}

registerShortcut(
    "ToggleAIAgentPanel",
    "Toggle AI Agent Panel",
    "Meta+Shift+A",
    togglePanel
);
