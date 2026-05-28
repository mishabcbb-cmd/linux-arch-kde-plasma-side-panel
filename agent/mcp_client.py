"""
agent/mcp_client.py — MCP (Model Context Protocol) client for the KDE AI Agent.

Connects to external MCP servers (lean-ctx, engram, codebase-memory, searxng)
and exposes their tools to the agent's ReAct loop.

Supports:
  - stdio transport (subprocess)
  - SSE transport (HTTP)
  - Auto-approve for trusted tools
  - Dynamic server discovery from config

Patterns from:
  - OpenCode (mcp-tools.go): MCP client with stdio/SSE support
  - ZooCode/RooCode: auto-approve mechanism for trusted tools
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class MCPServerConfig:
    """Configuration for an external MCP server."""

    name: str
    transport: str  # "stdio" or "sse"
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""  # For SSE transport
    auto_approve: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "MCPServerConfig":
        return cls(
            name=name,
            transport=data.get("transport", "stdio"),
            command=data.get("command", ""),
            args=data.get("args", []),
            url=data.get("url", ""),
            auto_approve=data.get("auto_approve", []),
            env=data.get("env", {}),
        )


@dataclass
class MCPToolInfo:
    """Information about a tool exposed by an MCP server."""

    server_name: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    auto_approved: bool = False


# ============================================================================
# MCP Client
# ============================================================================


class MCPClientConnection:
    """Connection to a single MCP server."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: Optional[subprocess.Popen] = None
        self._tools: List[MCPToolInfo] = []
        self._connected = False
        self._lock = threading.Lock()
        self._request_id = 0
        self._pending_responses: Dict[int, threading.Event] = {}
        self._responses: Dict[int, Dict[str, Any]] = {}
        self._read_thread: Optional[threading.Thread] = None

    def connect(self) -> bool:
        """Connect to the MCP server."""
        if self._connected:
            return True

        if self.config.transport == "stdio":
            return self._connect_stdio()
        elif self.config.transport == "sse":
            logger.warning(f"SSE transport not yet implemented for {self.config.name}")
            return False
        else:
            logger.error(f"Unknown transport: {self.config.transport}")
            return False

    def _connect_stdio(self) -> bool:
        """Connect via stdio subprocess."""
        try:
            cmd = [self.config.command] + self.config.args
            env = os.environ.copy()
            env.update(self.config.env)

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
            )

            # Start reader thread
            self._read_thread = threading.Thread(
                target=self._read_stdout,
                daemon=True,
            )
            self._read_thread.start()

            # Initialize
            if self._send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "kde-ai-agent", "version": "0.3.0"},
            }):
                self._connected = True
                # Discover tools
                self._discover_tools()
                logger.info(f"Connected to MCP server: {self.config.name}")
                return True

            return False

        except Exception as exc:
            logger.error(f"Failed to connect to {self.config.name}: {exc}")
            return False

    def _read_stdout(self) -> None:
        """Read JSON-RPC responses from stdout."""
        if not self._process or not self._process.stdout:
            return

        try:
            for line in self._process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    response = json.loads(line)
                    req_id = response.get("id")
                    if req_id is not None and req_id in self._pending_responses:
                        self._responses[req_id] = response
                        self._pending_responses[req_id].set()
                except json.JSONDecodeError:
                    pass
        except Exception as exc:
            logger.debug(f"Read thread ended for {self.config.name}: {exc}")

    def _send_request(self, method: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin:
            return None

        with self._lock:
            self._request_id += 1
            req_id = self._request_id
            request = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            }

            event = threading.Event()
            self._pending_responses[req_id] = event

            try:
                self._process.stdin.write(json.dumps(request) + "\n")
                self._process.stdin.flush()
            except Exception as exc:
                logger.error(f"Failed to send request to {self.config.name}: {exc}")
                del self._pending_responses[req_id]
                return None

        # Wait for response (timeout: 10 seconds)
        if event.wait(timeout=10):
            response = self._responses.pop(req_id, {})
            del self._pending_responses[req_id]
            if "error" in response:
                logger.error(f"MCP error from {self.config.name}: {response['error']}")
                return None
            return response.get("result")
        else:
            del self._pending_responses[req_id]
            logger.warning(f"Request timeout for {self.config.name}: {method}")
            return None

    def _discover_tools(self) -> None:
        """Discover tools from the MCP server."""
        result = self._send_request("tools/list", {})
        if result and "tools" in result:
            for tool_data in result["tools"]:
                tool = MCPToolInfo(
                    server_name=self.config.name,
                    name=tool_data.get("name", ""),
                    description=tool_data.get("description", ""),
                    input_schema=tool_data.get("inputSchema", {}),
                    auto_approved=tool_data.get("name", "") in self.config.auto_approve,
                )
                self._tools.append(tool)

    def get_tools(self) -> List[MCPToolInfo]:
        """Get discovered tools."""
        return self._tools

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on the MCP server."""
        result = self._send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        if result is None:
            return {
                "content": [{"type": "text", "text": f"Tool execution failed: {name}"}],
                "isError": True,
            }
        return result

    def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        self._connected = False
        if self._process:
            try:
                self._send_request("shutdown", {})
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None

    @property
    def connected(self) -> bool:
        return self._connected


class MCPClientManager:
    """Manages connections to multiple MCP servers."""

    def __init__(self):
        self._connections: Dict[str, MCPClientConnection] = {}
        self._lock = threading.Lock()

    def load_from_config(self, mcp_servers_config: Dict[str, Any]) -> None:
        """Load MCP server configurations from config dict."""
        for name, server_data in mcp_servers_config.items():
            config = MCPServerConfig.from_dict(name, server_data)
            self.add_server(config)

    def add_server(self, config: MCPServerConfig) -> None:
        """Add and connect to an MCP server."""
        with self._lock:
            if config.name in self._connections:
                logger.warning(f"Server already connected: {config.name}")
                return
            connection = MCPClientConnection(config)
            if connection.connect():
                self._connections[config.name] = connection
                tools = connection.get_tools()
                logger.info(f"Connected to {config.name}: {len(tools)} tools available")
            else:
                logger.warning(f"Failed to connect to MCP server: {config.name}")

    def remove_server(self, name: str) -> None:
        """Disconnect and remove an MCP server."""
        with self._lock:
            if name in self._connections:
                self._connections[name].disconnect()
                del self._connections[name]

    def get_all_tools(self) -> List[MCPToolInfo]:
        """Get all tools from all connected servers."""
        tools = []
        with self._lock:
            for connection in self._connections.values():
                tools.extend(connection.get_tools())
        return tools

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI-format tool schemas for all MCP tools."""
        schemas = []
        for tool in self.get_all_tools():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
                "mcp_server": tool.server_name,
                "auto_approved": tool.auto_approved,
            })
        return schemas

    def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool on a specific MCP server."""
        with self._lock:
            connection = self._connections.get(server_name)
            if not connection:
                return {
                    "content": [{"type": "text", "text": f"Server not connected: {server_name}"}],
                    "isError": True,
                }
        return connection.execute_tool(tool_name, arguments)

    def is_tool_auto_approved(self, tool_name: str) -> bool:
        """Check if a tool is auto-approved by any server."""
        for tool in self.get_all_tools():
            if tool.name == tool_name and tool.auto_approved:
                return True
        return False

    def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        with self._lock:
            for connection in self._connections.values():
                connection.disconnect()
            self._connections.clear()

    @property
    def connected_servers(self) -> List[str]:
        with self._lock:
            return list(self._connections.keys())

    @property
    def total_tools(self) -> int:
        return len(self.get_all_tools())
