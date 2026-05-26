#!/usr/bin/env python3
"""
agent/side_panel.py — KDE AI Agent Side Panel Window.

Configurable frameless side panel with:
  - Left or right positioning
  - Global hotkey (Ctrl+Shift+A) to toggle
  - Auto-show on mouse hover at screen edge
  - D-Bus communication with agent backend

Usage:
    python3 -m agent.side_panel [--side left|right] [--width 380]

Requires: PyQt6, PyQt6.QtQuick, PyQt6.QtGui, keybinder (optional)
"""

import argparse
import json
import logging
import os
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QUrl, Qt, QTimer, pyqtSignal, pyqtSlot, QObject, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QGuiApplication, QScreen, QAction, QKeySequence, QMouseEvent
from PyQt6.QtQuick import QQuickWindow
from PyQt6.QtQml import QQmlApplicationEngine

# D-Bus integration
try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    HAS_DBUS = True
except ImportError:
    HAS_DBUS = False

logger = logging.getLogger(__name__)

PANEL_WIDTH = 380
PANEL_SIDE = "left"  # "left" or "right"
AUTO_SHOW = True
AUTO_SHOW_EDGE = 5  # pixels from edge to trigger
HIDE_ON_FOCUS_LOST = True
ANIMATION_DURATION = 200  # ms


class AgentBridge(QObject):
    """Bridge between D-Bus agent and QML UI."""

    statusChanged = pyqtSignal(str)
    tokenStream = pyqtSignal(str, str)
    toolCallStarted = pyqtSignal(str, str)
    toolCallResult = pyqtSignal(str, str, bool, str)
    taskComplete = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    questionAsked = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proxy = None
        self._connected = False
        self._connect_dbus()

    def _connect_dbus(self):
        if not HAS_DBUS:
            logger.warning("D-Bus not available, agent bridge disabled")
            return
        try:
            DBusGMainLoop(set_as_default=True)
            bus = dbus.SessionBus()
            proxy = bus.get_object("org.kde.aiagent", "/org/kde/aiagent")
            self._proxy = dbus.Interface(proxy, "org.kde.aiagent")
            self._connected = True
            logger.info("Connected to D-Bus agent service")

            bus.add_signal_receiver(self._on_status_changed, signal_name="StatusChanged", dbus_interface="org.kde.aiagent")
            bus.add_signal_receiver(self._on_token_stream, signal_name="TokenStream", dbus_interface="org.kde.aiagent")
            bus.add_signal_receiver(self._on_tool_call_started, signal_name="ToolCallStarted", dbus_interface="org.kde.aiagent")
            bus.add_signal_receiver(self._on_tool_call_result, signal_name="ToolCallResult", dbus_interface="org.kde.aiagent")
            bus.add_signal_receiver(self._on_task_complete, signal_name="TaskComplete", dbus_interface="org.kde.aiagent")
            bus.add_signal_receiver(self._on_error, signal_name="ErrorOccurred", dbus_interface="org.kde.aiagent")
            bus.add_signal_receiver(self._on_question, signal_name="QuestionAsked", dbus_interface="org.kde.aiagent")
        except Exception as exc:
            logger.warning(f"D-Bus connection failed: {exc}")

    def _on_status_changed(self, status): self.statusChanged.emit(str(status))
    def _on_token_stream(self, content, msg_type): self.tokenStream.emit(str(content), str(msg_type))
    def _on_tool_call_started(self, tool_name, input_json): self.toolCallStarted.emit(str(tool_name), str(input_json))
    def _on_tool_call_result(self, tool_name, output, success, error): self.toolCallResult.emit(str(tool_name), str(output), bool(success), str(error))
    def _on_task_complete(self, data): self.taskComplete.emit(str(data))
    def _on_error(self, error): self.errorOccurred.emit(str(error))
    def _on_question(self, question, options_json): self.questionAsked.emit(str(question), str(options_json))

    @pyqtSlot(str, str)
    def runTask(self, task: str, files_json: str):
        if not self._connected:
            self.errorOccurred.emit("Agent not connected")
            return
        try:
            files = json.loads(files_json) if files_json else []
            self._proxy.RunTask(task, files)
        except Exception as exc:
            self.errorOccurred.emit(f"Failed to run task: {exc}")

    @pyqtSlot()
    def stopTask(self):
        if self._connected:
            try: self._proxy.StopTask()
            except Exception as exc: logger.warning(f"Stop task failed: {exc}")

    @pyqtSlot(str)
    def provideResponse(self, response: str):
        if self._connected:
            try: self._proxy.ProvideUserResponse(response)
            except Exception as exc: logger.warning(f"Provide response failed: {exc}")

    @pyqtSlot(result=str)
    def getStatus(self) -> str:
        if not self._connected: return json.dumps({"status": "disconnected"})
        try: return str(self._proxy.GetStatus())
        except Exception as exc: return json.dumps({"status": "error", "error": str(exc)})


class SidePanelWindow(QQuickWindow):
    """Frameless side panel window with edge detection and animation."""

    def __init__(self, engine, side="left", width=380):
        super().__init__(engine)
        self._side = side
        self._panel_width = width
        self._hidden = False
        self._edge_monitor = QTimer()
        self._edge_monitor.timeout.connect(self._check_edge)
        self._edge_monitor.start(200)  # check every 200ms

        # Animation for show/hide
        self._animation = QPropertyAnimation(self, b"pos")
        self._animation.setDuration(ANIMATION_DURATION)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Global hotkey via QAction
        self._toggle_action = QAction(self)
        self._toggle_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self._toggle_action.triggered.connect(self.toggle)
        self.addAction(self._toggle_action)

    def set_side(self, side):
        self._side = side
        self._reposition()

    def _reposition(self):
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        if self._side == "left":
            self.setX(geo.x())
        else:
            self.setX(geo.x() + geo.width() - self._panel_width)
        self.setY(geo.y())
        self.setWidth(self._panel_width)
        self.setHeight(geo.height())

    def toggle(self):
        if self._hidden:
            self.show_panel()
        else:
            self.hide_panel()

    def show_panel(self):
        self._reposition()
        self.show()
        self._hidden = False
        self.raise_()
        self.activateWindow()

    def hide_panel(self):
        # Animate slide out
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        target_x = geo.x() - self._panel_width if self._side == "left" else geo.x() + geo.width()
        self._animation.setStartValue(self.pos())
        self._animation.setEndValue(Qt.QPoint(int(target_x), int(self.y())))
        self._animation.finished.connect(self._on_hide_finished)
        self._animation.start()

    def _on_hide_finished(self):
        self.hide()
        self._hidden = True
        self._animation.finished.disconnect(self._on_hide_finished)

    def _check_edge(self):
        if not AUTO_SHOW or not self._hidden:
            return
        cursor = QGuiApplication.cursor().pos()
        screen = QGuiApplication.primaryScreen()
        if not screen:
            return
        geo = screen.availableGeometry()
        if self._side == "left":
            if cursor.x() <= geo.x() + AUTO_SHOW_EDGE:
                self.show_panel()
        else:
            if cursor.x() >= geo.x() + geo.width() - AUTO_SHOW_EDGE:
                self.show_panel()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if HIDE_ON_FOCUS_LOST and not self._hidden:
            self.hide_panel()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.hide_panel()
        super().keyPressEvent(event)


def main():
    parser = argparse.ArgumentParser(description="KDE AI Agent Side Panel")
    parser.add_argument("--side", choices=["left", "right"], default="left", help="Panel side")
    parser.add_argument("--width", type=int, default=380, help="Panel width in pixels")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("KDE AI Agent Panel")
    app.setOrganizationName("kde-ai-agent")

    # Find SidePanel.qml
    here = Path(__file__).parent
    search_paths = [
        here.parent / "plasmoid" / "ai-agent-panel" / "contents" / "ui" / "SidePanel.qml",
        Path.home() / ".local" / "share" / "plasma" / "plasmoids" / "org.kde.plasma.ai-agent-panel" / "contents" / "ui" / "SidePanel.qml",
        here / "SidePanel.qml",
    ]
    qml_path = None
    for p in search_paths:
        if p.exists():
            qml_path = p
            break

    if not qml_path:
        logger.error("SidePanel.qml not found")
        sys.exit(1)

    logger.info(f"Loading {qml_path}")

    # Create engine and bridge
    engine = QQmlApplicationEngine()
    bridge = AgentBridge()
    engine.rootContext().setContextProperty("agentBridge", bridge)

    # Load QML
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        logger.error("Failed to load SidePanel.qml")
        sys.exit(1)

    # Setup window
    for obj in engine.rootObjects():
        if isinstance(obj, QQuickWindow):
            window = SidePanelWindow(engine, side=args.side, width=args.width)
            # Copy QML window properties
            window.setColor(obj.color())
            window.setFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint |
                Qt.WindowType.Tool
            )
            window.show_panel()
            logger.info(f"Side panel created: {args.side} side, {args.width}px, hotkey Ctrl+Shift+A")
            break

    # D-Bus GLib integration
    if HAS_DBUS:
        loop = GLib.MainLoop()
        timer = QTimer()
        timer.timeout.connect(lambda: loop.iteration(False))
        timer.start(10)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
