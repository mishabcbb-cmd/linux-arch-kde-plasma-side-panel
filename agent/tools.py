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

    def register(self, name: str, func: Callable[[Dict[str, Any]], ToolResult]) -> None:
        self._tools[name] = func

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return OpenAI/Anthropic-compatible tool definitions."""
        return [
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
