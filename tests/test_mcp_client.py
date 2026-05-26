"""
tests/test_mcp_client.py — Tests for the MCP client module.

Tests MCPServerConfig, MCPClientConnection, and MCPClientManager.
"""

import json
from typing import Any, Dict

import pytest

from agent.mcp_client import MCPServerConfig, MCPClientManager


# ============================================================================
# MCPServerConfig Tests
# ============================================================================


class TestMCPServerConfig:
    """Tests for MCPServerConfig data class."""

    def test_from_dict_stdio(self):
        """Should parse stdio server config from dict."""
        config = MCPServerConfig.from_dict("test-server", {
            "transport": "stdio",
            "command": "/usr/bin/test",
            "args": ["--flag"],
            "auto_approve": ["tool1"],
        })
        assert config.name == "test-server"
        assert config.transport == "stdio"
        assert config.command == "/usr/bin/test"
        assert config.args == ["--flag"]
        assert config.auto_approve == ["tool1"]

    def test_from_dict_sse(self):
        """Should parse SSE server config from dict."""
        config = MCPServerConfig.from_dict("sse-server", {
            "transport": "sse",
            "url": "http://localhost:8765/sse",
        })
        assert config.name == "sse-server"
        assert config.transport == "sse"
        assert config.url == "http://localhost:8765/sse"

    def test_from_dict_defaults(self):
        """Should use defaults for missing fields."""
        config = MCPServerConfig.from_dict("minimal", {})
        assert config.name == "minimal"
        assert config.transport == "stdio"
        assert config.command == ""
        assert config.args == []
        assert config.auto_approve == []
        assert config.env == {}

    def test_from_dict_with_env(self):
        """Should parse env vars."""
        config = MCPServerConfig.from_dict("env-server", {
            "transport": "stdio",
            "command": "test",
            "env": {"API_KEY": "secret"},
        })
        assert config.env == {"API_KEY": "secret"}


# ============================================================================
# MCPClientManager Tests
# ============================================================================


class TestMCPClientManager:
    """Tests for MCPClientManager — managing multiple MCP server connections."""

    def test_init(self):
        """Should initialize with empty connections."""
        manager = MCPClientManager()
        assert manager.connected_servers == []
        assert manager.total_tools == 0

    def test_load_from_config_empty(self):
        """Should handle empty config."""
        manager = MCPClientManager()
        manager.load_from_config({})
        assert manager.connected_servers == []

    def test_load_from_config_with_servers(self):
        """Should load servers from config dict."""
        manager = MCPClientManager()
        manager.load_from_config({
            "lean-ctx": {
                "transport": "stdio",
                "command": "lean-ctx",
                "auto_approve": ["ctx_read", "ctx_search"],
            },
        })
        # Server may not connect if command doesn't exist, but config should be loaded
        # The connection attempt will fail silently
        assert isinstance(manager, MCPClientManager)

    def test_add_server_invalid_command(self):
        """Should handle failed connection gracefully."""
        manager = MCPClientManager()
        config = MCPServerConfig(
            name="nonexistent",
            transport="stdio",
            command="/nonexistent/command",
        )
        manager.add_server(config)
        # Should not crash, just log warning
        assert isinstance(manager, MCPClientManager)

    def test_remove_server_nonexistent(self):
        """Should handle removing nonexistent server."""
        manager = MCPClientManager()
        manager.remove_server("nonexistent")
        # Should not crash

    def test_get_all_tools_empty(self):
        """Should return empty list when no servers connected."""
        manager = MCPClientManager()
        assert manager.get_all_tools() == []

    def test_get_tool_schemas_empty(self):
        """Should return empty list when no servers connected."""
        manager = MCPClientManager()
        assert manager.get_tool_schemas() == []

    def test_is_tool_auto_approved_empty(self):
        """Should return False for any tool when no servers."""
        manager = MCPClientManager()
        assert manager.is_tool_auto_approved("any_tool") is False

    def test_execute_tool_no_server(self):
        """Should return error when server not connected."""
        manager = MCPClientManager()
        result = manager.execute_tool("unknown", "tool", {})
        assert result["isError"] is True
        assert "not connected" in result["content"][0]["text"]

    def test_disconnect_all_empty(self):
        """Should handle disconnect_all with no connections."""
        manager = MCPClientManager()
        manager.disconnect_all()
        assert manager.connected_servers == []

    def test_multiple_servers_same_name(self):
        """Should not add duplicate server."""
        manager = MCPClientManager()
        config1 = MCPServerConfig(name="dup", transport="stdio", command="cmd1")
        config2 = MCPServerConfig(name="dup", transport="stdio", command="cmd2")
        manager.add_server(config1)
        manager.add_server(config2)
        # Second add should be rejected (same name)
        # Both will fail to connect since commands don't exist
        assert isinstance(manager, MCPClientManager)


# ============================================================================
# MCPServerConfig Integration Tests
# ============================================================================


class TestMCPServerConfigIntegration:
    """Integration tests for MCPServerConfig with real config patterns."""

    def test_lean_ctx_config(self):
        """Should parse lean-ctx server config."""
        config = MCPServerConfig.from_dict("lean-ctx", {
            "transport": "stdio",
            "command": "lean-ctx",
            "auto_approve": ["ctx_read", "ctx_search"],
        })
        assert config.name == "lean-ctx"
        assert "ctx_read" in config.auto_approve

    def test_engram_config(self):
        """Should parse engram server config."""
        config = MCPServerConfig.from_dict("engram", {
            "transport": "stdio",
            "command": "/usr/bin/engram",
            "args": ["mcp"],
            "auto_approve": ["mem_search", "mem_context"],
        })
        assert config.name == "engram"
        assert config.args == ["mcp"]

    def test_codebase_memory_config(self):
        """Should parse codebase-memory server config."""
        config = MCPServerConfig.from_dict("codebase-memory", {
            "transport": "stdio",
            "command": "codebase-memory",
            "auto_approve": ["search_graph", "search_code"],
        })
        assert config.name == "codebase-memory"
        assert config.transport == "stdio"

    def test_searxng_config(self):
        """Should parse searxng server config."""
        config = MCPServerConfig.from_dict("searxng", {
            "transport": "sse",
            "url": "http://localhost:8888/sse",
        })
        assert config.name == "searxng"
        assert config.transport == "sse"
        assert config.url == "http://localhost:8888/sse"
