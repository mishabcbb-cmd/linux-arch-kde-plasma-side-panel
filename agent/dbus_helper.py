#!/usr/bin/env python3
"""
dbus_helper.py — CLI helper for QML → D-Bus communication.

Usage:
    python3 dbus_helper.py get_status
    python3 dbus_helper.py run_task "task string" '["/path/to/file1", "/path/to/file2"]'
    python3 dbus_helper.py stop_task
    python3 dbus_helper.py provide_response "response text"

This script uses dbus-python to call the org.kde.aiagent D-Bus service.
"""

import json
import sys

try:
    import dbus
except ImportError:
    print("ERROR: dbus-python not installed", file=sys.stderr)
    sys.exit(1)


BUS_NAME = "org.kde.aiagent"
OBJECT_PATH = "/org/kde/aiagent"
INTERFACE_NAME = "org.kde.aiagent"


def get_proxy():
    session_bus = dbus.SessionBus()
    try:
        proxy = session_bus.get_object(BUS_NAME, OBJECT_PATH)
        return dbus.Interface(proxy, INTERFACE_NAME)
    except dbus.exceptions.DBusException as e:
        print(f"ERROR: Cannot connect to {BUS_NAME}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: dbus_helper.py <command> [args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    proxy = get_proxy()

    if command == "get_status":
        status = proxy.GetStatus()
        print(f"STATUS: {status}")

    elif command == "run_task":
        if len(sys.argv) < 3:
            print("Usage: dbus_helper.py run_task <task> [files_json]", file=sys.stderr)
            sys.exit(1)
        task = sys.argv[2]
        files = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
        result = proxy.RunTask(task, files)
        print(f"OK: {result}")

    elif command == "stop_task":
        proxy.StopTask()
        print("OK: Task stopped")

    elif command == "launch_panel":
        import subprocess
        panel_script = os.path.join(os.path.dirname(__file__), "side_panel.py")
        subprocess.Popen([sys.executable, panel_script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("OK: Side panel launched")

    elif command == "provide_response":
        if len(sys.argv) < 3:
            print("Usage: dbus_helper.py provide_response <response>", file=sys.stderr)
            sys.exit(1)
        response = sys.argv[2]
        proxy.ProvideUserResponse(response)
        print("OK: Response sent")

    else:
        print(f"ERROR: Unknown command '{command}'", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
