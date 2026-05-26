"""
agent/mcp_server.py — MCP (Model Context Protocol) server for the KDE AI Agent.

Wraps ToolRegistry as an MCP server over stdio or SSE transports.
Allows the agent to be used as an MCP tool provider by external MCP clients
(e.g., IDE extensions, other agents).

Patterns from:
  - OpenCode (mcp-tools.go): MCP server wrapping tool registry
  - ZooCode/RooCode: MCP transport layer (stdio + SSE)

Usage:
    # As stdio server (for IDE integration)
    python -m agent.main --mcp-stdio

    # As SSE server on port 8765
    python -m agent.main --mcp-sse
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================================
# MCP Tool Definitions
# ============================================================================


class MCPToolDefinition:
    """An MCP tool definition matching the MCP protocol specification."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# ============================================================================
# MCP Server
# ============================================================================


class MCPToolServer:
    """Wraps ToolRegistry as an MCP server.

    Converts ToolRegistry tools to MCP tool definitions and handles
    tool call requests over MCP protocol.
    """

    def __init__(self, tool_registry):
        self._tool_registry = tool_registry
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._build_tool_definitions()

    def _build_tool_definitions(self) -> None:
        """Build MCP tool definitions from ToolRegistry schemas."""
        schemas = self._tool_registry.get_tool_schemas()
        for schema in schemas:
            name = schema.get("name", "")
            description = schema.get("description", "")
            input_schema = schema.get("input_schema", schema.get("inputSchema", {}))
            self._tools[name] = MCPToolDefinition(name, description, input_schema)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return MCP tool definitions for the list_tools request."""
        return [tool.to_dict() for tool in self._tools.values()]

    def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return MCP-formatted result."""
        try:
            result = self._tool_registry.execute(name, arguments)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result.output if result.success else result.error,
                    }
                ],
                "isError": not result.success,
            }
        except Exception as exc:
            logger.error(f"MCP tool execution error: {exc}")
            return {
                "content": [{"type": "text", "text": str(exc)}],
                "isError": True,
            }


# ============================================================================
# MCP Transport: stdio
# ============================================================================


class MCPStdioTransport:
    """MCP transport over stdin/stdout.

    Reads JSON-RPC requests from stdin, processes them, and writes
    responses to stdout. Used for IDE integration.
    """

    def __init__(self, server: MCPToolServer):
        self._server = server
        self._running = False

    def start(self) -> None:
        """Start processing MCP requests over stdio."""
        self._running = True
        logger.info("MCP stdio transport started")

        # Signal readiness
        self._send_response({
            "jsonrpc": "2.0",
            "method": "initialized",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "kde-ai-agent",
                    "version": "0.3.0",
                },
            },
        })

        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                request = json.loads(line)
                self._handle_request(request)

            except json.JSONDecodeError as exc:
                logger.warning(f"Invalid JSON from stdin: {exc}")
            except EOFError:
                break
            except Exception as exc:
                logger.error(f"Stdio transport error: {exc}")

    def _handle_request(self, request: Dict[str, Any]) -> None:
        """Handle a single JSON-RPC request."""
        method = request.get("method", "")
        request_id = request.get("id")
        params = request.get("params", {})

        if method == "tools/list":
            tools = self._server.get_tool_definitions()
            self._send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools},
            })

        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = self._server.execute_tool(name, arguments)
            self._send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result,
            })

        elif method == "initialize":
            self._send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "kde-ai-agent", "version": "0.3.0"},
                },
            })

        elif method == "shutdown":
            self._running = False
            self._send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": None,
            })

        else:
            self._send_response({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            })

    def _send_response(self, response: Dict[str, Any]) -> None:
        """Send a JSON-RPC response to stdout."""
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()

    def stop(self) -> None:
        self._running = False


# ============================================================================
# MCP Transport: SSE (Server-Sent Events)
# ============================================================================


class MCPSSETransport:
    """MCP transport over HTTP SSE.

    Provides an HTTP endpoint for MCP clients to connect via SSE.
    Requires uvicorn + starlette.
    """

    def __init__(self, server: MCPToolServer, host: str = "127.0.0.1", port: int = 8765):
        self._server = server
        self.host = host
        self.port = port
        self._app = None

    async def _handle_sse(self, scope, receive, send):
        """Handle SSE connection."""
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/event-stream"),
                (b"cache-control", b"no-cache"),
                (b"connection", b"keep-alive"),
            ],
        })

        # Send initial endpoint event
        await send({
            "type": "http.response.body",
            "body": f"event: endpoint\ndata: /mcp\n\n".encode(),
            "more_body": True,
        })

        # Keep connection alive
        try:
            while True:
                await asyncio.sleep(15)
                await send({
                    "type": "http.response.body",
                    "body": ": keepalive\n\n".encode(),
                    "more_body": True,
                })
        except asyncio.CancelledError:
            pass

    async def _handle_mcp(self, scope, receive, send):
        """Handle MCP JSON-RPC requests over HTTP POST."""
        if scope["method"] != "POST":
            await send({
                "type": "http.response.start",
                "status": 405,
                "headers": [(b"content-type", b"text/plain")],
            })
            await send({"type": "http.response.body", "body": b"Method not allowed"})
            return

        # Read request body
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.request":
                body += message.get("body", b"")
                more_body = message.get("more_body", False)

        try:
            request = json.loads(body)
            method = request.get("method", "")
            request_id = request.get("id")
            params = request.get("params", {})

            if method == "tools/list":
                tools = self._server.get_tool_definitions()
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools},
                }
            elif method == "tools/call":
                name = params.get("name", "")
                arguments = params.get("arguments", {})
                result = self._server.execute_tool(name, arguments)
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result,
                }
            elif method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "kde-ai-agent", "version": "0.3.0"},
                    },
                }
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }

            body_bytes = json.dumps(response).encode()
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body_bytes)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body_bytes})

        except Exception as exc:
            error_response = json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(exc)},
            }).encode()
            await send({
                "type": "http.response.start",
                "status": 400,
                "headers": [(b"content-type", b"application/json")],
            })
            await send({"type": "http.response.body", "body": error_response})

    async def start(self) -> None:
        """Start the SSE server."""
        try:
            import uvicorn
        except ImportError:
            logger.error(
                "uvicorn not installed. Install with: pip install uvicorn starlette"
            )
            return

        config = uvicorn.Config(
            self._create_app(),
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        logger.info(f"MCP SSE server starting on http://{self.host}:{self.port}")
        await server.serve()

    def _create_app(self):
        """Create an ASGI app for the SSE server."""
        async def app(scope, receive, send):
            if scope["type"] != "http":
                return

            path = scope.get("path", "")
            if path == "/sse":
                await self._handle_sse(scope, receive, send)
            elif path == "/mcp":
                await self._handle_mcp(scope, receive, send)
            else:
                await send({
                    "type": "http.response.start",
                    "status": 404,
                    "headers": [(b"content-type", b"text/plain")],
                })
                await send({"type": "http.response.body", "body": b"Not found"})

        return app
