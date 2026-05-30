#!/usr/bin/env bash
# install.sh — Install the KDE AI Agent Panel
#
# Steps:
#   1. Install system packages (pacman/yay)
#   2. Install Python dependencies
#   3. Install the plasmoid via kpackagetool6
#   4. Create systemd user service for the agent backend
#   5. Create default config
#   6. Print setup instructions
#
# Tested on: Arch Linux with KDE Plasma 6

set -euo pipefail

# ── Colors ────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m' # No Color

echo_ok()   { echo -e "${GREEN}✓${NC} $*"; }
echo_info() { echo -e "${BLUE}ℹ${NC} $*"; }
echo_warn() { echo -e "${YELLOW}⚠${NC} $*"; }
echo_err()  { echo -e "${RED}✗${NC} $*"; }

# ── Directories ───────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
PLASMOID_DIR="$PROJECT_DIR/plasmoid/ai-agent-panel"
AGENT_DIR="$PROJECT_DIR/agent"
CONFIG_DIR="$HOME/.config/kde-ai-agent"
SERVICE_DIR="$HOME/.config/systemd/user"

echo "================================================"
echo "  KDE AI Agent Panel — Installer"
echo "================================================"
echo ""

# ── Step 1: System Packages ──────────────────────
echo_info "Step 1/6: Installing system packages..."

REQUIRED_PKGS=(
    plasma-framework
    kirigami2
    qt6-declarative
    python-pip
    python-dbus
    python-gobject
    ripgrep
    git
    tree-sitter
)

MISSING_PKGS=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! pacman -Qi "$pkg" &>/dev/null; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo_info "Installing: ${MISSING_PKGS[*]}"
    if command -v yay &>/dev/null; then
        yay -S --needed --noconfirm "${MISSING_PKGS[@]}"
    elif command -v sudo &>/dev/null; then
        sudo pacman -S --needed --noconfirm "${MISSING_PKGS[@]}"
    else
        echo_err "Cannot install packages. Please install manually:"
        echo "  sudo pacman -S ${MISSING_PKGS[*]}"
        exit 1
    fi
else
    echo_ok "All system packages already installed"
fi

# ── Step 2: Python Dependencies ──────────────────
echo_info "Step 2/6: Installing Python dependencies..."

cd "$AGENT_DIR"

if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --break-system-packages 2>/dev/null || \
    pip install -r requirements.txt --user 2>/dev/null || {
        echo_warn "pip install failed. Trying with --user flag..."
        pip install --user -r requirements.txt
    }
    echo_ok "Python dependencies installed"
else
    echo_warn "requirements.txt not found in $AGENT_DIR"
fi

cd "$PROJECT_DIR"

# ── Step 3: Install Plasmoid ─────────────────────
echo_info "Step 3/6: Installing plasmoid..."

if command -v kpackagetool6 &>/dev/null; then
    # Remove old version if present
    kpackagetool6 --remove org.kde.plasma.ai-agent-panel 2>/dev/null || true

    # Install
    kpackagetool6 --install "$PLASMOID_DIR" --type Plasma/Applet
    echo_ok "Plasmoid installed via kpackagetool6"
else
    echo_warn "kpackagetool6 not found. Manual install:"
    echo "  cp -r $PLASMOID_DIR ~/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel"
    mkdir -p ~/.local/share/plasma/plasmoids/
    cp -r "$PLASMOID_DIR" ~/.local/share/plasma/plasmoids/org.kde.plasma.ai-agent-panel
    echo_ok "Plasmoid copied manually"
fi

# ── Step 4: Systemd User Service ─────────────────
echo_info "Step 4/6: Creating systemd user service..."

mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_DIR/kde-ai-agent.service" << 'SERVICEOF'
[Unit]
Description=KDE AI Agent Backend
After=network.target graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m agent.main
WorkingDirectory=%h/.local/share/kde-ai-agent
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=DISPLAY=:0

[Install]
WantedBy=graphical-session.target
SERVICEOF

# Copy agent code to service location
mkdir -p ~/.local/share/kde-ai-agent/agent
cp -r "$AGENT_DIR"/* ~/.local/share/kde-ai-agent/agent/

systemctl --user daemon-reload
systemctl --user enable kde-ai-agent.service
systemctl --user start kde-ai-agent.service

echo_ok "Systemd service created and started"

# ── Step 5: Default Config ───────────────────────
echo_info "Step 5/6: Creating default config..."

mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
    python3 -c "
import json, os
config = {
    'provider': 'anthropic',
    'model': 'claude-sonnet-4-20250514',
    'api_key': '',
    'ollama_host': 'http://localhost:11434',
    'ollama_model': 'llama3.2',
    'llama_host': 'http://localhost:8080',
    'llama_model': 'local-model',
    'max_tokens': 8192,
    'max_input_tokens': 100000,
    'temperature': 0.7,
    'working_dir': os.path.expanduser('~'),
    'openobserve_endpoint': '',
    'openobserve_stream': 'ai-agent-events',
}
with open('$CONFIG_DIR/config.json', 'w') as f:
    json.dump(config, f, indent=2)
    f.write('\n')
"
    echo_ok "Default config created at $CONFIG_DIR/config.json"
else
    echo_ok "Config already exists at $CONFIG_DIR/config.json"
fi

# ── Step 6: NVIDIA Wayland Setup ──────────────────
echo_info "Step 6/6: Checking NVIDIA Wayland configuration..."

# Check if NVIDIA GPU is present
if lspci 2>/dev/null | grep -qi "nvidia"; then
    echo_info "NVIDIA GPU detected — configuring Wayland env..."

    # Check if libva-nvidia-driver is installed
    if ! pacman -Qi libva-nvidia-driver &>/dev/null; then
        echo_warn "libva-nvidia-driver not found. Installing..."
        sudo pacman -S --noconfirm libva-nvidia-driver 2>/dev/null || \
            echo_warn "Failed to install libva-nvidia-driver. Install manually: sudo pacman -S libva-nvidia-driver"
    fi

    # KEY FIX: GSK_RENDERER=ngl — forces GTK4 OpenGL renderer instead of DMA-BUF
    # Without this, Tauri/GTK4 crashes with "Error 71 (Protocol error)" on NVIDIA
    if [ ! -f "$HOME/.config/environment.d/gsk.conf" ]; then
        mkdir -p "$HOME/.config/environment.d"
        echo 'GSK_RENDERER=ngl' > "$HOME/.config/environment.d/gsk.conf"
        echo_ok "Created ~/.config/environment.d/gsk.conf (GSK_RENDERER=ngl)"
    else
        echo_ok "gsk.conf already exists"
    fi

    # Add NVIDIA Wayland env vars to /etc/environment if not present
    if ! grep -q "GSK_RENDERER" /etc/environment 2>/dev/null; then
        echo 'GSK_RENDERER=ngl' | sudo tee -a /etc/environment > /dev/null
        echo_ok "Added GSK_RENDERER=ngl to /etc/environment"
    else
        echo_ok "GSK_RENDERER already in /etc/environment"
    fi

    if ! grep -q "NVD_BACKEND" /etc/environment 2>/dev/null; then
        echo 'NVD_BACKEND=direct' | sudo tee -a /etc/environment > /dev/null
        echo_ok "Added NVD_BACKEND=direct to /etc/environment"
    else
        echo_ok "NVD_BACKEND already in /etc/environment"
    fi

    if ! grep -q "GDK_BACKEND=wayland" /etc/environment 2>/dev/null; then
        echo 'GDK_BACKEND=wayland' | sudo tee -a /etc/environment > /dev/null
        echo_ok "Added GDK_BACKEND=wayland to /etc/environment"
    else
        echo_ok "GDK_BACKEND already in /etc/environment"
    fi

    echo_ok "NVIDIA Wayland setup complete"
    echo ""
    echo_info "NOTE: Log out and back in for environment.d changes to take effect."
    echo_info "Or run immediately: export GSK_RENDERER=ngl NVD_BACKEND=direct GDK_BACKEND=wayland"
else
    echo_ok "No NVIDIA GPU detected — skipping NVIDIA Wayland setup"
fi

# ── Step 7: Setup Instructions ───────────────────
echo ""
echo "================================================"
echo "  Installation Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Set your API key:"
echo "     Edit ~/.config/kde-ai-agent/config.json"
echo "     Set \"api_key\" to your Anthropic API key"
echo "     Or switch to Ollama: set \"provider\" to \"ollama\""
echo ""
echo "  2. Add the plasmoid to your panel:"
echo "     Right-click panel → Add Widgets → AI Agent Panel"
echo "     Or run: plasmashell --replace &"
echo ""
echo "  3. Test the D-Bus service:"
echo "     qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.GetStatus"
echo ""
echo "  4. If using Ollama, install and start it:"
echo "     pacman -S ollama"
echo "     systemctl --user enable --now ollama"
echo "     ollama pull llama3.2"
echo ""
echo "  5. Launch Tauri with Wayland support:"
echo "     ./scripts/tauri-wayland.sh"
echo ""
echo "  Service: systemctl --user status kde-ai-agent"
echo "  Logs:    journalctl --user -u kde-ai-agent -f"
echo "  Config:  ~/.config/kde-ai-agent/config.json"
echo ""
echo_ok "Done! Enjoy your AI-powered KDE desktop."
