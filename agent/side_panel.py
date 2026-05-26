#!/usr/bin/env python3
"""
agent/side_panel.py — KDE AI Agent Side Panel Window.

Frameless side panel using PyQt6 + QtDBus.
Positioned on left screen edge. Shows on mouse hover in top-left corner.
Toggle: Ctrl+Shift+A.

Usage:
    python3 -m agent.side_panel [--width 380]

Wayland-safe: uses QThread for edge detection (no QTimer → no GLib re-entrancy).
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from PyQt6.QtCore import (
    QUrl, Qt, QThread, pyqtSignal, pyqtSlot, QObject,
    QMetaObject, Q_ARG,
)
from PyQt6.QtGui import QGuiApplication, QShortcut, QKeySequence
from PyQt6.QtQuick import QQuickWindow
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage

logger = logging.getLogger(__name__)

HOVER_ZONE_SIZE = 50  # px from top-left corner
POLL_INTERVAL = 0.3   # seconds


class CursorWatcher(QThread):
    """Watches cursor position in a separate thread.
    
    Emits signals that are delivered via Qt.QueuedConnection,
    avoiding GLib re-entrancy on Wayland.
    """
    enterZone = pyqtSignal()
    leaveZone = pyqtSignal()

    def __init__(self, zone_size=HOVER_ZONE_SIZE):
        super().__init__()
        self._zone_size = zone_size
        self._running = True
        self._in_zone = False

    def run(self):
        while self._running:
            try:
                pos = QGuiApplication.cursor().pos()
                in_zone = pos.x() <= self._zone_size and pos.y() <= self._zone_size
                if in_zone and not self._in_zone:
                    self._in_zone = True
                    self.enterZone.emit()
                elif not in_zone and self._in_zone:
                    self._in_zone = False
                    self.leaveZone.emit()
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)

    def stop(self):
        self._running = False


class AgentBridge(QObject):
    """Bridge to D-Bus agent — uses polling for status."""

    statusChanged = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._iface = None
        self._connected = False
        self._connect_dbus()

    def _connect_dbus(self):
        bus = QDBusConnection.sessionBus()
        if not bus.isConnected():
            logger.warning("D-Bus session bus not available")
            return
        self._iface = QDBusInterface(
            "org.kde.aiagent", "/org/kde/aiagent", "org.kde.aiagent", bus,
        )
        if not self._iface.isValid():
            logger.warning(f"D-Bus interface not available: {bus.lastError().message()}")
            self._iface = None
            return
        self._connected = True
        logger.info("QtDBus connected to org.kde.aiagent")

    @pyqtSlot(str, str)
    def runTask(self, task, files_json):
        if not self._iface:
            return
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

    # Find SidePanel.qml
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

    # Engine + bridge
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

    # Position window on left side
    screen = app.primaryScreen()
    geo = screen.availableGeometry() if screen else app.primaryScreen().geometry()
    width = args.width
    x = geo.x()
    y = geo.y()

    window.setX(x)
    window.setY(y)
    window.setWidth(width)
    window.setHeight(geo.height())
    window.setFlags(
        Qt.WindowType.FramelessWindowHint |
        Qt.WindowType.WindowStaysOnTopHint |
        Qt.WindowType.Tool
    )
    window.show()

    logger.info(f"Panel: left side, {width}px, pos=({x},{y}), size={width}x{geo.height()}")

    # ── Wayland-safe show/hide via QThread signals ──
    # QTimer on Wayland uses QEventDispatcherGlib → re-entrancy crash.
    # QThread signals are delivered via Qt.QueuedConnection, safe on Wayland.

    def safe_show():
        QMetaObject.invokeMethod(window, "show", Qt.ConnectionType.QueuedConnection)
        QMetaObject.invokeMethod(window, "raise_", Qt.ConnectionType.QueuedConnection)

    def safe_hide():
        QMetaObject.invokeMethod(window, "hide", Qt.ConnectionType.QueuedConnection)

    # Cursor watcher thread
    watcher = CursorWatcher()
    watcher.enterZone.connect(safe_show)
    watcher.leaveZone.connect(safe_hide)
    watcher.start()

    # Global hotkey: Ctrl+Shift+A
    shortcut = QShortcut(QKeySequence("Ctrl+Shift+A"), window)
    def toggle():
        if window.isVisible():
            safe_hide()
        else:
            safe_show()
    shortcut.activated.connect(toggle)

    # Cleanup on exit
    app.aboutToQuit.connect(watcher.stop)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
