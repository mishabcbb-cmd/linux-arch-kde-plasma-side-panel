"""
tests/test_mcp_server.py — Tests for the MCP server module.

Tests MCPToolServer, MCPStdioTransport, and MCPSSETransport.
"""

import json
import sys
from io import StringIO
from typing import Any, Dict

import pytest

from agent.mcp_server import MCPToolServer, MCPStdioTransport
from agent.tools import ToolRegistry, ToolResult
from tests.conftest import MockToolRegistry


# ============================================================================
# MCPToolServer Tests
# ============================================================================


class TestMCPToolServer:
    """Tests for MCPToolServer — wrapping ToolRegistry as MCP server."""

    def test_init_with_tool_registry(self, mock_tool_registry: MockToolRegistry):
        """Should initialize with a ToolRegistry and build tool definitions."""
        server = MCPToolServer(mock_tool_registry)
        assert server is not None

    def test_get_tool_definitions_returns_list(self, mock_tool_registry: MockToolRegistry):
        """Should return a list of MCP tool definitions."""
        server = MCPToolServer(mock_tool_registry)
        tools = server.get_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tool_definitions_have_required_fields(self, mock_tool_registry: MockToolRegistry):
        """Each tool definition should have name, description, inputSchema."""
        server = MCPToolServer(mock_tool_registry)
        for tool in server.get_tool_definitions():
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_tool_definitions_include_all_tools(self, mock_tool_registry: MockToolRegistry):
        """Should include all 7 registered tools."""
        server = MCPToolServer(mock_tool_registry)
        tool_names = {t["name"] for t in server.get_tool_definitions()}
        expected = {"bash_exec", "file_read", "file_write", "search_codebase",
                     "repo_map", "run_tests", "ask_user"}
        assert tool_names == expected

    def test_execute_tool_success(self, mock_tool_registry: MockToolRegistry):
        """Should execute a tool and return success result."""
        server = MCPToolServer(mock_tool_registry)
        result = server.execute_tool("bash_exec", {"cmd": "echo hello"})
        assert result["isError"] is False
        assert len(result["content"]) > 0
        assert result["content"][0]["type"] == "text"

    def test_execute_tool_unknown(self, mock_tool_registry: MockToolRegistry):
        """Should return error for unknown tool."""
        server = MCPToolServer(mock_tool_registry)
        result = server.execute_tool("nonexistent", {})
        assert result["isError"] is True

    def test_execute_tool_with_invalid_args(self, mock_tool_registry: MockToolRegistry):
        """Should handle invalid arguments gracefully."""
        server = MCPToolServer(mock_tool_registry)
        result = server.execute_tool("file_read", {})  # Missing 'path'
        # Should not crash, return error
        assert isinstance(result, dict)
        assert "content" in result


# ============================================================================
# MCPStdioTransport Tests
# ============================================================================


class TestMCPStdioTransport:
    """Tests for MCPStdioTransport — JSON-RPC over stdin/stdout."""

    def test_init_with_server(self, mock_tool_registry: MockToolRegistry):
        """Should initialize with an MCPToolServer."""
        server = MCPToolServer(mock_tool_registry)
        transport = MCPStdioTransport(server)
        assert transport is not None

    def test_handle_tools_list_request(self, mock_tool_registry: MockToolRegistry):
        """Should respond to tools/list with tool definitions."""
        server = MCPToolServer(mock_tool_registry)
        transport = MCPStdioTransport(server)

        # Capture stdout
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            transport._handle_request({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            })

            output = captured.getvalue()
            response = json.loads(output.strip())

            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 1
            assert "result" in response
            assert "tools" in response["result"]
        finally:
            sys.stdout = old_stdout

    def test_handle_tools_call_request(self, mock_tool_registry: MockToolRegistry):
        """Should respond to tools/call with execution result."""
        server = MCPToolServer(mock_tool_registry)
        transport = MCPStdioTransport(server)

        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            transport._handle_request({
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "bash_exec",
                    "arguments": {"cmd": "echo test"},
                },
            })

            output = captured.getvalue()
            response = json.loads(output.strip())

            assert response["jsonrpc"] == "2.0"
            assert response["id"] == 2
            assert "result" in response
        finally:
            sys.stdout = old_stdout

    def test_handle_initialize_request(self, mock_tool_registry: MockToolRegistry):
        """Should respond to initialize with server info."""
        server = MCPToolServer(mock_tool_registry)
        transport = MCPStdioTransport(server)

        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            transport._handle_request({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "initialize",
                "params": {},
            })

            output = captured.getvalue()
            response = json.loads(output.strip())

            assert response["id"] == 3
            assert response["result"]["serverInfo"]["name"] == "kde-ai-agent"
        finally:
            sys.stdout = old_stdout

    def test_handle_unknown_method(self, mock_tool_registry: MockToolRegistry):
        """Should return error for unknown method."""
        server = MCPToolServer(mock_tool_registry)
        transport = MCPStdioTransport(server)

        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            transport._handle_request({
                "jsonrpc": "2.0",
                "id": 4,
                "method": "unknown_method",
                "params": {},
            })

            output = captured.getvalue()
            response = json.loads(output.strip())

            assert "error" in response
            assert response["error"]["code"] == -32601
        finally:
            sys.stdout = old_stdout

    def test_handle_shutdown(self, mock_tool_registry: MockToolRegistry):
        """Should handle shutdown and set running to False."""
        server = MCPToolServer(mock_tool_registry)
        transport = MCPStdioTransport(server)
        transport._running = True

        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured

        try:
            transport._handle_request({
                "jsonrpc": "2.0",
                "id": 5,
                "method": "shutdown",
                "params": {},
            })

            assert transport._running is False
        finally:
            sys.stdout = old_stdout


# ============================================================================
# MCPSSETransport Tests
# ============================================================================


class TestMCPSSETransport:
    """Tests for MCPSSETransport — HTTP SSE transport."""

    def test_init(self, mock_tool_registry: MockToolRegistry):
        """Should initialize with server and default host/port."""
        from agent.mcp_server import MCPSSETransport
        server = MCPToolServer(mock_tool_registry)
        transport = MCPSSETransport(server)
        assert transport.host == "127.0.0.1"
        assert transport.port == 8765

    def test_custom_host_port(self, mock_tool_registry: MockToolRegistry):
        """Should accept custom host and port."""
        from agent.mcp_server import MCPSSETransport
        server = MCPToolServer(mock_tool_registry)
        transport = MCPSSETransport(server, host="0.0.0.0", port=9999)
        assert transport.host == "0.0.0.0"
        assert transport.port == 9999
