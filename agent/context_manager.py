"""
agent/context_manager.py — Token-budgeted conversation context management.

Maintains conversation history with:
  • Token budget enforcement (configurable limit)
  • repo_map() injection at session start
  • Automatic summarization and compression when approaching token limit
  • Message history pruning (keep system + recent N exchanges)

Patterns from: Aider (ChatSummary, token counting), OpenCode (message history)
"""

import json
import logging
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from .llm_client import Message, TokenUsage

logger = logging.getLogger(__name__)


# ============================================================================
# Context Manager
# ============================================================================


class ContextManager:
    """Manages conversation context with token budget enforcement.

    Responsibilities:
      1. Store message history
      2. Enforce token budget by summarizing/truncating old context
      3. Inject repo map at session start
      4. Prepare messages for each LLM call
    """

    # Default system prompt
    DEFAULT_SYSTEM_PROMPT = (
        "You are an AI coding agent embedded in a KDE Plasma 6 desktop panel. "
        "You have access to tools for reading/writing files, running shell commands, "
        "searching code, and executing tests. Your responses update the QML chat view in real time.\n\n"
        "## Instructions\n"
        "- Be concise and direct — every token counts\n"
        "- When asked to make code changes, first read the file, then write it\n"
        "- Use bash_exec for all terminal operations\n"
        "- Use search_codebase to find patterns before making changes\n"
        "- When you complete a task, explicitly state 'TASK_COMPLETE'\n"
        "- Use git commit after file modifications to track changes\n"
        "- Never ask for confirmation — just do it\n"
    )

    def __init__(
        self,
        max_input_tokens: int = 100_000,
        max_output_tokens: int = 8_192,
        summary_threshold: float = 0.75,
    ):
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.summary_threshold = summary_threshold

        self._messages: Deque[Message] = deque()
        self._system_prompt: str = self.DEFAULT_SYSTEM_PROMPT
        self._repo_map: str = ""
        self._file_context: List[str] = []
        self._summaries: List[str] = []
        self._total_tokens_used: int = 0
        self._message_count: int = 0

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def messages(self) -> List[Message]:
        return list(self._messages)

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value

    @property
    def repo_map(self) -> str:
        return self._repo_map

    @repo_map.setter
    def repo_map(self, value: str) -> None:
        self._repo_map = value

    @property
    def file_context(self) -> List[str]:
        return list(self._file_context)

    def add_file_context(self, file_path: str) -> None:
        """Add a file to the context set."""
        if file_path not in self._file_context:
            self._file_context.append(file_path)

    def remove_file_context(self, file_path: str) -> None:
        """Remove a file from the context set."""
        if file_path in self._file_context:
            self._file_context.remove(file_path)

    def clear_file_context(self) -> None:
        self._file_context.clear()

    # ========================================================================
    # Message Management
    # ========================================================================

    def add_message(self, message: Message) -> None:
        """Add a message to the history."""
        self._messages.append(message)
        self._message_count += 1
        self._total_tokens_used += self._estimate_tokens(message.content)

        # Check if we need to summarize
        if self._total_tokens_used > int(self.max_input_tokens * self.summary_threshold):
            self._compress()

    def add_user_message(self, content: str) -> None:
        self.add_message(Message(role="user", content=content))

    def add_assistant_message(self, content: str, tool_calls: Optional[List[Dict]] = None) -> None:
        self.add_message(Message(role="assistant", content=content, tool_calls=tool_calls))

    def add_tool_result(self, tool_call_id: str, tool_name: str, content: str) -> None:
        self.add_message(Message(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=tool_name,
        ))

    def add_system_message(self, content: str) -> None:
        """Add an additional system-level instruction."""
        self.add_message(Message(role="system", content=content))

    # ========================================================================
    # Context Preparation
    # ========================================================================

    def prepare_messages(self) -> List[Message]:
        """Prepare messages for an LLM call.

        Returns the full message list with:
          1. System prompt as first message
          2. Repo map injected (if available)
          3. File context for currently selected files
          4. Conversation history
        """
        prepared: List[Message] = []

        # Build augmented system prompt
        system_content = self._system_prompt

        if self._repo_map:
            system_content += f"\n\n## Repository Structure\n\n{self._repo_map}"

        if self._file_context:
            files_str = "\n".join(f"  - {f}" for f in self._file_context)
            system_content += f"\n\n## Active Context Files\n\nThe user has selected these files for context:\n{files_str}"

        if self._summaries:
            summaries_str = "\n".join(f"  - {s}" for s in self._summaries)
            system_content += f"\n\n## Conversation Summaries\n{summaries_str}"

        prepared.append(Message(role="system", content=system_content))

        # Add conversation history
        prepared.extend(self._messages)

        return prepared

    def prepare_messages_for_streaming(self) -> Tuple[str, List[Message]]:
        """Returns (system_prompt, messages) tuple for streaming API calls."""
        messages = self.prepare_messages()
        system = ""
        non_system = []

        for msg in messages:
            if msg.role == "system":
                system = msg.content
            else:
                non_system.append(msg)

        return system, non_system

    def get_token_estimate(self) -> int:
        """Get the current token usage estimate."""
        return self._total_tokens_used

    def get_remaining_budget(self) -> int:
        """Get remaining tokens before hitting the budget."""
        return max(0, self.max_input_tokens - self._total_tokens_used)

    # ========================================================================
    # Compression & Summarization
    # ========================================================================

    def _compress(self) -> None:
        """Compress old messages to stay within token budget.

        Strategy: Keep the first 2 exchanges (setup) and last 10 exchanges (recent),
        summarize everything in between.
        """
        if len(self._messages) < 20:
            return

        keep_recent = 20  # Keep last 10 exchanges (user+assistant pairs)
        to_summarize = list(self._messages)[2:-keep_recent]

        if not to_summarize:
            return

        # Create a summary
        summary = self._build_summary(to_summarize)
        self._summaries.append(summary)

        # Keep only recent messages
        recent = list(self._messages)[-keep_recent:]
        self._messages.clear()
        self._messages.extend(recent)

        # Recalculate token usage
        self._total_tokens_used = sum(self._estimate_tokens(m.content) for m in self._messages)

        logger.info(
            f"Context compressed: summarized {len(to_summarize)} messages, "
            f"keeping {len(recent)} recent. Tokens: ~{self._total_tokens_used}"
        )

    def _build_summary(self, messages: List[Message]) -> str:
        """Build a concise summary of a message range."""
        actions: List[str] = []
        for msg in messages:
            if msg.role == "tool":
                prefix = msg.content[:80].replace("\n", " ")
                actions.append(f"  - Tool [{msg.name}]: {prefix}...")
            elif msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    actions.append(f"  - Called: {tc.get('name', 'unknown')}")
            elif msg.role == "user":
                actions.append(f"  - User: {msg.content[:100]}")

        summary = f"Earlier in the conversation ({len(messages)} messages):\n"
        summary += "\n".join(actions[:20])  # Max 20 summarized actions
        return summary

    # ========================================================================
    # Helpers
    # ========================================================================

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimation: ~4 characters per token."""
        return max(1, len(text) // 4)

    def clear(self) -> None:
        """Reset all context."""
        self._messages.clear()
        self._summaries.clear()
        self._file_context.clear()
        self._total_tokens_used = 0
        self._message_count = 0
        self._repo_map = ""

    def get_stats(self) -> Dict[str, Any]:
        """Return context statistics."""
        return {
            "message_count": self._message_count,
            "current_messages": len(self._messages),
            "summaries": len(self._summaries),
            "file_context": len(self._file_context),
            "estimated_tokens": self._total_tokens_used,
            "token_budget": self.max_input_tokens,
            "remaining": self.get_remaining_budget(),
            "has_repo_map": bool(self._repo_map),
        }
