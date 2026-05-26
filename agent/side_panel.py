#!/usr/bin/env python3
"""
agent/side_panel.py — KDE AI Agent Side Panel Window.

Frameless side panel using PyQt6 + QtDBus.
Positioned on left screen edge. Shows on mouse hover in top-left corner.
Toggle: Ctrl+Shift+A.

Wayland-safe: uses self-pipe trick (QSocketNotifier) instead of QTimer/QThread
signals to avoid GLib re-entrancy crash from Qt6 Wayland compositor roundtrips.
"""

import argparse
import json
import logging
import os
import select
import subprocess
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import (
    QUrl, Qt, QSocketNotifier, QObject, pyqtSlot,
)
from PyQt6.QtGui import QGuiApplication, QShortcut, QKeySequence
from PyQt6.QtQuick import QQuickWindow
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

logger = logging.getLogger(__name__)

HOVER_ZONE_SIZE = 50
POLL_INTERVAL = 0.3


def get_cursor_pos():
    """Get cursor position using xdotool (no Qt API = no GLib crash)."""
    try:
        out = subprocess.check_output(
            ["xdotool", "getmouselocation", "--shell"],
            stderr=subprocess.DEVNULL, timeout=1,
        ).decode()
        x = y = None
        for line in out.splitlines():
            if line.startswith("X="):
                x = int(line.split("=")[1])
            elif line.startswith("Y="):
                y = int(line.split("=")[1])
        return x, y
    except Exception:
        return None, None


class AgentBridge(QObject):
    """Bridge to D-Bus agent."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._iface = None
        self._connect_dbus()

    def _connect_dbus(self):
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            return
        self._iface = QDBusInterface(
            "org.kde.aiagent", "/org/kde/aiagent", "org.kde.aiagent", bus,
        )
        if self._iface.isValid():
            logger.info("QtDBus connected")

    @pyqtSlot(str, str)
    def runTask(self, task, files_json):
        if self._iface:
            files = json.loads(files_json) if files_json else []
            self._iface.call("RunTask", task, files)

    @pyqtSlot()
    def stopTask(self):
        if self._iface:
            self._iface.call("StopTask")

    @pyqtSlot(result=str)
    def getStatus(self):
        if not self._iface:
            return json.dumps({"status": "disconnected"})
        reply = self._iface.call("GetStatus")
        if reply.type() == QDBusMessage.MessageType.ReplyMessage and reply.arguments():
            return str(reply.arguments()[0])
        return json.dumps({"status": "unknown"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=380)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("KDE AI Agent Panel")

    here = Path(__file__).parent
    qml_path = next(
        (p for p in [
            here.parent / "plasmoid" / "ai-agent-panel" / "contents" / "ui" / "SidePanel.qml",
            Path.home() / ".local" / "share" / "plasma" / "plasmoids" / "org.kde.plasma.ai-agent-panel" / "contents" / "ui" / "SidePanel.qml",
        ] if p.exists()),
        None
    )
    if not qml_path:
        logger.error("SidePanel.qml not found")
        sys.exit(1)

    engine = QQmlApplicationEngine()
    bridge = AgentBridge()
    engine.rootContext().setContextProperty("agentBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        logger.error("Failed to load QML")
        sys.exit(1)

    window = engine.rootObjects()[0]
    if not isinstance(window, QQuickWindow):
        logger.error("Root object is not a window")
        sys.exit(1)

    screen = app.primaryScreen()
    geo = screen.availableGeometry() if screen else app.primaryScreen().geometry()
    width = args.width

    window.setX(geo.x())
    window.setY(geo.y())
    window.setWidth(width)
    window.setHeight(geo.height())
    window.setFlags(
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint |
        Qt.WindowType.Tool
    )
    window.show()

    logger.info(f"Panel: left side, {width}px, size={width}x{geo.height()}")

    # ── Self-pipe trick for Wayland-safe show/hide ──
    # QSocketNotifier uses poll(), NOT GLib timers.
    # This avoids the Qt6 Wayland GLib re-entrancy crash entirely.
    r_fd, w_fd = os.pipe()
    os.set_blocking(w_fd, False)

    def cursor_poller():
        """Thread: polls cursor via xdotool, writes to pipe."""
        in_zone = False
        while True:
            try:
                x, y = get_cursor_pos()
                if x is not None:
                    now_in = x <= HOVER_ZONE_SIZE and y <= HOVER_ZONE_SIZE
                    if now_in and not in_zone:
                        in_zone = True
                        os.write(w_fd, b"show\n")
                    elif not now_in and in_zone:
                        in_zone = False
                        os.write(w_fd, b"hide\n")
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)

    poller_thread = threading.Thread(target=cursor_poller, daemon=True)
    poller_thread.start()

    # ── Slide in/out via position (no setVisible) ──
    # setVisible(False) on Wayland breaks subsequent setVisible(True).
    # Solution: window is always visible, slides off-screen to "hide".
    panel_x = geo.x()
    hidden_x = geo.x() - width - 10  # off-screen left

    def slide_in():
        window.setX(panel_x)
        window.raise_()
        window.requestActivate()

    def slide_out():
        window.setX(hidden_x)

    # Start hidden
    window.setX(hidden_x)

    def on_pipe_ready(fd):
        try:
            data = os.read(fd, 4096)
            if b"show" in data:
                slide_in()
            elif b"hide" in data:
                slide_out()
        except Exception:
            pass

    notifier = QSocketNotifier(r_fd, QSocketNotifier.Type.Read)
    notifier.activated.connect(lambda fd: on_pipe_ready(fd))

    # Global hotkey: Ctrl+Shift+A
    shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), window)
    def toggle():
        if window.x() == panel_x:
            slide_out()
        else:
            slide_in()
    shortcut.activated.connect(toggle)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
