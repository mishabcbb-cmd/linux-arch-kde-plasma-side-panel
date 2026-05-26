"""agent/__init__.py — KDE AI Agent package."""

from .agent_loop import AgentLoop, AgentSignalType, AgentStatus
from .context_manager import ContextManager
from .llm_client import (
    AnthropicProvider,
    BaseLLMProvider,
    EventType,
    LlamaCppProvider,
    Message,
    OllamaProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
    ProviderResponse,
    StreamEvent,
    TokenUsage,
    create_provider,
    create_provider_from_config,
)
from .tools import ToolRegistry, ToolResult

__version__ = "0.2.0"
__all__ = [
    "AgentLoop", "AgentSignalType", "AgentStatus",
    "ContextManager",
    "AnthropicProvider", "BaseLLMProvider", "EventType", "Message",
    "LlamaCppProvider", "OllamaProvider", "OpenAICompatibleProvider",
    "OpenRouterProvider", "ProviderResponse", "StreamEvent", "TokenUsage",
    "create_provider", "create_provider_from_config",
    "ToolRegistry", "ToolResult",
]
