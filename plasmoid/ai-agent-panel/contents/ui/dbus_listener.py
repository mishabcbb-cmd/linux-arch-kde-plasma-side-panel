#!/usr/bin/env python3
"""
agent/dbus_listener.py — D-Bus signal listener for QML SidePanelWindow.

Listens to org.kde.aiagent signals and writes JSON lines to stdout.
Each line is a complete JSON object that QML can parse via
Plasma5Support.DataSource (executable engine).

Signals monitored:
  • StatusChanged(status, data)
  • TokenStream(content, msg_type)
  • ToolCallStarted(tool_name, input_json, iteration)
  • ToolCallResult(tool_name, output, success, error)
  • TaskComplete(data)
  • ErrorOccurred(error)
  • QuestionAsked(question, options_json)

Usage:
    python3 dbus_listener.py

Output format (one JSON object per line, flushed immediately):
    {"signal": "StatusChanged", "status": "thinking", "data": {...}}
    {"signal": "TokenStream", "content": "Hello", "msg_type": "thought"}
    {"signal": "ToolCallStarted", "tool_name": "read_file", ...}
"""

import json
import os
import signal as sig
import sys
import traceback

# ── D-Bus imports ──
try:
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib
except ImportError:
    print(json.dumps({
        "signal": "ErrorOccurred",
        "error": "dbus-python or gi not installed. Run: pip install dbus-python PyGObject"
    }))
    sys.exit(1)

BUS_NAME = "org.kde.aiagent"
OBJECT_PATH = "/org/kde/aiagent"
INTERFACE = "org.kde.aiagent"

# ── Signal handlers ──

def on_status_changed(status: str, data: str):
    """Handle StatusChanged signal."""
    try:
        parsed = json.loads(data) if data else {}
    except json.JSONDecodeError:
        parsed = {"raw": data}
    _emit({
        "signal": "StatusChanged",
        "status": status,
        "data": parsed,
    })


def on_token_stream(content: str, msg_type: str):
    """Handle TokenStream signal."""
    _emit({
        "signal": "TokenStream",
        "content": content,
        "msg_type": msg_type,
    })


def on_tool_call_started(tool_name: str, input_json: str, iteration: str):
    """Handle ToolCallStarted signal."""
    try:
        inp = json.loads(input_json) if input_json else {}
    except json.JSONDecodeError:
        inp = {"raw": input_json}
    _emit({
        "signal": "ToolCallStarted",
        "tool_name": tool_name,
        "input": inp,
        "iteration": iteration,
    })


def on_tool_call_result(tool_name: str, output: str, success: bool, error: str):
    """Handle ToolCallResult signal."""
    _emit({
        "signal": "ToolCallResult",
        "tool_name": tool_name,
        "output": output,
        "success": bool(success),
        "error": error,
    })


def on_task_complete(data: str):
    """Handle TaskComplete signal."""
    try:
        parsed = json.loads(data) if data else {}
    except json.JSONDecodeError:
        parsed = {"raw": data}
    _emit({
        "signal": "TaskComplete",
        "data": parsed,
    })


def on_error_occurred(error: str):
    """Handle ErrorOccurred signal."""
    _emit({
        "signal": "ErrorOccurred",
        "error": error,
    })


def on_question_asked(question: str, options_json: str):
    """Handle QuestionAsked signal."""
    try:
        options = json.loads(options_json) if options_json else []
    except json.JSONDecodeError:
        options = []
    _emit({
        "signal": "QuestionAsked",
        "question": question,
        "options": options,
    })


def _emit(obj: dict):
    """Write JSON line to stdout and flush immediately."""
    line = json.dumps(obj, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


# ── Signal dispatch table ──

SIGNAL_HANDLERS = {
    "StatusChanged": on_status_changed,
    "TokenStream": on_token_stream,
    "ToolCallStarted": on_tool_call_started,
    "ToolCallResult": on_tool_call_result,
    "TaskComplete": on_task_complete,
    "ErrorOccurred": on_error_occurred,
    "QuestionAsked": on_question_asked,
}


def handle_dbus_signal(*args, **kwargs):
    """Generic D-Bus signal handler — dispatches by member name."""
    member = kwargs.get("member", "")
    handler = SIGNAL_HANDLERS.get(member)
    if handler:
        try:
            handler(*args)
        except Exception as exc:
            _emit({
                "signal": "ErrorOccurred",
                "error": f"Handler error for {member}: {exc}",
            })
    else:
        _emit({
            "signal": "UnknownSignal",
            "member": member,
            "args": [str(a) for a in args],
        })


def main():
    """Main entry point — connect to D-Bus and listen for signals."""
    # Print startup message
    _emit({
        "signal": "_listener_started",
        "bus_name": BUS_NAME,
        "object_path": OBJECT_PATH,
    })

    # Set up D-Bus main loop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()

    # Add signal match rules
    bus.add_signal_receiver(
        handle_dbus_signal,
        dbus_interface=INTERFACE,
        path=OBJECT_PATH,
        member_keyword="member",
    )

    # Also listen for NameOwnerChanged to detect service restart
    def on_name_owner_changed(name: str, old_owner: str, new_owner: str):
        if name == BUS_NAME:
            if new_owner and not old_owner:
                _emit({"signal": "_service_started", "name": name})
            elif old_owner and not new_owner:
                _emit({"signal": "_service_stopped", "name": name})

    bus.add_signal_receiver(
        on_name_owner_changed,
        dbus_interface="org.freedesktop.DBus",
        signal_name="NameOwnerChanged",
        arg0=BUS_NAME,
    )

    # Handle SIGTERM/SIGINT gracefully
    loop = GLib.MainLoop()

    def shutdown(_signum=None, _frame=None):
        _emit({"signal": "_listener_stopped"})
        loop.quit()

    sig.signal(sig.SIGTERM, shutdown)
    sig.signal(sig.SIGINT, shutdown)

    # Run the main loop
    loop.run()


if __name__ == "__main__":
    main()
