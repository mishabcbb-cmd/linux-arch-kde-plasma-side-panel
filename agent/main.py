"""
agent/main.py — D-Bus service entry point for the KDE AI Agent.

Exposes over D-Bus:
  • run_task(task_str, file_context) -> bool
  • stop_task() -> void
  • get_status() -> dict
  • provide_user_response(response) -> void

Also initializes:
  • D-Bus session bus connection with org.kde.aiagent service name
  • OpenObserve log sink for structured event streaming
  • Provider from config (~/.config/kde-ai-agent/config.json)
  • Falls back to Unix socket if D-Bus is unavailable

Signals emitted on D-Bus:
  • StatusChanged(status: string)
  • TokenStream(content: string, msg_type: string)
  • ToolCallStarted(tool_name: string, input: string)
  • ToolCallResult(tool_name: string, success: bool, output: string)
  • TaskComplete(data: string)
  • ErrorOccurred(error: string)
  • QuestionAsked(question: string, options: string)
"""

import json
import logging
import os
import signal
import socket
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ============================================================================
# Logging Setup
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),
    ],
)
logger = logging.getLogger("ai-agent")


# ============================================================================
# Config Loading
# ============================================================================

CONFIG_DIR = Path.home() / ".config" / "kde-ai-agent"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": "",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.2",
    "max_tokens": 8192,
    "max_input_tokens": 100_000,
    "temperature": 0.7,
    "working_dir": str(Path.home()),
    "openobserve_endpoint": "",
    "openobserve_stream": "ai-agent-events",
    "dbus_service_name": "org.kde.aiagent",
    "dbus_object_path": "/org/kde/aiagent",
    "fallback_socket": str(Path.home() / ".local" / "share" / "kde-ai-agent" / "agent.sock"),
}


def load_config() -> Dict[str, Any]:
    """Load config from ~/.config/kde-ai-agent/config.json, merging with defaults."""
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                user_config = json.load(f)
            config.update(user_config)
            logger.info(f"Loaded config from {CONFIG_PATH}")
        except Exception as exc:
            logger.warning(f"Failed to load config: {exc}, using defaults")
    return config


def save_config(config: Dict[str, Any]) -> None:
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Config saved to {CONFIG_PATH}")


# ============================================================================
# OpenObserve Log Sink
# ============================================================================


class OpenObserveSink:
    """Streams agent events to an OpenObserve instance for real-time observability.

    Every tool call, LLM response, and error gets sent as structured JSON to
    the configured OpenObserve stream, enabling SQL queries and dashboards.
    """

    def __init__(self, endpoint: str, stream_name: str = "ai-agent-events"):
        self.endpoint = endpoint.rstrip("/") if endpoint else ""
        self.stream_name = stream_name
        self.enabled = bool(self.endpoint)
        self._buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._flush_interval = 5  # seconds
        self._max_buffer = 100
        if self.enabled:
            self._start_flush_timer()

    def send(self, event_dict: Dict[str, Any]) -> None:
        """Queue an event for sending to OpenObserve."""
        if not self.enabled:
            return
        with self._lock:
            self._buffer.append(event_dict)
            if len(self._buffer) >= self._max_buffer:
                self._flush()

    def _flush(self) -> None:
        """Send buffered events to OpenObserve."""
        if not self._buffer or not self.enabled:
            return
        events = list(self._buffer)
        self._buffer.clear()
        try:
            import urllib.request
            payload = json.dumps(events).encode("utf-8")
            url = f"{self.endpoint}/api/{self.stream_name}/_json"
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as exc:
            logger.debug(f"OpenObserve send failed (non-fatal): {exc}")

    def _start_flush_timer(self) -> None:
        """Periodically flush buffered events."""
        def _timer():
            while self.enabled:
                threading.Event().wait(self._flush_interval)
                with self._lock:
                    self._flush()
        t = threading.Thread(target=_timer, daemon=True)
        t.start()

    def close(self) -> None:
        self.enabled = False
        self._flush()


# ============================================================================
# D-Bus Service
# ============================================================================

dbus_available = False
try:
    import dbus
    import dbus.service
    import dbus.mainloop.glib
    from gi.repository import GLib  # type: ignore
    dbus_available = True
except ImportError:
    logger.warning("dbus-python or gi not available, falling back to Unix socket")


if dbus_available:
    class AIAgentDBusService(dbus.service.Object):
        """D-Bus service exposing the agent to QML/KDE plasmoid."""

        def __init__(self, agent_loop, config: Dict[str, Any]):
            self._agent = agent_loop
            bus_name = config.get("dbus_service_name", "org.kde.aiagent")
            object_path = config.get("dbus_object_path", "/org/kde/aiagent")

            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self._bus = dbus.SessionBus()
            bus = dbus.service.BusName(bus_name, self._bus)
            super().__init__(bus, object_path)

            # Wire signal handler to D-Bus signals
            self._agent.set_signal_handler(self._emit_dbus_signal)
            self._agent.set_dbus_signal(self._emit_dbus_signal)

        @dbus.service.method(
            "org.kde.aiagent",
            in_signature="sas", out_signature="b",
        )
        def RunTask(self, task: str, file_context: List[str]) -> bool:
            """Start executing a task. Returns True if started successfully."""
            logger.info(f"D-Bus RunTask: {task[:100]}...")
            thread = threading.Thread(
                target=self._agent.run_task,
                args=(task, file_context),
                daemon=True,
            )
            thread.start()
            return True

        @dbus.service.method("org.kde.aiagent", in_signature="", out_signature="")
        def StopTask(self) -> None:
            """Stop the currently running task."""
            logger.info("D-Bus StopTask")
            self._agent.stop_task()

        @dbus.service.method("org.kde.aiagent", in_signature="", out_signature="s")
        def GetStatus(self) -> str:
            """Get current agent status as JSON."""
            status = self._agent.get_status()
            return json.dumps(status)

        @dbus.service.method("org.kde.aiagent", in_signature="s", out_signature="")
        def ProvideUserResponse(self, response: str) -> None:
            """Provide user's answer to an ask_user question."""
            self._agent.provide_user_response(response)

        @dbus.service.method("org.kde.aiagent", in_signature="", out_signature="")
        def TogglePanel(self) -> None:
            """Toggle the side panel visibility (called from KWin script)."""
            logger.info("D-Bus TogglePanel")
            import subprocess
            import os
            panel_script = os.path.join(
                os.path.dirname(__file__), "side_panel.py"
            )
            subprocess.Popen(
                [sys.executable, panel_script, "--width", "380"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        @dbus.service.signal("org.kde.aiagent", signature="ss")
        def StatusChanged(self, status: str, data: str) -> None:
            pass

        @dbus.service.signal("org.kde.aiagent", signature="ss")
        def TokenStream(self, content: str, msg_type: str) -> None:
            pass

        @dbus.service.signal("org.kde.aiagent", signature="sss")
        def ToolCallStarted(self, tool_name: str, input_json: str, iteration: str) -> None:
            pass

        @dbus.service.signal("org.kde.aiagent", signature="ssbs")
        def ToolCallResult(self, tool_name: str, output: str, success: bool, error: str) -> None:
            pass

        @dbus.service.signal("org.kde.aiagent", signature="s")
        def TaskComplete(self, data: str) -> None:
            pass

        @dbus.service.signal("org.kde.aiagent", signature="s")
        def ErrorOccurred(self, error: str) -> None:
            pass

        @dbus.service.signal("org.kde.aiagent", signature="ss")
        def QuestionAsked(self, question: str, options_json: str) -> None:
            pass

        def _emit_dbus_signal(self, signal_type, data: Dict[str, Any]) -> None:
            """Route agent signals to D-Bus signals."""
            try:
                from .agent_loop import AgentSignalType

                if signal_type == AgentSignalType.STATUS_CHANGED:
                    self.StatusChanged(data.get("status", "unknown"), json.dumps(data))
                elif signal_type == AgentSignalType.TOKEN_STREAM:
                    self.TokenStream(data.get("content", ""), data.get("type", "thought"))
                elif signal_type == AgentSignalType.TOOL_CALL_START:
                    self.ToolCallStarted(
                        data.get("tool_name", ""),
                        json.dumps(data.get("input", {})),
                        str(data.get("iteration", 0)),
                    )
                elif signal_type == AgentSignalType.TOOL_CALL_RESULT:
                    self.ToolCallResult(
                        data.get("tool_name", ""),
                        data.get("output", "")[:2000],
                        data.get("success", False),
                        data.get("error", ""),
                    )
                elif signal_type == AgentSignalType.TASK_COMPLETE:
                    self.TaskComplete(json.dumps(data))
                elif signal_type == AgentSignalType.ERROR:
                    self.ErrorOccurred(data.get("error", "Unknown error"))
                elif signal_type == AgentSignalType.QUESTION_ASKED:
                    self.QuestionAsked(
                        data.get("question", ""),
                        json.dumps(data.get("options", [])),
                    )
            except Exception as exc:
                logger.error(f"D-Bus signal emission error: {exc}")


# ============================================================================
# Unix Socket Fallback (when D-Bus is unavailable)
# ============================================================================


class UnixSocketServer:
    """Unix domain socket fallback for when D-Bus is not available."""

    def __init__(self, agent_loop, socket_path: str):
        self._agent = agent_loop
        self._socket_path = Path(socket_path)
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        self._server_socket: Optional[socket.socket] = None
        self._running = False

    def start(self) -> None:
        """Start the Unix socket server."""
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(str(self._socket_path))
        self._server_socket.listen(5)
        self._running = True
        logger.info(f"Unix socket listening on {self._socket_path}")

        while self._running:
            try:
                conn, _ = self._server_socket.accept()
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
            except Exception as exc:
                if self._running:
                    logger.error(f"Socket accept error: {exc}")

    def _handle_client(self, conn: socket.socket) -> None:
        """Handle a client connection."""
        try:
            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            command = json.loads(data.decode("utf-8"))
            response = self._execute_command(command)
            conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except Exception as exc:
            logger.error(f"Socket client error: {exc}")
        finally:
            conn.close()

    def _execute_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command received over the socket."""
        cmd = command.get("command", "")
        if cmd == "run_task":
            thread = threading.Thread(
                target=self._agent.run_task,
                args=(command.get("task", ""), command.get("file_context", [])),
                daemon=True,
            )
            thread.start()
            return {"status": "started"}
        elif cmd == "stop_task":
            self._agent.stop_task()
            return {"status": "stopped"}
        elif cmd == "get_status":
            return self._agent.get_status()
        elif cmd == "provide_user_response":
            self._agent.provide_user_response(command.get("response", ""))
            return {"status": "ok"}
        else:
            return {"error": f"Unknown command: {cmd}"}

    def stop(self) -> None:
        self._running = False
        if self._server_socket:
            self._server_socket.close()
        if self._socket_path.exists():
            self._socket_path.unlink()


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Initialize and run the AI Agent service."""
    print("=" * 60)
    print("  KDE AI Agent Service")
    print("  D-Bus: org.kde.aiagent  |  Config: ~/.config/kde-ai-agent/")
    print("=" * 60)

    # Load config
    config = load_config()

    # Ensure config directory exists with defaults on first run
    if not CONFIG_PATH.exists():
        save_config(config)
        print(f"✓ Created default config at {CONFIG_PATH}")
        print("  Edit this file to set your API key and preferences.")

    # Lazy import agent modules (only after config is loaded)
    from .agent_loop import AgentLoop, AgentSignalType  # noqa: F811

    # Create agent
    agent = AgentLoop(config)

    # Setup OpenObserve log sink
    oo_endpoint = config.get("openobserve_endpoint", "")
    oo_sink = OpenObserveSink(
        endpoint=oo_endpoint,
        stream_name=config.get("openobserve_stream", "ai-agent-events"),
    )

    def event_handler(event):
        """Route agent events to OpenObserve."""
        oo_sink.send(event.to_dict())

    agent.set_event_handler(event_handler)

    # Start service (D-Bus or Unix socket)
    if dbus_available:
        logger.info("Starting D-Bus service...")
        try:
            dbus_service = AIAgentDBusService(agent, config)
            print(f"✓ D-Bus service registered: {config['dbus_service_name']}")
            print(f"  Object path: {config['dbus_object_path']}")

            # Start GLib main loop
            loop = GLib.MainLoop()
            loop.run()
        except KeyboardInterrupt:
            print("\nShutting down...")
        except Exception as exc:
            logger.error(f"D-Bus initialization failed: {exc}")
            print(f"✗ D-Bus failed: {exc}")
            print("  Falling back to Unix socket...")
    else:
        # Fallback: Unix socket
        socket_path = config.get("fallback_socket", str(Path.home() / ".local/share/kde-ai-agent/agent.sock"))
        socket_server = UnixSocketServer(agent, socket_path)
        try:
            socket_server.start()
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            socket_server.stop()

    oo_sink.close()


if __name__ == "__main__":
    main()
