"""
agent/tools.py — Tool implementations for the KDE AI Agent.

Provides:
  • bash_exec(cmd, timeout)     — Run shell commands, capture stdout/stderr
  • file_read(path, offset, limit) — Read file with line numbers
  • file_write(path, content)   — Write file, auto git commit
  • search_codebase(query, file_pattern) — ripgrep across project
  • repo_map(max_tokens)        — tree-sitter codebase summary (Aider-style)
  • run_tests(path)             — Auto-detect test runner and execute
  • ask_user(question, options) — Pause loop, surface question via D-Bus

Patterns extracted from: Aider (repomap, auto-commit), OpenCode (tool interface),
end4 (function calling schema), ZooCode/RooCode (tool result handling).
"""

import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ============================================================================
# Data Classes
# ============================================================================


class ToolResult:
    """Result of a single tool execution."""

    __slots__ = ("tool_name", "success", "output", "error", "metadata", "timestamp")

    def __init__(
        self,
        tool_name: str,
        success: bool,
        output: str = "",
        error: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ):
        self.tool_name = tool_name
        self.success = success
        self.output = output
        self.error = error
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


# ============================================================================
# Tool Registry
# ============================================================================


class ToolRegistry:
    """Registry of all available tools with OpenAI-compatible schemas."""

    def __init__(self, working_dir: Optional[str] = None, dbus_signal: Optional[Callable] = None):
        self._tools: Dict[str, Callable[[Dict[str, Any]], ToolResult]] = {}
        self.working_dir = working_dir or os.getcwd()
        self._dbus_signal = dbus_signal  # For ask_user

        # Register all tools
        self.register("bash_exec", self._bash_exec)
        self.register("file_read", self._file_read)
        self.register("file_write", self._file_write)
        self.register("search_codebase", self._search_codebase)
        self.register("repo_map", self._repo_map)
        self.register("run_tests", self._run_tests)
        self.register("ask_user", self._ask_user)
        self.register("cross_repo_search", self._cross_repo_search)
        self.register("cross_repo_trace", self._cross_repo_trace)
        self.register("system_monitor", self._system_monitor)
        self.register("voice_input", self._voice_input)
        self.register("tts_output", self._tts_output)

    def register(self, name: str, func: Callable[[Dict[str, Any]], ToolResult]) -> None:
        self._tools[name] = func

    # Internal tool definitions in a neutral format
    _TOOL_DEFINITIONS: List[Dict[str, Any]] = [
        {
            "name": "bash_exec",
            "description": (
                "Execute a shell command in the project directory. "
                "Returns stdout and stderr. Use for running build commands, "
                "git operations, system queries, and code analysis tools. "
                "Commands run non-interactively."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "Shell command to execute (e.g. 'pytest tests/', 'npm run build')",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 120, max: 600)",
                    },
                },
                "required": ["cmd"],
            },
        },
        {
            "name": "file_read",
            "description": (
                "Read a file from the project and return its contents with line numbers. "
                "Use before editing files to understand their current state."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file, relative to project root",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "1-based line offset to start reading from (default: 1)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of lines to return (default: 2000)",
                    },
                },
                "required": ["path"],
            },
        },
        {
            "name": "file_write",
            "description": (
                "Write content to a file. Creates parent directories if they don't exist. "
                "After writing, automatically stages the file with git add and creates a commit "
                "with a descriptive message. Use this for ALL file creation and modification."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write the file, relative to project root",
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete file content to write",
                    },
                    "commit_message": {
                        "type": "string",
                        "description": "Git commit message (auto-generated if not provided)",
                    },
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "search_codebase",
            "description": (
                "Search the codebase using ripgrep. Returns matching file paths with line numbers "
                "and surrounding context. Supports full regex syntax. "
                "Use to find function definitions, usages, patterns, and TODO comments."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (regex supported, e.g. 'def handle_|class Agent')",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file glob filter (e.g. '*.py', '*.qml')",
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Lines of context around each match (default: 2)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "repo_map",
            "description": (
                "Generate a tree-sitter based structural summary of the codebase showing "
                "all functions, classes, methods, and their signatures. "
                "Like Aider's repo map — provides the LLM with a high-level understanding "
                "of the project structure without reading every file."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "max_tokens": {
                        "type": "integer",
                        "description": "Approximate maximum tokens for the output (default: 1500)",
                    }
                },
            },
        },
        {
            "name": "run_tests",
            "description": (
                "Auto-detect the project's test framework and execute tests. "
                "Supports pytest (Python), cargo test (Rust), npm test (JavaScript/TypeScript), "
                "go test (Go), and ctest (C/C++). Returns test output with pass/fail summary."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional: specific test file or directory to run",
                    }
                },
            },
        },
        {
            "name": "ask_user",
            "description": (
                "Pause execution and ask the user a question via the QML UI. "
                "Use ONLY when a genuine blocker requires human input — never for "
                "confirmation of routine actions. The agent loop will wait for the user's response."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to display in the UI",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of preset answer choices",
                    },
                },
                "required": ["question"],
            },
        },
        {
            "name": "cross_repo_search",
            "description": (
                "Search across ALL indexed reference projects (OpenCode, Jarvis, Aider, "
                "llama.cpp, and other open-source projects) for code patterns, functions, "
                "classes, or architectural patterns. Uses the codebase-memory knowledge graph. "
                "Returns matching symbols with their source project, file path, and description. "
                "Use this to find how other projects implement similar features."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language or keyword search query (e.g. 'MCP client implementation', 'tool registry pattern')",
                    },
                    "project": {
                        "type": "string",
                        "description": "Optional: limit search to a specific project (e.g. 'opencode-main', 'jarvis-main')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10, max: 30)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "cross_repo_trace",
            "description": (
                "Trace function calls, data flow, or cross-service calls through "
                "a specific reference project's codebase. Uses the codebase-memory "
                "knowledge graph to follow CALLS, DATA_FLOWS, and HTTP_CALLS edges. "
                "Use this to understand how a specific function is called and what it calls."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Function or method name to trace (e.g. 'handleToolCall', 'RunTask')",
                    },
                    "project": {
                        "type": "string",
                        "description": "Project to trace in (e.g. 'opencode-main', 'jarvis-main')",
                    },
                    "direction": {
                        "type": "string",
                        "enum": ["inbound", "outbound", "both"],
                        "description": "Trace direction: inbound (callers), outbound (callees), or both (default: both)",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Trace depth (default: 2, max: 5)",
                    },
                },
                "required": ["function_name", "project"],
            },
        },
        {
            "name": "system_monitor",
            "description": (
                "Get real-time system metrics: CPU usage, memory usage, CPU temperature, "
                "disk usage, uptime, and kernel version. Reads from /proc filesystem. "
                "Use this to diagnose performance issues or check system health."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "metrics": {
                        "type": "string",
                        "description": "Comma-separated list of metrics to fetch: cpu, memory, temp, disk, uptime, all (default: all)",
                    },
                },
            },
        },
        {
            "name": "voice_input",
            "description": (
                "Record audio from the microphone and transcribe it to text using "
                "whisper.cpp or a system speech-to-text engine. "
                "Use this to accept voice commands instead of typing."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "duration": {
                        "type": "integer",
                        "description": "Recording duration in seconds (default: 5, max: 30)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language code for transcription (default: 'en')",
                    },
                },
            },
        },
        {
            "name": "tts_output",
            "description": (
                "Convert text to speech and play it through the system speakers. "
                "Uses system TTS engine (espeak-ng, festival, or speech-dispatcher). "
                "Use this to read responses aloud or provide audio feedback."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to convert to speech",
                    },
                    "voice": {
                        "type": "string",
                        "description": "Voice name or language (default: 'en')",
                    },
                    "speed": {
                        "type": "integer",
                        "description": "Speech speed in words per minute (default: 150, range: 80-450)",
                    },
                },
                "required": ["text"],
            },
        },
    ]

    def get_tool_schemas(self, fmt: str = "openai") -> List[Dict[str, Any]]:
        """Return tool definitions in the requested format.

        Args:
            fmt: "openai" for OpenAI-compatible APIs (llama.cpp, OpenRouter),
                 "anthropic" for Anthropic Claude API,
                 "internal" for the raw neutral format.
        """
        if fmt == "internal":
            return list(self._TOOL_DEFINITIONS)
        if fmt == "anthropic":
            return [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"],
                }
                for t in self._TOOL_DEFINITIONS
            ]
        # Default: OpenAI format
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in self._TOOL_DEFINITIONS
        ]

    def execute(self, name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a tool by name with the given arguments."""
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Unknown tool: {name}. Available: {list(self._tools.keys())}",
            )
        try:
            return self._tools[name](args)
        except Exception as exc:
            return ToolResult(tool_name=name, success=False, error=str(exc))

    # ========================================================================
    # Tool Implementations
    # ========================================================================

    def _bash_exec(self, args: Dict[str, Any]) -> ToolResult:
        cmd = args["cmd"]
        timeout = min(args.get("timeout", 120), 600)
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
                env={**os.environ, "PAGER": "cat"},
            )
            output_parts = []
            if result.stdout:
                output_parts.append(result.stdout.rstrip())
            if result.stderr:
                output_parts.append(f"\n--- STDERR ---\n{result.stderr.rstrip()}")
            output = "\n".join(output_parts) if output_parts else "(no output)"

            return ToolResult(
                tool_name="bash_exec",
                success=(result.returncode == 0),
                output=output,
                metadata={
                    "command": cmd,
                    "exit_code": result.returncode,
                    "directory": self.working_dir,
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="bash_exec",
                success=False,
                error=f"Command timed out after {timeout}s: {cmd}",
                metadata={"command": cmd, "timeout": timeout},
            )
        except FileNotFoundError:
            return ToolResult(
                tool_name="bash_exec",
                success=False,
                error=f"Shell not found or command not available: {cmd}",
            )

    def _file_read(self, args: Dict[str, Any]) -> ToolResult:
        path = args["path"]
        offset = args.get("offset", 1)
        limit = args.get("limit", 2000)

        p = (Path(self.working_dir) / path).resolve()
        # Security: prevent reading outside working dir
        try:
            p.relative_to(Path(self.working_dir).resolve())
        except ValueError:
            return ToolResult(
                tool_name="file_read",
                success=False,
                error=f"Security: path escapes working directory: {path}",
            )

        if not p.exists():
            return ToolResult(tool_name="file_read", success=False, error=f"File not found: {path}")
        if p.is_dir():
            # If directory, list contents
            try:
                items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name))
                lines = []
                for item in items:
                    suffix = "/" if item.is_dir() else ""
                    lines.append(f"  {item.name}{suffix}")
                return ToolResult(
                    tool_name="file_read",
                    success=True,
                    output=f"[Directory: {path}]\n" + "\n".join(lines),
                    metadata={"path": str(p), "is_directory": True, "item_count": len(lines)},
                )
            except PermissionError:
                return ToolResult(tool_name="file_read", success=False, error=f"Permission denied: {path}")

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return ToolResult(tool_name="file_read", success=False, error=f"Binary file: {path}")
        except PermissionError:
            return ToolResult(tool_name="file_read", success=False, error=f"Permission denied: {path}")

        lines = content.splitlines()
        total = len(lines)
        start = max(0, offset - 1)
        end = min(start + limit, total)
        selected = lines[start:end]
        numbered = "\n".join(f"{i + 1:6d}|{line}" for i, line in enumerate(selected, start))
        header = f"[{path}] lines {start + 1}-{end} of {total}\n"

        return ToolResult(
            tool_name="file_read",
            success=True,
            output=header + numbered,
            metadata={"path": str(p), "total_lines": total, "start": start + 1, "end": end},
        )

    def _file_write(self, args: Dict[str, Any]) -> ToolResult:
        file_path = args["path"]
        content = args["content"]
        commit_message = args.get("commit_message")

        p = (Path(self.working_dir) / file_path).resolve()
        # Security check
        try:
            p.relative_to(Path(self.working_dir).resolve())
        except ValueError:
            return ToolResult(
                tool_name="file_write",
                success=False,
                error=f"Security: path escapes working directory: {file_path}",
            )

        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        previous_content = None
        if existed:
            try:
                previous_content = p.read_text()
            except Exception:
                pass

        p.write_text(content, encoding="utf-8")

        # Auto git commit (pattern: Aider's auto_commits)
        git_info = ""
        try:
            subprocess.run(
                ["git", "add", str(p)],
                capture_output=True, text=True, check=True, cwd=self.working_dir,
            )
            if not commit_message:
                action = "update" if existed else "create"
                commit_message = f"{action}: {file_path}"
            commit_result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                capture_output=True, text=True, cwd=self.working_dir,
            )
            if commit_result.returncode == 0:
                git_info = f"\n✓ Git commit: {commit_result.stdout.strip().split(chr(10))[0]}"
            else:
                git_info = f"\nGit: {commit_result.stderr.strip()}"
        except FileNotFoundError:
            git_info = ""
        except subprocess.CalledProcessError:
            git_info = ""

        return ToolResult(
            tool_name="file_write",
            success=True,
            output=f"{'Updated' if existed else 'Created'} {file_path}{git_info}",
            metadata={
                "path": str(p),
                "existed": existed,
                "size_bytes": len(content),
                "previous_size_bytes": len(previous_content) if previous_content else 0,
            },
        )

    def _search_codebase(self, args: Dict[str, Any]) -> ToolResult:
        query = args["query"]
        file_pattern = args.get("file_pattern")
        context_lines = args.get("context_lines", 2)

        cmd = ["rg", "--line-number", "--no-heading", "--color=never", f"--context={context_lines}"]
        if file_pattern:
            cmd.extend(["--glob", file_pattern])
        cmd.append(query)

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, cwd=self.working_dir,
            )
            stdout = result.stdout.strip()
            if not stdout:
                return ToolResult(
                    tool_name="search_codebase",
                    success=True,
                    output=f"No matches found for: {query}",
                    metadata={"query": query, "match_count": 0},
                )
            match_count = len([l for l in stdout.splitlines() if not l.startswith("--")])
            # Truncate if too large
            max_chars = 8000
            if len(stdout) > max_chars:
                stdout = stdout[:max_chars] + f"\n... (truncated, {match_count} total matches)"

            return ToolResult(
                tool_name="search_codebase",
                success=True,
                output=stdout,
                metadata={"query": query, "match_count": match_count, "pattern": file_pattern},
            )
        except FileNotFoundError:
            # Fallback to Python's own recursive grep
            return self._fallback_grep(query, file_pattern)

    def _fallback_grep(self, query: str, file_pattern: Optional[str]) -> ToolResult:
        """Fallback code search using Python when ripgrep is not available."""
        results: List[str] = []
        root = Path(self.working_dir)
        try:
            compiled = re.compile(query)
        except re.error:
            compiled = re.compile(re.escape(query))

        for p in root.rglob("*"):
            if ".git" in p.parts or "__pycache__" in p.parts:
                continue
            if file_pattern and not p.match(file_pattern):
                continue
            if not p.is_file():
                continue
            if p.suffix in {".pyc", ".pyo", ".so", ".o", ".a", ".exe", ".zip", ".gz", ".tar"}:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if compiled.search(line):
                    rel = p.relative_to(root)
                    results.append(f"{rel}:{i}:{line}")
                    if len(results) > 500:
                        break
            if len(results) > 500:
                break

        output = "\n".join(results[:500]) if results else f"No matches found for: {query}"
        return ToolResult(
            tool_name="search_codebase",
            success=True,
            output=output,
            metadata={"query": query, "match_count": len(results), "fallback": True},
        )

    def _repo_map(self, args: Dict[str, Any]) -> ToolResult:
        """Generate a tree-sitter structural map of the codebase."""
        max_tokens = args.get("max_tokens", 1500)

        try:
            from tree_sitter import Language, Parser

            # Try to load tree-sitter languages
            languages_loaded = self._load_tree_sitter_languages()
        except ImportError:
            return self._fallback_repo_map(max_tokens)
        except Exception:
            return self._fallback_repo_map(max_tokens)

        if not languages_loaded:
            return self._fallback_repo_map(max_tokens)

        root = Path(self.working_dir)
        map_entries: List[str] = []
        total_symbols = 0
        max_entries = max_tokens * 2  # Rough estimate

        for p in sorted(root.rglob("*")):
            if total_symbols >= max_entries:
                break
            if ".git" in p.parts or "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            if not p.is_file():
                continue
            if p.suffix not in {".py", ".js", ".ts", ".go", ".rs", ".qml", ".cpp", ".h", ".c"}:
                continue
            if p.stat().st_size > 500_000:  # Skip files > 500KB
                continue

            rel = p.relative_to(root)
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            symbols = self._extract_symbols_tree_sitter(str(rel), text, p.suffix)
            if symbols:
                map_entries.append(f"\n{rel}:")
                for sym in symbols[:30]:  # Max 30 symbols per file
                    map_entries.append(f"  {sym}")
                    total_symbols += 1
                    if total_symbols >= max_entries:
                        break

        header = f"# Repository Map ({self.working_dir})\n"
        header += f"# {total_symbols} symbols extracted\n"
        output = header + "\n".join(map_entries)
        # Truncate to approximate token limit (4 chars ~= 1 token)
        char_limit = max_tokens * 4
        if len(output) > char_limit:
            output = output[:char_limit] + "\n... (truncated)"

        return ToolResult(
            tool_name="repo_map",
            success=True,
            output=output,
            metadata={"symbol_count": total_symbols, "method": "tree-sitter"},
        )

    def _fallback_repo_map(self, max_tokens: int = 1500) -> ToolResult:
        """Fallback repo map using regex-based symbol extraction."""
        root = Path(self.working_dir)
        map_entries: List[str] = []
        total_symbols = 0
        max_entries = max_tokens * 2

        patterns = [
            (".py", re.compile(r"^\s*(def |class |async def )\s*(\w+)")),
            (".js", re.compile(r"^\s*(function |class |const |let |var )\s*(\w+)")),
            (".ts", re.compile(r"^\s*(function |class |interface |const |let |var )\s*(\w+)")),
            (".go", re.compile(r"^\s*(func |type |var )\s*(\w+)")),
            (".rs", re.compile(r"^\s*(pub )?(fn |struct |enum |trait |impl )\s*(\w+)")),
            (".qml", re.compile(r"^\s*(import |property |function |signal |Component |Item |Rectangle)\s")),
            (".cpp", re.compile(r"^\s*(\w+::\w+|\w+\s+\w+::\w+)")),
            (".h", re.compile(r"^\s*(class |struct |enum |typedef )\s")),
        ]

        for p in sorted(root.rglob("*")):
            if total_symbols >= max_entries:
                break
            if ".git" in p.parts or "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            if not p.is_file():
                continue

            matching_pattern = None
            for ext, pat in patterns:
                if p.suffix == ext:
                    matching_pattern = pat
                    break
            if not matching_pattern:
                continue

            rel = p.relative_to(root)
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            symbols: List[str] = []
            for i, line in enumerate(text.splitlines(), 1):
                m = matching_pattern.search(line)
                if m:
                    symbols.append(f"  L{i:4d}: {line.strip()[:120]}")
                    total_symbols += 1
                    if total_symbols >= max_entries:
                        break

            if symbols:
                map_entries.append(f"\n{rel}:")
                map_entries.extend(symbols[:30])

        header = f"# Repository Map ({self.working_dir})\n"
        header += f"# {total_symbols} symbols extracted (regex fallback)\n"
        output = header + "\n".join(map_entries)
        char_limit = max_tokens * 4
        if len(output) > char_limit:
            output = output[:char_limit] + "\n... (truncated)"

        return ToolResult(
            tool_name="repo_map",
            success=True,
            output=output,
            metadata={"symbol_count": total_symbols, "method": "regex-fallback"},
        )

    def _load_tree_sitter_languages(self) -> bool:
        """Load tree-sitter language parsers. Returns True if at least one loaded."""
        try:
            from tree_sitter import Language, Parser  # noqa: F811

            # Try to find pre-built language libraries
            self._ts_languages: Dict[str, Any] = {}
            lang_paths = [
                Path.home() / ".local" / "share" / "tree-sitter",
                Path("/usr/lib/tree-sitter"),
                Path("/usr/local/lib/tree-sitter"),
            ]
            for base in lang_paths:
                if base.exists():
                    for so_file in base.glob("*.so"):
                        try:
                            lang_name = so_file.stem.replace("lib", "").replace("tree-sitter-", "").replace("tree_sitter_", "")
                            lang = Language(str(so_file), lang_name)
                            self._ts_languages[lang_name] = lang
                        except Exception:
                            pass
            return len(self._ts_languages) > 0
        except Exception:
            return False

    def _extract_symbols_tree_sitter(self, rel_path: str, text: str, suffix: str) -> List[str]:
        """Extract symbols using tree-sitter for a specific file."""
        lang_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".go": "go", ".rs": "rust", ".cpp": "cpp", ".c": "c", ".h": "c",
        }
        lang_name = lang_map.get(suffix)
        if not lang_name or lang_name not in getattr(self, "_ts_languages", {}):
            return []

        try:
            from tree_sitter import Parser
            parser = Parser()
            parser.set_language(self._ts_languages[lang_name])
            tree = parser.parse(bytes(text, "utf-8"))

            query_str = self._get_tree_sitter_query(lang_name)
            if not query_str:
                return []

            query = self._ts_languages[lang_name].query(query_str)
            captures = query.captures(tree.root_node)

            symbols: List[str] = []
            for node, tag in captures:
                start_row = node.start_point[0] + 1
                name = text[node.start_byte:node.end_byte].splitlines()[0].strip()[:100]
                symbols.append(f"  L{start_row:4d}: [{tag}] {name}")

            return symbols
        except Exception:
            return []

    @staticmethod
    def _get_tree_sitter_query(lang: str) -> str:
        """Tree-sitter queries for extracting definitions per language."""
        queries = {
            "python": """
                (function_definition name: (identifier) @function)
                (class_definition name: (identifier) @class)
                (decorated_definition (function_definition name: (identifier) @function))
            """,
            "javascript": """
                (function_declaration name: (identifier) @function)
                (class_declaration name: (identifier) @class)
                (method_definition name: (property_identifier) @method)
                (arrow_function) @function
            """,
            "typescript": """
                (function_declaration name: (identifier) @function)
                (class_declaration name: (identifier) @class)
                (method_definition name: (property_identifier) @method)
                (interface_declaration name: (type_identifier) @interface)
            """,
            "go": """
                (function_declaration name: (identifier) @function)
                (method_declaration name: (field_identifier) @method)
                (type_spec name: (type_identifier) @type)
            """,
            "rust": """
                (function_item name: (identifier) @function)
                (struct_item name: (type_identifier) @struct)
                (enum_item name: (type_identifier) @enum)
                (impl_item type: (_) @impl)
                (trait_item name: (type_identifier) @trait)
            """,
        }
        return queries.get(lang, "")

    def _run_tests(self, args: Dict[str, Any]) -> ToolResult:
        """Auto-detect test framework and run tests."""
        test_path = args.get("path", "")
        root = Path(self.working_dir)

        # Detect test framework
        detectors = [
            ("pytest", ["pytest", "-x", "--tb=short"]),
            ("cargo", ["cargo", "test"]),
            ("npm", ["npm", "test"]),
            ("go", ["go", "test", "./..."]),
            ("ctest", ["ctest", "--output-on-failure"]),
        ]

        # Check for common test config files
        has_cargo = (root / "Cargo.toml").exists()
        has_pytest = (root / "pytest.ini").exists() or (root / "pyproject.toml").exists() or list(root.glob("*test*.py"))
        has_package_json = (root / "package.json").exists()
        has_go_mod = (root / "go.mod").exists()
        has_ctest = (root / "CTestTestfile.cmake").exists() or (root / "CMakeLists.txt").exists()

        selected_cmd = None
        if has_pytest and not has_cargo:
            selected_cmd = ["pytest", "-x", "--tb=short", "-v"]
        elif has_cargo:
            selected_cmd = ["cargo", "test"]
        elif has_package_json:
            selected_cmd = ["npm", "test"]
        elif has_go_mod:
            selected_cmd = ["go", "test", "./..."]
        elif has_ctest:
            selected_cmd = ["ctest", "--output-on-failure"]
        else:
            return ToolResult(
                tool_name="run_tests",
                success=False,
                error="Could not detect test framework. Supported: pytest, cargo test, npm test, go test, ctest",
            )

        if test_path:
            if selected_cmd[0] == "pytest":
                selected_cmd.append(test_path)
            elif selected_cmd[0] == "go":
                selected_cmd[-1] = "./" + test_path

        try:
            result = subprocess.run(
                selected_cmd,
                capture_output=True, text=True, timeout=300,
                cwd=self.working_dir,
            )
            output = result.stdout.rstrip()
            if result.stderr:
                output += f"\n--- STDERR ---\n{result.stderr.rstrip()}"
            # Summarize
            summary = "✓ Tests passed" if result.returncode == 0 else "✗ Tests failed"
            return ToolResult(
                tool_name="run_tests",
                success=(result.returncode == 0),
                output=f"{summary}\nCommand: {' '.join(selected_cmd)}\n\n{output}",
                metadata={
                    "command": " ".join(selected_cmd),
                    "exit_code": result.returncode,
                    "framework": selected_cmd[0],
                },
            )
        except subprocess.TimeoutExpired:
            return ToolResult(tool_name="run_tests", success=False, error="Tests timed out after 300s")
        except FileNotFoundError:
            return ToolResult(tool_name="run_tests", success=False, error=f"Test runner '{selected_cmd[0]}' not found")

    def _ask_user(self, args: Dict[str, Any]) -> ToolResult:
        """Pause the agent loop and ask the user a question via D-Bus signal."""
        question = args["question"]
        options = args.get("options", [])

        # Signal via D-Bus if available
        if self._dbus_signal:
            try:
                self._dbus_signal("QuestionAsked", {
                    "question": question,
                    "options": options,
                    "timestamp": datetime.now().isoformat(),
                })
                return ToolResult(
                    tool_name="ask_user",
                    success=True,
                    output=f"Question sent to UI: {question}",
                    metadata={"question": question, "options": options, "awaiting_response": True},
                )
            except Exception as exc:
                return ToolResult(
                    tool_name="ask_user",
                    success=False,
                    error=f"Failed to send question via D-Bus: {exc}",
                )
        else:
            # Fallback: print to stdout
            print(f"\n[AGENT QUESTION] {question}")
            if options:
                for i, opt in enumerate(options):
                    print(f"  [{i+1}] {opt}")
            try:
                answer = input("> ").strip()
                return ToolResult(
                    tool_name="ask_user",
                    success=True,
                    output=f"User response: {answer}",
                    metadata={"question": question, "answer": answer},
                )
            except EOFError:
                return ToolResult(
                    tool_name="ask_user",
                    success=True,
                    output="User response: (no input available)",
                    metadata={"question": question, "answer": None},
                )

    # ========================================================================
    # Cross-Repository Intelligence Tools
    # ========================================================================

    def _cross_repo_search(self, args: Dict[str, Any]) -> ToolResult:
        """Search across all indexed reference projects using codebase-memory."""
        query = args.get("query", "")
        project = args.get("project", "")
        limit = min(args.get("limit", 10), 30)

        if not query:
            return ToolResult(
                tool_name="cross_repo_search",
                success=False,
                error="Query is required",
            )

        try:
            # Use codebase-memory search_graph via bash
            cmd_parts = [
                "codebase-memory", "search-graph",
                "--project", project if project else "*",
                "--query", query,
                "--limit", str(limit),
            ]
            result = subprocess.run(
                cmd_parts,
                capture_output=True, text=True, timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
            else:
                # Fallback: try via MCP tool if codebase-memory CLI not available
                output = self._fallback_cross_repo_search(query, project, limit)

            return ToolResult(
                tool_name="cross_repo_search",
                success=True,
                output=output,
                metadata={"query": query, "project": project or "all", "limit": limit},
            )

        except FileNotFoundError:
            # codebase-memory CLI not installed, try fallback
            output = self._fallback_cross_repo_search(query, project, limit)
            return ToolResult(
                tool_name="cross_repo_search",
                success=True,
                output=output,
                metadata={"query": query, "project": project or "all", "limit": limit, "method": "fallback"},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="cross_repo_search",
                success=False,
                error="Cross-repo search timed out after 30s",
            )
        except Exception as exc:
            return ToolResult(
                tool_name="cross_repo_search",
                success=False,
                error=f"Cross-repo search failed: {exc}",
            )

    def _fallback_cross_repo_search(self, query: str, project: str, limit: int) -> str:
        """Fallback: use ripgrep across known reference project directories."""
        ref_dirs = []

        # Known reference project locations
        known_projects = {
            "opencode-main": os.path.expanduser("~/ecosystem/source-codes/opencode-main/opencode-main"),
            "jarvis-main": os.path.expanduser("~/ecosystem/source-codes/jarvis-main/jarvis-main"),
        }

        if project and project in known_projects:
            ref_dirs = [known_projects[project]]
        elif project:
            ref_dirs = [os.path.expanduser(f"~/ecosystem/source-codes/{project}")]
        else:
            ref_dirs = list(known_projects.values())

        results = []
        for ref_dir in ref_dirs:
            if not os.path.isdir(ref_dir):
                continue
            proj_name = os.path.basename(ref_dir)
            try:
                rg_result = subprocess.run(
                    ["rg", "--line-number", "--no-heading", "--color=never",
                     "-g", "*.py", "-g", "*.go", "-g", "*.ts", "-g", "*.rs",
                     "-m", "5", query, ref_dir],
                    capture_output=True, text=True, timeout=15,
                )
                if rg_result.stdout.strip():
                    lines = rg_result.stdout.strip().splitlines()[:limit]
                    results.append(f"\n## {proj_name}")
                    results.extend(f"  {l}" for l in lines)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

        if results:
            return "\n".join(results)
        return f"No cross-repo results found for: {query}"

    def _cross_repo_trace(self, args: Dict[str, Any]) -> ToolResult:
        """Trace function calls through a reference project using codebase-memory."""
        function_name = args.get("function_name", "")
        project = args.get("project", "")
        direction = args.get("direction", "both")
        depth = min(args.get("depth", 2), 5)

        if not function_name or not project:
            return ToolResult(
                tool_name="cross_repo_trace",
                success=False,
                error="Both function_name and project are required",
            )

        try:
            cmd_parts = [
                "codebase-memory", "trace-path",
                "--project", project,
                "--function", function_name,
                "--direction", direction,
                "--depth", str(depth),
            ]
            result = subprocess.run(
                cmd_parts,
                capture_output=True, text=True, timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                output = result.stdout.strip()
            else:
                output = f"Trace: {function_name} in {project} ({direction}, depth={depth})\n"
                output += "(codebase-memory CLI not available. Install with: pip install codebase-memory)"

            return ToolResult(
                tool_name="cross_repo_trace",
                success=True,
                output=output,
                metadata={
                    "function": function_name,
                    "project": project,
                    "direction": direction,
                    "depth": depth,
                },
            )

        except FileNotFoundError:
            return ToolResult(
                tool_name="cross_repo_trace",
                success=True,
                output=f"codebase-memory CLI not available. Install to enable trace.\n"
                       f"Requested: trace {function_name} in {project} ({direction}, depth={depth})",
                metadata={"function": function_name, "project": project, "available": False},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                tool_name="cross_repo_trace",
                success=False,
                error="Cross-repo trace timed out after 30s",
            )
        except Exception as exc:
            return ToolResult(
                tool_name="cross_repo_trace",
                success=False,
                error=f"Cross-repo trace failed: {exc}",
            )

    # ========================================================================
    # System Monitoring (pattern: Jarvis readCpuUsage, readMemoryUsage, readCpuTemp)
    # ========================================================================

    def _system_monitor(self, args: Dict[str, Any]) -> ToolResult:
        """Get real-time system metrics by reading /proc filesystem.

        Pattern from Jarvis: jarvissystem.cpp readCpuUsage, readMemoryUsage, readCpuTemp
        """
        metrics_str = args.get("metrics", "all").lower()
        requested = [m.strip() for m in metrics_str.split(",")]
        want_all = "all" in requested

        result_parts = []

        # ── CPU Usage (pattern: Jarvis /proc/stat) ──
        if want_all or "cpu" in requested:
            try:
                with open("/proc/stat") as f:
                    line = f.readline()
                parts = line.split()
                if parts and parts[0] == "cpu" and len(parts) >= 8:
                    user, nice, sys, idle = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
                    total = user + nice + sys + idle + int(parts[5]) + int(parts[6]) + int(parts[7])
                    # Read again after short delay for delta
                    import time
                    time.sleep(0.1)
                    with open("/proc/stat") as f:
                        line2 = f.readline()
                    parts2 = line2.split()
                    if parts2 and parts2[0] == "cpu" and len(parts2) >= 8:
                        idle2 = int(parts2[4])
                        total2 = sum(int(parts2[i]) for i in range(1, 8))
                        total_diff = total2 - total
                        idle_diff = idle2 - idle
                        if total_diff > 0:
                            cpu_pct = 100.0 * (1.0 - idle_diff / total_diff)
                            result_parts.append(f"CPU Usage: {cpu_pct:.1f}%")
            except Exception as exc:
                result_parts.append(f"CPU: error ({exc})")

        # ── Memory Usage (pattern: Jarvis /proc/meminfo) ──
        if want_all or "memory" in requested:
            try:
                with open("/proc/meminfo") as f:
                    content = f.read()
                mem_total = mem_available = 0
                for line in content.splitlines():
                    if line.startswith("MemTotal:"):
                        mem_total = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        mem_available = int(line.split()[1])
                    if mem_total > 0 and mem_available > 0:
                        break
                if mem_total > 0:
                    used_gb = (mem_total - mem_available) / 1048576.0
                    total_gb = mem_total / 1048576.0
                    pct = 100.0 * (mem_total - mem_available) / mem_total
                    result_parts.append(f"Memory: {used_gb:.1f}GB / {total_gb:.1f}GB ({pct:.1f}%)")
            except Exception as exc:
                result_parts.append(f"Memory: error ({exc})")

        # ── CPU Temperature (pattern: Jarvis /sys/class/thermal) ──
        if want_all or "temp" in requested:
            temp_paths = [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/hwmon/hwmon0/temp1_input",
                "/sys/class/hwmon/hwmon1/temp1_input",
            ]
            for tp in temp_paths:
                try:
                    with open(tp) as f:
                        raw = f.read().strip()
                    temp_c = int(raw) / 1000 if len(raw) > 3 else int(raw)
                    result_parts.append(f"CPU Temperature: {temp_c}°C")
                    break
                except (FileNotFoundError, PermissionError, ValueError):
                    continue

        # ── Disk Usage ──
        if want_all or "disk" in requested:
            try:
                stat = os.statvfs("/")
                total_bytes = stat.f_frsize * stat.f_blocks
                free_bytes = stat.f_frsize * stat.f_bfree
                used_bytes = total_bytes - free_bytes
                total_gb = total_bytes / (1024**3)
                used_gb = used_bytes / (1024**3)
                pct = 100.0 * used_bytes / total_bytes if total_bytes > 0 else 0
                result_parts.append(f"Disk (/): {used_gb:.1f}GB / {total_gb:.1f}GB ({pct:.1f}%)")
            except Exception as exc:
                result_parts.append(f"Disk: error ({exc})")

        # ── Uptime ──
        if want_all or "uptime" in requested:
            try:
                with open("/proc/uptime") as f:
                    uptime_sec = float(f.read().split()[0])
                days = int(uptime_sec // 86400)
                hours = int((uptime_sec % 86400) // 3600)
                minutes = int((uptime_sec % 3600) // 60)
                result_parts.append(f"Uptime: {days}d {hours}h {minutes}m")
            except Exception as exc:
                result_parts.append(f"Uptime: error ({exc})")

        output = "\n".join(result_parts) if result_parts else "No metrics available"
        return ToolResult(
            tool_name="system_monitor",
            success=True,
            output=output,
            metadata={"metrics_requested": requested},
        )

    # ========================================================================
    # Voice Input (whisper.cpp integration)
    # ========================================================================

    def _voice_input(self, args: Dict[str, Any]) -> ToolResult:
        """Record audio and transcribe using whisper.cpp or system STT.

        Pattern from Jarvis: whisper.cpp integration via CMake FetchContent
        """
        duration = min(args.get("duration", 5), 30)
        language = args.get("language", "en")

        # Try whisper.cpp first
        whisper_binary = shutil.which("whisper-cli") or shutil.which("whisper")
        if whisper_binary:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    wav_path = tmp.name

                # Record audio with arecord (ALSA) or parec (PulseAudio)
                record_cmd = []
                if shutil.which("parec"):
                    record_cmd = ["parec", "--format=s16le", "--rate=16000",
                                  f"--record-duration={duration}", wav_path]
                elif shutil.which("arecord"):
                    record_cmd = ["arecord", "-f", "S16_LE", "-r", "16000",
                                  "-d", str(duration), wav_path]
                else:
                    return ToolResult(
                        tool_name="voice_input",
                        success=False,
                        error="No recording tool found. Install parec (pulseaudio-utils) or arecord (alsa-utils)",
                    )

                subprocess.run(record_cmd, capture_output=True, text=True, timeout=duration + 5)

                # Transcribe with whisper
                whisper_result = subprocess.run(
                    [whisper_binary, "-f", wav_path, "-l", language, "--no-prints"],
                    capture_output=True, text=True, timeout=60,
                )

                os.unlink(wav_path)

                text = whisper_result.stdout.strip() or "(no speech detected)"
                return ToolResult(
                    tool_name="voice_input",
                    success=True,
                    output=text,
                    metadata={"duration": duration, "language": language, "engine": "whisper"},
                )

            except subprocess.TimeoutExpired:
                return ToolResult(
                    tool_name="voice_input",
                    success=False,
                    error="Voice recording/transcription timed out",
                )
            except Exception as exc:
                return ToolResult(
                    tool_name="voice_input",
                    success=False,
                    error=f"Voice input failed: {exc}",
                )

        # Fallback: check if any STT is available
        return ToolResult(
            tool_name="voice_input",
            success=True,
            output=f"Voice input requires whisper.cpp. Install with:\n"
                   f"  pip install whisper-cpp\n"
                   f"  or build from source: https://github.com/ggerganov/whisper.cpp\n"
                   f"Requested: {duration}s recording in {language}",
            metadata={"available": False, "duration": duration, "language": language},
        )

    # ========================================================================
    # TTS Output (text-to-speech)
    # ========================================================================

    def _tts_output(self, args: Dict[str, Any]) -> ToolResult:
        """Convert text to speech and play through system speakers.

        Tries: espeak-ng → festival → speech-dispatcher → spd-say
        """
        text = args.get("text", "")
        voice = args.get("voice", "en")
        speed = min(max(args.get("speed", 150), 80), 450)

        if not text:
            return ToolResult(
                tool_name="tts_output",
                success=False,
                error="Text is required for TTS",
            )

        # Truncate very long text
        if len(text) > 2000:
            text = text[:2000] + "..."

        # Try espeak-ng (most common on Arch)
        espeak = shutil.which("espeak-ng") or shutil.which("espeak")
        if espeak:
            try:
                subprocess.run(
                    [espeak, "-v", voice, "-s", str(speed), text],
                    capture_output=True, text=True, timeout=30,
                )
                return ToolResult(
                    tool_name="tts_output",
                    success=True,
                    output=f"Spoken: {text[:100]}...",
                    metadata={"engine": "espeak", "voice": voice, "speed": speed, "length": len(text)},
                )
            except Exception as exc:
                return ToolResult(
                    tool_name="tts_output",
                    success=False,
                    error=f"TTS failed: {exc}",
                )

        # Try spd-say (speech-dispatcher)
        spd_say = shutil.which("spd-say")
        if spd_say:
            try:
                subprocess.run(
                    [spd_say, "-l", voice, "-r", str(speed), text],
                    capture_output=True, text=True, timeout=30,
                )
                return ToolResult(
                    tool_name="tts_output",
                    success=True,
                    output=f"Spoken: {text[:100]}...",
                    metadata={"engine": "speech-dispatcher", "voice": voice, "speed": speed},
                )
            except Exception as exc:
                return ToolResult(
                    tool_name="tts_output",
                    success=False,
                    error=f"TTS failed: {exc}",
                )

        # No TTS engine found
        return ToolResult(
            tool_name="tts_output",
            success=True,
            output=f"TTS output requires espeak-ng or speech-dispatcher.\n"
                   f"Install with: sudo pacman -S espeak-ng\n"
                   f"Requested: '{text[:100]}...' in {voice} at {speed} wpm",
            metadata={"available": False, "text_length": len(text)},
        )
