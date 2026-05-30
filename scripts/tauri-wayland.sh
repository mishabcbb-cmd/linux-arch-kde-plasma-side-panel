#!/usr/bin/env bash
# scripts/tauri-wayland.sh — Launch Tauri app with NVIDIA Wayland fixes
#
# Research: docs/tauri-nvidia-wayland-research.md (40 sources)
#
# Fixes applied:
#   1. __NV_DISABLE_EXPLICIT_SYNC=1 — disables explicit sync in NVIDIA EGL-Wayland
#      (fixes "Error 71 Protocol error" / "explicit sync is used, but no acquire point is set")
#   2. GSK_RENDERER=ngl — forces GTK4 OpenGL renderer (not Vulkan which is broken on NVIDIA)
#   3. NVD_BACKEND=direct — VA-API hardware video acceleration via nvidia-vaapi-driver
#   4. GDK_BACKEND=wayland — native Wayland (no XWayland fallback)
#
# Note: Rust code in lib.rs also auto-detects NVIDIA + Wayland and sets these vars
#       if they're not already set. This script provides explicit overrides.
#
# Usage:
#   ./scripts/tauri-wayland.sh           # debug build
#   ./scripts/tauri-wayland.sh --release # release build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ── NVIDIA Wayland env ──────────────────────────────
export __NV_DISABLE_EXPLICIT_SYNC=1
export GSK_RENDERER=ngl
export NVD_BACKEND=direct
export GDK_BACKEND=wayland

# ── Launch ──────────────────────────────────────────
MODE="${1:-}"
echo "🚀 Launching Tauri with NVIDIA Wayland fixes..."
echo "   __NV_DISABLE_EXPLICIT_SYNC=$__NV_DISABLE_EXPLICIT_SYNC"
echo "   GSK_RENDERER=$GSK_RENDERER"
echo "   NVD_BACKEND=$NVD_BACKEND"
echo "   GDK_BACKEND=$GDK_BACKEND"

if [[ "$MODE" == "--release" ]]; then
    cargo tauri build 2>/dev/null && "./src-tauri/target/release/ai-agent-panel"
else
    cargo tauri dev
fi
