"""
agent/agent_loop.py — ReAct (Reasoning + Acting) agent loop.

The core execution loop inspired by Aider's coder loop:
  1. Inject task + repo_map + file context into LLM context
  2. Stream LLM response — tokens go to QML ChatView in real time
  3. Parse tool calls from LLM response
  4. Execute each tool, capture structured result
  5. Append tool results back to context
  6. Repeat until LLM signals TASK_COMPLETE

Every tool call, result, and error is:
  - Streamed to QML UI via D-Bus signal (pattern: end4's streaming pattern)
  - Logged as a structured event (ready for OpenObserve sink)

Patterns from:
  - Aider (base_coder.py run loop, auto_commits, repo_map injection)
  - OpenCode (agent.go: Run/Cancel/IsBusy, pubsub events)
  - end4 (Ai.qml: streaming append, color-coded message types)
  - ZooCode/RooCode (tool result → context feedback loop)
"""

import json
import logging
import signal
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

from .context_manager import ContextManager
from .llm_client import (
    BaseLLMProvider,
    EventType,
    Message,
    ProviderResponse,
    StreamEvent,
    TokenUsage,
    create_provider_from_config,
)
from .mcp_client import MCPClientManager
from .tools import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


# ============================================================================
# Agent States
# ============================================================================


class AgentStatus(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_USER = "waiting_user"
    COMPLETE = "complete"
    ERROR = "error"


# ============================================================================
# Signal Types (for UI / D-Bus)
# ============================================================================


class AgentSignalType(str, Enum):
    STATUS_CHANGED = "status_changed"
    LLM_THOUGHT = "llm_thought"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_RESULT = "tool_call_result"
    TOKEN_STREAM = "token_stream"
    TASK_COMPLETE = "task_complete"
    ERROR = "error"
    QUESTION_ASKED = "question_asked"


# ============================================================================
# Agent Events (for OpenObserve logging)
# ============================================================================


class AgentEvent:
    """Structured event for logging and streaming."""

    __slots__ = ("event_type", "data", "timestamp")

    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ============================================================================
# Agent Loop
# ============================================================================


class AgentLoop:
    """The main ReAct agent loop.

    Usage:
        agent = AgentLoop(config)
        agent.set_signal_handler(my_handler)  # for UI/D-Bus signals
        agent.run_task("Create a hello world script")
    """

    MAX_ITERATIONS = 50
    TOOL_TIMEOUT = 120  # seconds

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.working_dir = config.get("working_dir", ".")

        # Components
        self.provider: BaseLLMProvider = create_provider_from_config(config)
        self.context: ContextManager = ContextManager(
            max_input_tokens=config.get("max_input_tokens", 100_000),
            max_output_tokens=config.get("max_output_tokens", 8_192),
        )
        self.tools = ToolRegistry(
            working_dir=self.working_dir,
            dbus_signal=None,  # Set later via set_signal_handler
        )

        # MCP Client Manager — connects to external MCP servers
        self.mcp_client = MCPClientManager()
        mcp_servers_config = config.get("mcp_servers", {})
        if mcp_servers_config:
            self.mcp_client.load_from_config(mcp_servers_config)
            logger.info(
                f"MCP client initialized: {len(self.mcp_client.connected_servers)} servers, "
                f"{self.mcp_client.total_tools} tools"
            )

        # State
        self.status: AgentStatus = AgentStatus.IDLE
        self._stop_flag = threading.Event()
        self._current_task: str = ""
        self._iteration: int = 0
        self._total_tool_calls: int = 0
        self._session_start: Optional[datetime] = None
        self._accumulated_tokens: TokenUsage = TokenUsage()

        # Callbacks
        self._signal_handler: Optional[Callable[[AgentSignalType, Dict[str, Any]], None]] = None
        self._event_handler: Optional[Callable[[AgentEvent], None]] = None
        self._user_response: Optional[str] = None
        self._user_response_event = threading.Event()

        # Thread safety
        self._lock = threading.RLock()

    # ========================================================================
    # Public API
    # ========================================================================

    def set_signal_handler(
        self,
        handler: Callable[[AgentSignalType, Dict[str, Any]], None],
    ) -> None:
        """Set handler for UI signals (D-Bus or WebSocket)."""
        self._signal_handler = handler

    def set_event_handler(self, handler: Callable[[AgentEvent], None]) -> None:
        """Set handler for structured events (OpenObserve log sink)."""
        self._event_handler = handler

    def set_dbus_signal(self, signal_func: Callable) -> None:
        """Set the D-Bus signal emitter for ask_user."""
        self.tools._dbus_signal = signal_func

    def run_task(self, task: str, file_context: Optional[List[str]] = None) -> bool:
        """Run the agent loop for a given task. Returns True if completed successfully."""
        with self._lock:
            if self.status not in (AgentStatus.IDLE, AgentStatus.COMPLETE, AgentStatus.ERROR):
                logger.warning(f"Cannot start task: agent is {self.status.value}")
                return False

            self._reset(task)

        self._emit_signal(AgentSignalType.STATUS_CHANGED, {"status": AgentStatus.THINKING.value})

        try:
            self._session_start = datetime.now()
            self._log_event("session_start", {"task": task, "config": {
                "provider": self.config.get("provider"),
                "model": self.config.get("model"),
                "working_dir": self.working_dir,
            }})

            # Step 1: Build initial context (task + repo map + file context)
            self._build_initial_context(task, file_context or [])

            # Step 2: ReAct loop
            while self._iteration < self.MAX_ITERATIONS:
                if self._stop_flag.is_set():
                    self._set_status(AgentStatus.IDLE)
                    self._emit_signal(AgentSignalType.ERROR, {"error": "Task cancelled by user"})
                    self._log_event("task_cancelled", {"iterations": self._iteration})
                    return False

                self._iteration += 1
                self._set_status(AgentStatus.THINKING)

                # Send to LLM
                response = self._call_llm()

                # Handle tool calls
                if response.tool_calls:
                    self._set_status(AgentStatus.EXECUTING)
                    for tool_call in response.tool_calls:
                        if self._stop_flag.is_set():
                            break
                        self._execute_tool(tool_call)
                elif self._is_task_complete(response):
                    # TASK_COMPLETE
                    self._set_status(AgentStatus.COMPLETE)
                    self._emit_signal(AgentSignalType.TASK_COMPLETE, {
                        "iterations": self._iteration,
                        "tool_calls": self._total_tool_calls,
                        "tokens": self._accumulated_tokens.__dict__,
                        "duration": (datetime.now() - self._session_start).total_seconds(),
                    })
                    self._log_event("task_complete", {
                        "iterations": self._iteration,
                        "tool_calls": self._total_tool_calls,
                        "tokens_input": self._accumulated_tokens.input_tokens,
                        "tokens_output": self._accumulated_tokens.output_tokens,
                    })
                    return True
                else:
                    # LLM responded with only text, no tool calls and not complete
                    # This means the LLM is asking a question or providing info
                    # Just continue the loop with the response in context
                    pass

            # Max iterations reached
            self._set_status(AgentStatus.ERROR)
            self._emit_signal(AgentSignalType.ERROR, {
                "error": f"Max iterations ({self.MAX_ITERATIONS}) reached without completion",
            })
            return False

        except Exception as exc:
            logger.error(f"Agent loop error: {exc}")
            traceback.print_exc()
            self._set_status(AgentStatus.ERROR)
            self._emit_signal(AgentSignalType.ERROR, {"error": str(exc)})
            self._log_event("task_error", {"error": str(exc), "traceback": traceback.format_exc()})
            return False

    def stop_task(self) -> None:
        """Signal the agent to stop."""
        self._stop_flag.set()
        self._set_status(AgentStatus.IDLE)

    def provide_user_response(self, response: str) -> None:
        """Provide a response to an ask_user question."""
        self._user_response = response
        self._user_response_event.set()

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status."""
        return {
            "status": self.status.value,
            "iteration": self._iteration,
            "tool_calls": self._total_tool_calls,
            "task": self._current_task,
            "tokens": self._accumulated_tokens.__dict__,
            "context": self.context.get_stats(),
        }

    # ========================================================================
    # Internal Methods
    # ========================================================================

    def _reset(self, task: str) -> None:
        """Reset state for a new task."""
        self._stop_flag.clear()
        self._current_task = task
        self._iteration = 0
        self._total_tool_calls = 0
        self._accumulated_tokens = TokenUsage()
        self._user_response = None
        self._user_response_event.clear()
        self.context.clear()
        self._set_status(AgentStatus.IDLE)

    def _set_status(self, status: AgentStatus) -> None:
        self.status = status
        self._emit_signal(AgentSignalType.STATUS_CHANGED, {"status": status.value})

    def _build_initial_context(self, task: str, file_context: List[str]) -> None:
        """Build the initial context for a new task."""
        # Add file context
        for f in file_context:
            self.context.add_file_context(f)

        # Generate repo map and inject (pattern: Aider's repo_map injection)
        try:
            repo_map_result = self.tools.execute("repo_map", {"max_tokens": 1500})
            if repo_map_result.success:
                self.context.repo_map = repo_map_result.output
                self._log_event("repo_map_generated", {
                    "symbols": repo_map_result.metadata.get("symbol_count", 0),
                })
        except Exception as exc:
            logger.warning(f"Repo map generation failed: {exc}")

        # Cross-repo intelligence: enrich context with reference project info
        cross_repo_context = self._build_cross_repo_context(task)
        if cross_repo_context:
            self.context.add_system_message(cross_repo_context)
            self._log_event("cross_repo_context_added", {
                "context_length": len(cross_repo_context),
            })

        # Add the task as the first user message
        task_message = f"## Task\n\n{task}\n\nProceed step by step. Use tools as needed. Signal TASK_COMPLETE when done."
        self.context.add_user_message(task_message)

    def _build_cross_repo_context(self, task: str) -> str:
        """Build cross-repository context from indexed reference projects.

        Searches codebase-memory for patterns related to the current task
        and injects relevant findings as system context.
        """
        parts = []

        # Check if MCP client has codebase-memory connected
        mcp_tools = self.mcp_client.get_all_tools()
        has_codebase_memory = any(
            "search_graph" in t.name or "search_code" in t.name
            for t in mcp_tools
        )

        if has_codebase_memory:
            parts.append(
                "## Cross-Repository Intelligence\n\n"
                "The following reference projects are indexed and available for queries:\n"
                "  • OpenCode — Go-based MCP client, PubSub, permission system\n"
                "  • Jarvis — C++ KDE plasmoid, llama.cpp integration\n"
                "  • Aider — Python AI coding assistant, repo_map pattern\n\n"
                "Use `cross_repo_search` to find patterns across these projects.\n"
                "Use `cross_repo_trace` to trace function calls through a specific project.\n"
            )
        else:
            # Even without MCP, the built-in cross_repo_search tool can search
            # reference project directories via ripgrep fallback
            parts.append(
                "## Cross-Repository Intelligence\n\n"
                "Reference projects are available for code search:\n"
                "  • OpenCode (~/ecosystem/source-codes/opencode-main)\n"
                "  • Jarvis (~/ecosystem/source-codes/jarvis-main)\n\n"
                "Use `cross_repo_search` to find patterns across these projects.\n"
                "Use `cross_repo_trace` to trace function calls (requires codebase-memory CLI).\n"
            )

        return "\n".join(parts)

    def _call_llm(self) -> ProviderResponse:
        """Send context to LLM and stream response to UI."""
        system, messages = self.context.prepare_messages_for_streaming()

        # Merge built-in tools with MCP tools
        builtin_tools = self.tools.get_tool_schemas()
        mcp_tools = self.mcp_client.get_tool_schemas()
        all_tools = builtin_tools + mcp_tools

        self._log_event("llm_call_start", {
            "iteration": self._iteration,
            "message_count": len(messages),
            "tool_count": len(all_tools),
            "builtin_tools": len(builtin_tools),
            "mcp_tools": len(mcp_tools),
        })

        # Collect the full response
        full_content = ""
        tool_calls: List[Dict[str, Any]] = []
        current_tool: Optional[Dict[str, Any]] = None
        current_tool_input: str = ""

        try:
            for event in self.provider.stream_message(messages, all_tools, system_prompt=system):
                if self._stop_flag.is_set():
                    break

                if event.type == EventType.CONTENT_DELTA:
                    full_content += event.content
                    # Stream each token to UI (pattern: end4's streaming pattern)
                    self._emit_signal(AgentSignalType.TOKEN_STREAM, {
                        "content": event.content,
                        "type": "thought",
                    })

                elif event.type == EventType.THINKING_DELTA:
                    full_content += event.thinking
                    self._emit_signal(AgentSignalType.TOKEN_STREAM, {
                        "content": event.thinking,
                        "type": "thinking",
                    })

                elif event.type == EventType.TOOL_USE_START:
                    if event.tool_call:
                        current_tool = event.tool_call
                        current_tool_input = ""
                        self._emit_signal(AgentSignalType.TOOL_CALL_START, {
                            "tool_name": current_tool.get("name", ""),
                            "iteration": self._iteration,
                        })

                elif event.type == EventType.TOOL_USE_DELTA:
                    current_tool_input += event.content

                elif event.type == EventType.TOOL_USE_STOP:
                    if current_tool and event.tool_call:
                        tool_calls.append(event.tool_call)
                        self._emit_signal(AgentSignalType.TOOL_CALL_START, {
                            "tool_name": event.tool_call.get("name", ""),
                            "input": event.tool_call.get("input", {}),
                            "iteration": self._iteration,
                        })
                    current_tool = None
                    current_tool_input = ""

                elif event.type == EventType.CONTENT_STOP:
                    if event.response and event.response.usage:
                        self._accumulated_tokens.input_tokens += event.response.usage.input_tokens
                        self._accumulated_tokens.output_tokens += event.response.usage.output_tokens
                    # Finalize any pending tool calls from streaming
                    if current_tool:
                        if current_tool_input:
                            try:
                                current_tool["input"] = json.loads(current_tool_input)
                            except json.JSONDecodeError:
                                current_tool["input"] = {"raw": current_tool_input}
                        tool_calls.append(current_tool)
                        current_tool = None
                        current_tool_input = ""

                elif event.type == EventType.ERROR:
                    self._emit_signal(AgentSignalType.ERROR, {"error": event.error or "Unknown error"})
                    self._log_event("llm_error", {"error": event.error, "iteration": self._iteration})

        except Exception as exc:
            logger.error(f"LLM streaming error: {exc}")
            self._emit_signal(AgentSignalType.ERROR, {"error": str(exc)})
            self._log_event("llm_stream_error", {"error": str(exc)})

        # Add response to context
        if full_content or tool_calls:
            self.context.add_assistant_message(full_content, tool_calls)

        self._log_event("llm_call_end", {
            "iteration": self._iteration,
            "content_length": len(full_content),
            "tool_calls": len(tool_calls),
            "tokens_input": self._accumulated_tokens.input_tokens,
            "tokens_output": self._accumulated_tokens.output_tokens,
        })

        return ProviderResponse(
            content=full_content,
            tool_calls=tool_calls,
            finish_reason="stop",
            usage=self._accumulated_tokens,
        )

    def _execute_tool(self, tool_call: Dict[str, Any]) -> None:
        """Execute a single tool call and feed result back to context."""
        tool_name = tool_call.get("name", "")
        tool_input = tool_call.get("input", {})
        tool_id = tool_call.get("id", f"tool_{self._total_tool_calls}")

        self._total_tool_calls += 1

        self._emit_signal(AgentSignalType.TOOL_CALL_START, {
            "tool_name": tool_name,
            "input": tool_input,
        })

        self._log_event("tool_call_start", {
            "tool_name": tool_name,
            "input": str(tool_input)[:500],
            "iteration": self._iteration,
            "call_number": self._total_tool_calls,
        })

        start_time = time.time()

        # Route tool execution: ask_user → local, MCP tools → MCP client, rest → ToolRegistry
        if tool_name == "ask_user":
            result = self._handle_ask_user(tool_input)
        elif self._is_mcp_tool(tool_name):
            result = self._execute_mcp_tool(tool_name, tool_input)
        else:
            result = self.tools.execute(tool_name, tool_input)

        duration_ms = (time.time() - start_time) * 1000

        # Format result for context
        if result.success:
            result_text = f"Tool [{tool_name}] succeeded:\n{result.output}"
        else:
            result_text = f"Tool [{tool_name}] FAILED:\n{result.error}"

        # Stream result to UI
        self._emit_signal(AgentSignalType.TOOL_CALL_RESULT, {
            "tool_name": tool_name,
            "success": result.success,
            "output": result.output[:2000],
            "error": result.error,
            "duration_ms": duration_ms,
        })

        # Log to OpenObserve
        self._log_event("tool_call_end", {
            "tool_name": tool_name,
            "success": result.success,
            "output_length": len(result.output),
            "duration_ms": duration_ms,
            "error": result.error if not result.success else None,
        })

        # Append tool result to context (pattern: ZooCode tool result feedback)
        self.context.add_tool_result(tool_id, tool_name, result_text)

    def _handle_ask_user(self, tool_input: Dict[str, Any]) -> ToolResult:
        """Handle ask_user — emit signal to UI and wait for response."""
        question = tool_input.get("question", "Continue?")
        options = tool_input.get("options", [])

        self._set_status(AgentStatus.WAITING_USER)
        self._emit_signal(AgentSignalType.QUESTION_ASKED, {
            "question": question,
            "options": options,
        })

        self._user_response_event.clear()

        # Wait for user response (with timeout)
        timeout = 120  # 2 minute timeout for user response
        if self._user_response_event.wait(timeout=timeout):
            response = self._user_response or "(no response)"
            self._user_response = None
            result = ToolResult(
                tool_name="ask_user",
                success=True,
                output=f"User response: {response}",
                metadata={"question": question, "answer": response},
            )
        else:
            result = ToolResult(
                tool_name="ask_user",
                success=True,
                output="User response: (timed out after 120s)",
                metadata={"question": question, "answer": None, "timed_out": True},
            )

        self._set_status(AgentStatus.THINKING)
        return result

    # ========================================================================
    # MCP Tool Routing
    # ========================================================================

    def _is_mcp_tool(self, tool_name: str) -> bool:
        """Check if a tool is provided by an external MCP server."""
        for tool in self.mcp_client.get_all_tools():
            if tool.name == tool_name:
                return True
        return False

    def _execute_mcp_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> ToolResult:
        """Execute a tool via the MCP client manager.

        Finds the server that provides this tool and routes the call.
        """
        # Find which server provides this tool
        server_name = None
        for tool in self.mcp_client.get_all_tools():
            if tool.name == tool_name:
                server_name = tool.server_name
                break

        if not server_name:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"MCP tool '{tool_name}' not found on any connected server",
            )

        # Execute via MCP client
        mcp_result = self.mcp_client.execute_tool(server_name, tool_name, tool_input)

        # Convert MCP result to ToolResult
        if mcp_result.get("isError"):
            error_text = mcp_result.get("content", [{}])[0].get("text", "Unknown error")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=error_text,
                metadata={"mcp_server": server_name},
            )
        else:
            output_text = mcp_result.get("content", [{}])[0].get("text", "")
            return ToolResult(
                tool_name=tool_name,
                success=True,
                output=output_text,
                metadata={"mcp_server": server_name},
            )

    @staticmethod
    def _is_task_complete(response: ProviderResponse) -> bool:
        """Check if the LLM signaled task completion."""
        content_lower = response.content.lower()
        indicators = [
            "task_complete",
            "task complete",
            "task completed",
            "the task is complete",
            "all tasks complete",
        ]
        return any(indicator in content_lower for indicator in indicators)

    # ========================================================================
    # Signal / Event Helpers
    # ========================================================================

    def _emit_signal(self, signal_type: AgentSignalType, data: Dict[str, Any]) -> None:
        """Emit a UI signal via the configured handler."""
        if self._signal_handler:
            try:
                self._signal_handler(signal_type, data)
            except Exception as exc:
                logger.error(f"Signal handler error: {exc}")

    def _log_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Log a structured event for OpenObserve / audit trail."""
        event = AgentEvent(event_type, data)
        if self._event_handler:
            try:
                self._event_handler(event)
            except Exception as exc:
                logger.error(f"Event handler error: {exc}")


# ============================================================================
# Convenience: Run agent in a background thread
# ============================================================================


class AgentThread(threading.Thread):
    """Run the agent loop in a separate thread for non-blocking D-Bus integration."""

    def __init__(self, agent: AgentLoop, task: str, file_context: Optional[List[str]] = None):
        super().__init__(daemon=True)
        self.agent = agent
        self.task = task
        self.file_context = file_context or []
        self.result: Optional[bool] = None

    def run(self) -> None:
        self.result = self.agent.run_task(self.task, self.file_context)

    def stop(self) -> None:
        self.agent.stop_task()
