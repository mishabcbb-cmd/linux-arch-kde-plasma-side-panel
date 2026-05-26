"""
tests/conftest.py — Shared fixtures for all test modules.

Provides:
  - MockToolRegistry: A ToolRegistry with mock implementations
  - sample_config: A minimal agent config dict
  - temp_dir: A temporary directory for file operations
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from agent.tools import ToolRegistry, ToolResult


# ============================================================================
# Mock Tool Registry
# ============================================================================


class MockToolRegistry(ToolRegistry):
    """ToolRegistry with mock implementations for testing."""

    def __init__(self, working_dir: Optional[str] = None):
        super().__init__(working_dir=working_dir)
        # Override with mock implementations
        self._tools = {}
        self.register("bash_exec", self._mock_bash_exec)
        self.register("file_read", self._mock_file_read)
        self.register("file_write", self._mock_file_write)
        self.register("search_codebase", self._mock_search)
        self.register("repo_map", self._mock_repo_map)
        self.register("run_tests", self._mock_run_tests)
        self.register("ask_user", self._mock_ask_user)

    def _mock_bash_exec(self, args: Dict[str, Any]) -> ToolResult:
        cmd = args.get("cmd", "")
        return ToolResult("bash_exec", True, output=f"Executed: {cmd}")

    def _mock_file_read(self, args: Dict[str, Any]) -> ToolResult:
        path = args.get("path", "")
        return ToolResult("file_read", True, output=f"Content of {path}\nline 1\nline 2")

    def _mock_file_write(self, args: Dict[str, Any]) -> ToolResult:
        path = args.get("path", "")
        content = args.get("content", "")
        return ToolResult("file_write", True, output=f"Written {len(content)} bytes to {path}")

    def _mock_search(self, args: Dict[str, Any]) -> ToolResult:
        query = args.get("query", "")
        return ToolResult("search_codebase", True, output=f"Found 3 matches for '{query}'")

    def _mock_repo_map(self, args: Dict[str, Any]) -> ToolResult:
        return ToolResult("repo_map", True, output="file1.py: class Foo\nfile2.py: def bar")

    def _mock_run_tests(self, args: Dict[str, Any]) -> ToolResult:
        return ToolResult("run_tests", True, output="All tests passed!")

    def _mock_ask_user(self, args: Dict[str, Any]) -> ToolResult:
        question = args.get("question", "")
        return ToolResult("ask_user", True, output=f"User response to: {question}")


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_config() -> Dict[str, Any]:
    """A minimal agent configuration."""
    return {
        "provider": "ollama",
        "model": "llama3.2",
        "api_key": "",
        "ollama_host": "http://localhost:11434",
        "ollama_model": "llama3.2",
        "max_tokens": 8192,
        "max_input_tokens": 100000,
        "temperature": 0.7,
        "working_dir": str(Path.home()),
        "openobserve_endpoint": "",
        "openobserve_stream": "ai-agent-events",
    }


@pytest.fixture
def mock_tool_registry() -> MockToolRegistry:
    """A ToolRegistry with mock implementations."""
    return MockToolRegistry()


@pytest.fixture
def temp_dir() -> str:
    """A temporary directory for file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_file(temp_dir: str) -> str:
    """Create a temporary file with test content."""
    filepath = os.path.join(temp_dir, "test_file.txt")
    with open(filepath, "w") as f:
        f.write("line 1\nline 2\nline 3\n")
    return filepath
