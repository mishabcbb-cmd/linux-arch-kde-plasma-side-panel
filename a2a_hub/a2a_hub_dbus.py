#!/usr/bin/env python3
"""
a2a_hub_dbus.py — D-Bus service for A2A Hub.

Exposes over D-Bus (org.kde.a2ahub):
  • get_conversations() -> list of conversation summaries
  • get_conversation(task_id) -> full conversation log
  • send_message(task_id, message) -> send user message to agent
  • get_agents() -> list of registered agents
  • get_status() -> hub status

Signals emitted on D-Bus:
  • ConversationUpdated(task_id, message_count)
  • AgentStatusChanged(agent_name, status)
  • NewMessage(task_id, role, content, agent)

Usage:
    python a2a_hub_dbus.py [--hub-url http://127.0.0.1:9000]
"""

import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import dbus
import dbus.mainloop.glib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

sys.path.insert(0, str(Path(__file__).parent))
from client.hub_client import A2AHubClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("a2a-hub-dbus")

BUS_NAME = "org.kde.a2ahub"
OBJECT_PATH = "/org/kde/a2ahub"
INTERFACE_NAME = "org.kde.a2ahub"


class A2AHubDBusService(dbus.service.Object):
    """D-Bus service exposing A2A Hub conversation log and agent status."""

    def __init__(self, hub_url: str = "http://127.0.0.1:9000"):
        self.hub_url = hub_url
        self._client = A2AHubClient(
            hub_url=hub_url,
            agent_name="a2a-hub-dbus",
            agent_description="A2A Hub D-Bus Service",
            agent_endpoint="",
            capabilities=["dbus", "chat"],
        )
        self._client.register()
        self._client.start_heartbeat()

        # Set up D-Bus
        DBusGMainLoop(set_as_default=True)
        bus_name = dbus.service.BusName(BUS_NAME, bus=dbus.SessionBus())
        super().__init__(bus_name, OBJECT_PATH)

        # Poll for new messages
        self._poll_interval = 2  # seconds
        self._last_conversation_count = 0
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        logger.info(f"A2A Hub D-Bus service started on {BUS_NAME}")

    # --- D-Bus Methods ---

    @dbus.service.method(INTERFACE_NAME, in_signature="", out_signature="s")
    def GetStatus(self) -> str:
        """Get Hub status as JSON string."""
        try:
            status = self._client._request("GET", "/health")
            agents = self._client.discover_agents()
            active = [a for a in agents if a.get("status") == "active"]
            result = {
                "status": "running",
                "hub_url": self.hub_url,
                "agents_total": len(agents),
                "agents_active": len(active),
            }
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @dbus.service.method(INTERFACE_NAME, in_signature="", out_signature="s")
    def GetAgents(self) -> str:
        """Get list of registered agents as JSON string."""
        try:
            agents = self._client.discover_agents()
            return json.dumps(agents)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @dbus.service.method(INTERFACE_NAME, in_signature="", out_signature="s")
    def GetConversations(self) -> str:
        """Get list of all conversations as JSON string."""
        try:
            result = self._client._request("GET", "/conversations")
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @dbus.service.method(INTERFACE_NAME, in_signature="s", out_signature="s")
    def GetConversation(self, task_id: str) -> str:
        """Get full conversation log for a task as JSON string."""
        try:
            result = self._client._request("GET", f"/conversations/{task_id}")
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @dbus.service.method(INTERFACE_NAME, in_signature="ss", out_signature="s")
    def SendMessage(self, task_id: str, message: str) -> str:
        """Send a user message to an agent via Hub."""
        try:
            # Post user message to conversation log
            self._client._post_conversation_message(
                task_id=task_id, role="user", content=message, agent="user"
            )
            # Submit task to Hub for routing
            result = self._client.submit_task(text=message, context={"task_id": task_id})
            return json.dumps({"status": "ok", "result": result})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @dbus.service.method(INTERFACE_NAME, in_signature="s", out_signature="s")
    def DelegateTask(self, task_json: str) -> str:
        """Delegate a task to a specific agent. JSON: {task, target_agent, context?}."""
        try:
            data = json.loads(task_json)
            task = data.get("task", "")
            target = data.get("target_agent", "")
            context = data.get("context", {})
            result = self._client.delegate_task(task, target, context)
            return json.dumps({"status": "ok", "result": result})
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    @dbus.service.method(INTERFACE_NAME, in_signature="", out_signature="s")
    def GetConversationSummary(self) -> str:
        """Get summary of all conversations (lightweight)."""
        try:
            result = self._client._request("GET", "/conversations")
            conversations = result.get("conversations", [])
            summaries = []
            for conv in conversations[:20]:
                task_id = conv.get("task_id", "")
                messages = conv.get("messages", [])
                user_msgs = [m for m in messages if m.get("role") == "user"]
                agent_msgs = [m for m in messages if m.get("role") == "assistant"]
                summaries.append({
                    "task_id": task_id,
                    "total_messages": len(messages),
                    "user_messages": len(user_msgs),
                    "agent_messages": len(agent_msgs),
                    "agents_involved": list(set(m.get("agent", "") for m in agent_msgs)),
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at"),
                    "last_message": messages[-1] if messages else None,
                })
            return json.dumps({"conversations": summaries, "total": len(conversations)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    # --- D-Bus Signals ---

    @dbus.service.signal(INTERFACE_NAME, signature="si")
    def ConversationUpdated(self, task_id: str, message_count: int):
        """Emitted when a conversation receives new messages."""
        pass

    @dbus.service.signal(INTERFACE_NAME, signature="ss")
    def AgentStatusChanged(self, agent_name: str, status: str):
        """Emitted when an agent's status changes."""
        pass

    @dbus.service.signal(INTERFACE_NAME, signature="ssss")
    def NewMessage(self, task_id: str, role: str, content: str, agent: str):
        """Emitted when a new message is added to a conversation."""
        pass

    # --- Polling Loop ---

    def _poll_loop(self) -> None:
        """Poll Hub for new messages and emit signals."""
        while self._running:
            try:
                result = self._client._request("GET", "/conversations")
                conversations = result.get("conversations", [])
                current_count = len(conversations)

                if current_count != self._last_conversation_count:
                    self._last_conversation_count = current_count
                    # Emit signal for the most recent conversation
                    if conversations:
                        latest = conversations[0]
                        task_id = latest.get("task_id", "")
                        messages = latest.get("messages", [])
                        self.ConversationUpdated(task_id, len(messages))

                        # Emit NewMessage for the last message
                        if messages:
                            last_msg = messages[-1]
                            self.NewMessage(
                                task_id,
                                last_msg.get("role", ""),
                                last_msg.get("content", "")[:200],
                                last_msg.get("agent", ""),
                            )
            except Exception as e:
                logger.debug(f"Poll error (non-fatal): {e}")

            time.sleep(self._poll_interval)

    def stop(self) -> None:
        """Stop the D-Bus service."""
        self._running = False
        self._client.stop_heartbeat()
        logger.info("A2A Hub D-Bus service stopped.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="A2A Hub D-Bus Service")
    parser.add_argument("--hub-url", default="http://127.0.0.1:9000", help="Hub URL")
    args = parser.parse_args()

    service = A2AHubDBusService(hub_url=args.hub_url)

    # Handle signals
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run GLib main loop
    from gi.repository import GLib
    loop = GLib.MainLoop()
    logger.info("A2A Hub D-Bus service running. Press Ctrl+C to stop.")
    try:
        loop.run()
    except KeyboardInterrupt:
        service.stop()


if __name__ == "__main__":
    main()
