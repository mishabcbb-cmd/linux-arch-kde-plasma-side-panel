"""
tests/test_tools.py — Tests for the ToolRegistry and tool implementations.

Tests all 7 built-in tools with mock implementations.
"""

import os
from typing import Any, Dict

import pytest

from agent.tools import ToolRegistry, ToolResult
from tests.conftest import MockToolRegistry


# ============================================================================
# ToolResult Tests
# ============================================================================


class TestToolResult:
    """Tests for ToolResult data class."""

    def test_create_success(self):
        """Should create a success result."""
        result = ToolResult("test_tool", True, output="done")
        assert result.tool_name == "test_tool"
        assert result.success is True
        assert result.output == "done"
        assert result.error == ""

    def test_create_failure(self):
        """Should create a failure result."""
        result = ToolResult("test_tool", False, error="Something went wrong")
        assert result.success is False
        assert result.error == "Something went wrong"

    def test_to_dict(self):
        """Should convert to dict."""
        result = ToolResult("test", True, output="ok", metadata={"key": "val"})
        d = result.to_dict()
        assert d["tool_name"] == "test"
        assert d["success"] is True
        assert d["output"] == "ok"
        assert d["metadata"]["key"] == "val"
        assert "timestamp" in d

    def test_default_metadata(self):
        """Should have empty dict as default metadata."""
        result = ToolResult("test", True)
        assert result.metadata == {}

    def test_timestamp_auto(self):
        """Should auto-generate timestamp."""
        result = ToolResult("test", True)
        assert result.timestamp is not None


# ============================================================================
# ToolRegistry Tests
# ============================================================================


class TestToolRegistry:
    """Tests for ToolRegistry — tool registration and schema generation."""

    def test_init(self):
        """Should initialize with 9 registered tools."""
        registry = ToolRegistry()
        assert len(registry._tools) == 9

    def test_register_custom_tool(self):
        """Should allow registering custom tools."""
        registry = ToolRegistry()

        def custom_tool(args):
            return ToolResult("custom", True, output="custom result")

        registry.register("custom_tool", custom_tool)
        assert "custom_tool" in registry._tools

    def test_get_tool_schemas_returns_list(self):
        """Should return a list of tool schemas."""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 9

    def test_tool_schemas_have_required_fields(self):
        """Each schema should have name, description, input_schema."""
        registry = ToolRegistry()
        for schema in registry.get_tool_schemas():
            assert "name" in schema
            assert "description" in schema
            assert "input_schema" in schema

    def test_tool_schemas_include_all_tools(self):
        """Should include all 9 default tools."""
        registry = ToolRegistry()
        names = {s["name"] for s in registry.get_tool_schemas()}
        expected = {"bash_exec", "file_read", "file_write", "search_codebase",
                     "repo_map", "run_tests", "ask_user",
                     "cross_repo_search", "cross_repo_trace"}
        assert names == expected

    def test_execute_known_tool(self, mock_tool_registry: MockToolRegistry):
        """Should execute a known tool."""
        result = mock_tool_registry.execute("bash_exec", {"cmd": "echo hello"})
        assert result.success is True

    def test_execute_unknown_tool(self, mock_tool_registry: MockToolRegistry):
        """Should return error for unknown tool."""
        result = mock_tool_registry.execute("nonexistent", {})
        assert result.success is False
        assert "unknown tool" in result.error.lower()

    def test_execute_with_working_dir(self, temp_dir: str):
        """Should use working directory."""
        registry = ToolRegistry(working_dir=temp_dir)
        assert registry.working_dir == temp_dir


# ============================================================================
# Mock Tool Tests
# ============================================================================


class TestMockTools:
    """Tests for individual mock tool implementations."""

    @pytest.fixture
    def registry(self) -> MockToolRegistry:
        return MockToolRegistry()

    def test_bash_exec(self, registry: MockToolRegistry):
        """bash_exec should return command output."""
        result = registry.execute("bash_exec", {"cmd": "echo test"})
        assert result.success is True
        assert "Executed:" in result.output

    def test_file_read(self, registry: MockToolRegistry):
        """file_read should return file content."""
        result = registry.execute("file_read", {"path": "test.txt"})
        assert result.success is True
        assert "Content of" in result.output

    def test_file_write(self, registry: MockToolRegistry):
        """file_write should confirm write."""
        result = registry.execute("file_write", {
            "path": "test.txt",
            "content": "hello",
        })
        assert result.success is True
        assert "Written" in result.output

    def test_search_codebase(self, registry: MockToolRegistry):
        """search_codebase should return matches."""
        result = registry.execute("search_codebase", {"query": "test"})
        assert result.success is True
        assert "Found" in result.output

    def test_repo_map(self, registry: MockToolRegistry):
        """repo_map should return structure."""
        result = registry.execute("repo_map", {"max_tokens": 500})
        assert result.success is True
        assert "file1.py" in result.output

    def test_run_tests(self, registry: MockToolRegistry):
        """run_tests should return test results."""
        result = registry.execute("run_tests", {"path": "tests/"})
        assert result.success is True
        assert "passed" in result.output

    def test_ask_user(self, registry: MockToolRegistry):
        """ask_user should return user response."""
        result = registry.execute("ask_user", {
            "question": "Continue?",
            "options": ["yes", "no"],
        })
        assert result.success is True
        assert "User response" in result.output


# ============================================================================
# Tool Schema Validation Tests
# ============================================================================


class TestToolSchemas:
    """Tests for tool schema correctness."""

    def test_bash_exec_schema(self):
        """bash_exec should require 'cmd' parameter."""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        bash_schema = next(s for s in schemas if s["name"] == "bash_exec")
        assert "cmd" in bash_schema["input_schema"].get("required", [])

    def test_file_read_schema(self):
        """file_read should require 'path' parameter."""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        schema = next(s for s in schemas if s["name"] == "file_read")
        assert "path" in schema["input_schema"].get("required", [])

    def test_file_write_schema(self):
        """file_write should require 'path' and 'content'."""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        schema = next(s for s in schemas if s["name"] == "file_write")
        required = schema["input_schema"].get("required", [])
        assert "path" in required
        assert "content" in required

    def test_search_codebase_schema(self):
        """search_codebase should require 'query'."""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        schema = next(s for s in schemas if s["name"] == "search_codebase")
        assert "query" in schema["input_schema"].get("required", [])

    def test_ask_user_schema(self):
        """ask_user should require 'question'."""
        registry = ToolRegistry()
        schemas = registry.get_tool_schemas()
        schema = next(s for s in schemas if s["name"] == "ask_user")
        assert "question" in schema["input_schema"].get("required", [])
