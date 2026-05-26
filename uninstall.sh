#!/usr/bin/env bash
# uninstall.sh — Remove the KDE AI Agent Panel
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

echo_ok()   { echo -e "${GREEN}✓${NC} $*"; }
echo_info() { echo -e "${BLUE}ℹ${NC} $*"; }

echo "================================================"
echo "  KDE AI Agent Panel — Uninstaller"
echo "================================================"
echo ""

# Stop and disable systemd service
echo_info "Stopping systemd service..."
systemctl --user stop kde-ai-agent.service 2>/dev/null || true
systemctl --user disable kde-ai-agent.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/kde-ai-agent.service"
systemctl --user daemon-reload
echo_ok "Service removed"

# Remove plasmoid
echo_info "Removing plasmoid..."
if command -v kpackagetool6 &>/dev/null; then
    kpackagetool6 --remove org.kde.plasma.ai-agent-panel 2>/dev/null || true
else
    rm -rf "$HOME/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel"
fi
echo_ok "Plasmoid removed"

# Remove agent code
echo_info "Removing agent code..."
rm -rf "$HOME/.local/share/kde-ai-agent"
echo_ok "Agent code removed"

# Optionally remove config
echo ""
echo_info "Config directory: ~/.config/kde-ai-agent/"
read -p "Remove config files too? [y/N] " -r REPLY
if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    rm -rf "$HOME/.config/kde-ai-agent"
    echo_ok "Config removed"
else
    echo_ok "Config kept"
fi

echo ""
echo_ok "Uninstall complete."
echo ""
echo "To also remove Python packages (optional):"
echo "  pip uninstall anthropic dbus-python gitpython tree-sitter watchdog"
