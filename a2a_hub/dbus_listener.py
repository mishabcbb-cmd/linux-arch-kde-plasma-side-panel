#!/usr/bin/env python3
"""
a2a_hub_dbus_listener.py — D-Bus signal listener for A2A Hub.

Listens to org.kde.a2ahub signals and writes JSON lines to stdout.
Each line is a complete JSON object that QML can parse via
Plasma5Support.DataSource (executable engine).

Signals monitored:
  • ConversationUpdated(task_id, message_count)
  • NewMessage(task_id, role, content, agent)
  • AgentStatusChanged(agent_name, status)

Usage:
    python3 dbus_listener.py

Output format (one JSON object per line, flushed immediately):
    {"signal": "ConversationUpdated", "task_id": "abc123", "message_count": 5}
    {"signal": "NewMessage", "task_id": "abc123", "role": "assistant", "content": "...", "agent": "owl-coder"}
"""

import json
import signal as sig
import sys
import traceback

try:
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib
except ImportError:
    print(json.dumps({
        "signal": "ErrorOccurred",
        "error": "dbus-python or gi not installed"
    }))
    sys.exit(1)

BUS_NAME = "org.kde.a2ahub"
OBJECT_PATH = "/org/kde/a2ahub"
INTERFACE = "org.kde.a2ahub"


def on_conversation_updated(task_id, message_count):
    """Handle ConversationUpdated signal."""
    print(json.dumps({
        "signal": "ConversationUpdated",
        "task_id": str(task_id),
        "message_count": int(message_count),
    }), flush=True)


def on_new_message(task_id, role, content, agent):
    """Handle NewMessage signal."""
    print(json.dumps({
        "signal": "NewMessage",
        "task_id": str(task_id),
        "role": str(role),
        "content": str(content)[:500],  # limit size
        "agent": str(agent),
    }), flush=True)


def on_agent_status_changed(agent_name, status):
    """Handle AgentStatusChanged signal."""
    print(json.dumps({
        "signal": "AgentStatusChanged",
        "agent_name": str(agent_name),
        "status": str(status),
    }), flush=True)


def main():
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    session_bus = dbus.SessionBus()

    # Check if service is available
    try:
        session_bus.get_object(BUS_NAME, OBJECT_PATH)
    except dbus.exceptions.DBusException:
        print(json.dumps({
            "signal": "ErrorOccurred",
            "error": f"Cannot connect to {BUS_NAME}. Is a2a_hub_dbus.py running?"
        }), flush=True)
        sys.exit(1)

    # Connect to signals
    session_bus.add_signal_receiver(
        on_conversation_updated,
        signal_name="ConversationUpdated",
        dbus_interface=INTERFACE,
        bus_name=BUS_NAME,
        path=OBJECT_PATH,
    )
    session_bus.add_signal_receiver(
        on_new_message,
        signal_name="NewMessage",
        dbus_interface=INTERFACE,
        bus_name=BUS_NAME,
        path=OBJECT_PATH,
    )
    session_bus.add_signal_receiver(
        on_agent_status_changed,
        signal_name="AgentStatusChanged",
        dbus_interface=INTERFACE,
        bus_name=BUS_NAME,
        path=OBJECT_PATH,
    )

    print(json.dumps({
        "signal": "Connected",
        "bus_name": BUS_NAME,
        "status": "listening",
    }), flush=True)

    # Handle signals
    def signal_handler(s, frame):
        print(json.dumps({"signal": "Disconnected"}), flush=True)
        sys.exit(0)

    sig.signal(sig.SIGINT, signal_handler)
    sig.signal(sig.SIGTERM, signal_handler)

    # Run main loop
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
