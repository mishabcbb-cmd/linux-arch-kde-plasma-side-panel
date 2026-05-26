"""
agent/llm_client.py — Model-agnostic LLM provider abstraction.

Provides:
  • BaseLLMProvider              — Abstract interface (pattern: OpenCode provider.go)
  • AnthropicProvider            — Claude API with streaming + native tool use
  • OllamaProvider               — Local Ollama, same interface
  • OpenAICompatibleProvider     — Base for any /v1/chat/completions endpoint
  • LlamaCppProvider             — llama.cpp server (OpenAI-compatible)
  • OpenRouterProvider           — OpenRouter multi-model gateway
  • create_provider()            — Factory, switchable via config with no rewiring

Patterns extracted from:
  - OpenCode (provider.Provider interface: SendMessages + StreamResponse)
  - end4 (ApiStrategy.qml: buildEndpoint, buildRequestData, parseResponseLine)
  - Aider (litellm integration for model dispatch)
"""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional, Union

logger = logging.getLogger(__name__)


# ============================================================================
# Data Types (pattern: OpenCode message.Message, provider.ProviderEvent)
# ============================================================================


class EventType(str, Enum):
    """Stream event types matching OpenCode's provider.EventType."""
    CONTENT_START = "content_start"
    CONTENT_DELTA = "content_delta"
    THINKING_DELTA = "thinking_delta"
    TOOL_USE_START = "tool_use_start"
    TOOL_USE_DELTA = "tool_use_delta"
    TOOL_USE_STOP = "tool_use_stop"
    CONTENT_STOP = "content_stop"
    COMPLETE = "complete"
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Message:
    """Chat message following OpenAI/Anthropic format."""
    role: str
    content: str
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ProviderResponse:
    content: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""


@dataclass
class StreamEvent:
    type: EventType
    content: str = ""
    thinking: str = ""
    tool_call: Optional[Dict[str, Any]] = None
    response: Optional[ProviderResponse] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"type": self.type.value, "content": self.content}
        if self.thinking:
            d["thinking"] = self.thinking
        if self.tool_call:
            d["tool_call"] = self.tool_call
        if self.error:
            d["error"] = self.error
        return d


# ============================================================================
# Provider Interface
# ============================================================================


class BaseLLMProvider(ABC):
    """Abstract provider interface — all LLM backends implement this."""

    def __init__(self, model: str, config: Optional[Dict[str, Any]] = None):
        self.model = model
        self.config = config or {}
        self._system_prompt: str = ""

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str) -> None:
        self._system_prompt = value

    @abstractmethod
    def send_message(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    def stream_message(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> Generator[StreamEvent, None, None]:
        ...

    def estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)


# ============================================================================
# Anthropic Provider
# ============================================================================


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API with native streaming and tool use."""

    API_VERSION = "2023-06-01"
    DEFAULT_MAX_TOKENS = 8192

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model, config)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = self.config.get("max_tokens", self.DEFAULT_MAX_TOKENS)

    def _get_client(self):
        try:
            import anthropic
            return anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    def _build_system(self, system_prompt: Optional[str] = None) -> str:
        sp = system_prompt or self._system_prompt
        if not sp:
            sp = (
                "You are an AI coding assistant integrated into KDE Plasma. "
                "You have access to tools for reading/writing files, running shell "
                "commands, searching code, and executing tests. Be concise and direct."
            )
        return sp

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        converted = []
        for msg in messages:
            if msg.role == "system":
                continue
            entry: Dict[str, Any] = {"role": msg.role}
            if msg.role == "tool":
                entry["content"] = [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id or "",
                    "content": msg.content,
                }]
            else:
                content_blocks: List[Dict[str, Any]] = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.get("id", f"toolu_{hash(str(tc)):x}"[:16]),
                            "name": tc["name"],
                            "input": tc.get("input", {}),
                        })
                entry["content"] = content_blocks if content_blocks else [{"type": "text", "text": ""}]
            converted.append(entry)
        return converted

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anthropic_tools = []
        for tool in tools:
            func = tool.get("function", tool)
            anthropic_tools.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get("parameters", func.get("input_schema", {
                    "type": "object", "properties": {},
                })),
            })
        return anthropic_tools

    def send_message(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> ProviderResponse:
        client = self._get_client()
        system = self._build_system(system_prompt)
        converted_msgs = self._convert_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted_msgs,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            resp = client.messages.create(**kwargs)
            return self._parse_response(resp)
        except Exception as exc:
            logger.error(f"Anthropic API error: {exc}")
            return ProviderResponse(content=f"API Error: {exc}", finish_reason="error")

    def stream_message(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
    ) -> Generator[StreamEvent, None, None]:
        client = self._get_client()
        system = self._build_system(system_prompt)
        converted_msgs = self._convert_messages(messages)

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": converted_msgs,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._convert_tools(tools)

        try:
            with client.messages.stream(**kwargs) as stream:
                current_tool_id: Optional[str] = None
                current_tool_name: Optional[str] = None
                current_tool_input: str = ""

                for event in stream:
                    if event.type == "content_block_delta":
                        delta = event.delta
                        if delta.type == "text_delta":
                            yield StreamEvent(type=EventType.CONTENT_DELTA, content=delta.text)
                        elif delta.type == "input_json_delta":
                            current_tool_input += delta.partial_json
                            yield StreamEvent(type=EventType.TOOL_USE_DELTA, content=delta.partial_json)

                    elif event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            current_tool_id = block.id
                            current_tool_name = block.name
                            current_tool_input = ""
                            yield StreamEvent(
                                type=EventType.TOOL_USE_START,
                                tool_call={"id": block.id, "name": block.name},
                            )

                    elif event.type == "content_block_stop":
                        if current_tool_id and current_tool_name:
                            try:
                                tool_input = json.loads(current_tool_input) if current_tool_input else {}
                            except json.JSONDecodeError:
                                tool_input = {"raw": current_tool_input}
                            yield StreamEvent(
                                type=EventType.TOOL_USE_STOP,
                                tool_call={"id": current_tool_id, "name": current_tool_name, "input": tool_input},
                            )
                            current_tool_id = current_tool_name = None
                            current_tool_input = ""

                    elif event.type == "message_stop":
                        final_snapshot = stream.current_message_snapshot
                        usage = TokenUsage(
                            input_tokens=getattr(getattr(final_snapshot, "usage", None), "input_tokens", 0),
                            output_tokens=getattr(getattr(final_snapshot, "usage", None), "output_tokens", 0),
                        )
                        yield StreamEvent(
                            type=EventType.CONTENT_STOP,
                            response=ProviderResponse(usage=usage, model=getattr(final_snapshot, "model", "")),
                        )

                    elif event.type == "error":
                        err = getattr(event, "error", None)
                        yield StreamEvent(type=EventType.ERROR, error=str(err) if err else "Unknown error")

        except Exception as exc:
            logger.error(f"Anthropic streaming error: {exc}")
            yield StreamEvent(type=EventType.ERROR, error=str(exc))

    def _parse_response(self, resp: Any) -> ProviderResponse:
        content_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for block in resp.content:
            if block.type == "text":
                content_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append({"id": block.id, "name": block.name, "input": block.input})
        usage = resp.usage
        return ProviderResponse(
            content="\n".join(content_parts),
            tool_calls=tool_calls,
            finish_reason=resp.stop_reason or "stop",
            usage=TokenUsage(
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
            ),
            model=resp.model,
        )


# ============================================================================
# Ollama Provider
# ============================================================================


class OllamaProvider(BaseLLMProvider):
    """Local Ollama provider using /api/chat endpoint."""

    DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        model: str = "llama3.2",
        host: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model, config)
        self.host = host or self.DEFAULT_HOST
        self.api_url = f"{self.host}/api/chat"
        self.temperature = self.config.get("temperature", 0.7)

    def _build_body(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        stream: bool = True,
    ) -> Dict[str, Any]:
        sp = system_prompt or self._system_prompt
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "options": {"temperature": self.temperature},
        }
        if sp:
            body["messages"].insert(0, {"role": "system", "content": sp})
        if tools:
            body["tools"] = tools
        return body

    def send_message(self, messages, tools=None, system_prompt=None) -> ProviderResponse:
        import urllib.request, urllib.error
        body = self._build_body(messages, tools, system_prompt, stream=False)
        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg_data = data.get("message", {})
                response_content = msg_data.get("content", "")
                # Fallback to reasoning_content for models using thinking mode (e.g., Qwen)
                if not response_content and msg_data.get("reasoning_content"):
                    response_content = msg_data["reasoning_content"]
                return ProviderResponse(
                    content=response_content,
                    tool_calls=msg_data.get("tool_calls", []),
                    finish_reason="stop",
                    model=self.model,
                    usage=TokenUsage(
                        input_tokens=data.get("prompt_eval_count", 0),
                        output_tokens=data.get("eval_count", 0),
                    ),
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else str(exc)
            return ProviderResponse(content=f"Ollama Error: {error_body}", finish_reason="error")
        except Exception as exc:
            return ProviderResponse(content=f"Connection error: {exc}. Is Ollama running?", finish_reason="error")

    def stream_message(self, messages, tools=None, system_prompt=None) -> Generator[StreamEvent, None, None]:
        import urllib.request, urllib.error
        body = self._build_body(messages, tools, system_prompt, stream=True)
        req = urllib.request.Request(
            self.api_url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                buffer = b""
                while True:
                    chunk = resp.read(4096)
                    if not chunk:
                        break
                    buffer += chunk
                    while b"\n" in buffer:
                        line_bytes, buffer = buffer.split(b"\n", 1)
                        line = line_bytes.decode("utf-8").strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            msg_data = data.get("message", {})
                            content = msg_data.get("content", "")
                            if content:
                                yield StreamEvent(type=EventType.CONTENT_DELTA, content=content)
                            if data.get("done", False):
                                yield StreamEvent(
                                    type=EventType.CONTENT_STOP,
                                    response=ProviderResponse(
                                        model=self.model,
                                        usage=TokenUsage(
                                            input_tokens=data.get("prompt_eval_count", 0),
                                            output_tokens=data.get("eval_count", 0),
                                        ),
                                    ),
                                )
                        except json.JSONDecodeError:
                            pass
        except urllib.error.HTTPError as exc:
            yield StreamEvent(type=EventType.ERROR, error=f"Ollama HTTP {exc.code}")
        except Exception as exc:
            logger.error(f"Ollama streaming error: {exc}")
            yield StreamEvent(type=EventType.ERROR, error=str(exc))


# ============================================================================
# OpenAI-Compatible Base Provider (llama.cpp, OpenRouter, any /v1/chat/completions)
# ============================================================================


class OpenAICompatibleProvider(BaseLLMProvider):
    """Base for any OpenAI-compatible /v1/chat/completions API with SSE streaming.

    Streaming format: SSE — ``data: {json}\\n\\n``, terminated by ``data: [DONE]``.
    Used by: LlamaCppProvider, OpenRouterProvider, and any custom endpoint.
    """

    def __init__(
        self,
        model: str,
        endpoint: str,
        api_key: str = "",
        extra_headers: Optional[Dict[str, str]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(model, config)
        self.endpoint = endpoint
        self.api_key = api_key
        self.extra_headers = extra_headers or {}
        self.temperature = self.config.get("temperature", 0.7)

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(self.extra_headers)
        return headers

    def _build_body(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_prompt: Optional[str] = None,
        stream: bool = True,
    ) -> Dict[str, Any]:
        sp = system_prompt or self._system_prompt
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
            "temperature": self.temperature,
            "max_tokens": self.config.get("max_tokens", 8192),
        }
        if sp:
            body["messages"].insert(0, {"role": "system", "content": sp})
        if tools:
            body["tools"] = tools
        return body

    def send_message(self, messages, tools=None, system_prompt=None) -> ProviderResponse:
        import urllib.request, urllib.error
        body = self._build_body(messages, tools, system_prompt, stream=False)
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=self._build_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = (data.get("choices") or [{}])[0]
                msg = choice.get("message", {})
                usage_data = data.get("usage", {})
                # Fallback to reasoning_content for models using thinking mode (e.g., Qwen)
                response_content = msg.get("content", "") or ""
                if not response_content and msg.get("reasoning_content"):
                    response_content = msg["reasoning_content"]
                return ProviderResponse(
                    content=response_content,
                    tool_calls=msg.get("tool_calls", []),
                    finish_reason=choice.get("finish_reason", "stop"),
                    model=data.get("model", self.model),
                    usage=TokenUsage(
                        input_tokens=usage_data.get("prompt_tokens", 0),
                        output_tokens=usage_data.get("completion_tokens", 0),
                    ),
                )
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else str(exc)
            return ProviderResponse(content=f"API Error ({exc.code}): {error_body}", finish_reason="error")
        except Exception as exc:
            return ProviderResponse(content=f"Error: {exc}", finish_reason="error")

    def stream_message(self, messages, tools=None, system_prompt=None) -> Generator[StreamEvent, None, None]:
        import urllib.request, urllib.error
        body = self._build_body(messages, tools, system_prompt, stream=True)
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=self._build_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                buffer = b""
                for chunk in iter(lambda: resp.read(1), b""):
                    buffer += chunk
                    while b"\n\n" in buffer:
                        raw, buffer = buffer.split(b"\n\n", 1)
                        line = raw.decode("utf-8").strip()
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            yield StreamEvent(type=EventType.CONTENT_STOP)
                            continue
                        try:
                            for event in self._parse_sse_event(json.loads(data_str)):
                                yield event
                        except json.JSONDecodeError:
                            pass
                if buffer.strip():
                    line = buffer.decode("utf-8").strip()
                    if line.startswith("data: ") and line[6:] != "[DONE]":
                        try:
                            for event in self._parse_sse_event(json.loads(line[6:])):
                                yield event
                        except json.JSONDecodeError:
                            pass
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8") if exc.fp else str(exc)
            yield StreamEvent(type=EventType.ERROR, error=f"API Error ({exc.code}): {error_body}")
        except Exception as exc:
            logger.error(f"OpenAI-compatible streaming error: {exc}")
            yield StreamEvent(type=EventType.ERROR, error=str(exc))

    def _parse_sse_event(self, data: Dict[str, Any]) -> Generator[StreamEvent, None, None]:
        choices = data.get("choices", [])
        if not choices:
            return
        choice = choices[0]
        delta = choice.get("delta", {})
        finish_reason = choice.get("finish_reason")

        if "content" in delta and delta["content"]:
            yield StreamEvent(type=EventType.CONTENT_DELTA, content=delta["content"])

        if "tool_calls" in delta:
            for tc in delta["tool_calls"]:
                tc_id = tc.get("id")
                tc_fn = tc.get("function", {})
                if tc_id and tc_fn.get("name"):
                    yield StreamEvent(
                        type=EventType.TOOL_USE_START,
                        tool_call={"id": tc_id, "name": tc_fn["name"]},
                    )
                if tc_fn.get("arguments"):
                    yield StreamEvent(type=EventType.TOOL_USE_DELTA, content=tc_fn["arguments"])

        if finish_reason:
            usage_data = data.get("usage", {})
            yield StreamEvent(
                type=EventType.CONTENT_STOP,
                response=ProviderResponse(
                    model=data.get("model", self.model),
                    usage=TokenUsage(
                        input_tokens=usage_data.get("prompt_tokens", 0),
                        output_tokens=usage_data.get("completion_tokens", 0),
                    ),
                ),
            )


# ============================================================================
# llama.cpp Provider
# ============================================================================


class LlamaCppProvider(OpenAICompatibleProvider):
    """llama.cpp server — OpenAI-compatible /v1/chat/completions endpoint.

    Start server:  llama-server -m model.gguf --port 8080
    Default host:  http://localhost:8080
    """

    DEFAULT_HOST = "http://localhost:8080"

    def __init__(
        self,
        model: str = "local-model",
        host: str = "",
        api_key: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        host_url = host or self.DEFAULT_HOST
        endpoint = f"{host_url.rstrip('/')}/v1/chat/completions"
        super().__init__(model=model, endpoint=endpoint, api_key=api_key or "no-key", config=config)


# ============================================================================
# OpenRouter Provider
# ============================================================================


class OpenRouterProvider(OpenAICompatibleProvider):
    """OpenRouter — multi-model gateway via OpenAI-compatible API.

    Requires API key from https://openrouter.ai/keys.
    Available models: openai/gpt-4o, anthropic/claude-sonnet-4-20250514,
    google/gemini-2.5-flash, meta-llama/llama-4-maverick, etc.
    """

    ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(
        self,
        model: str = "anthropic/claude-sonnet-4-20250514",
        api_key: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            model=model,
            endpoint=self.ENDPOINT,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            extra_headers={
                "HTTP-Referer": "https://github.com/kde-ai-agent/kde-ai-agent",
                "X-Title": "KDE AI Agent Panel",
            },
            config=config,
        )


# ============================================================================
# Provider Factory
# ============================================================================

PROVIDER_REGISTRY: Dict[str, type] = {
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "llama.cpp": LlamaCppProvider,
    "openrouter": OpenRouterProvider,
}


def register_provider(name: str, provider_cls: type) -> None:
    """Register a new provider type at runtime."""
    PROVIDER_REGISTRY[name] = provider_cls


def create_provider(provider_type: str, model: str, **kwargs: Any) -> BaseLLMProvider:
    """Factory: create provider by type name.

    Usage:
        create_provider("anthropic", "claude-sonnet-4-20250514", api_key="...")
        create_provider("llama.cpp", "local-model", host="http://localhost:8080")
        create_provider("openrouter", "openai/gpt-4o", api_key="...")
    """
    if provider_type not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider: {provider_type}. Available: {list(PROVIDER_REGISTRY.keys())}"
        )
    return PROVIDER_REGISTRY[provider_type](model=model, **kwargs)


def create_provider_from_config(config: Dict[str, Any]) -> BaseLLMProvider:
    """Create a provider from a config dictionary.

    Config keys by provider:
      anthropic:  provider, model, api_key
      ollama:     provider, model, ollama_host
      llama.cpp:  provider, model (optional), llama_host
      openrouter: provider, model, api_key

    Common: max_tokens, temperature
    """
    provider_type = config.get("provider", "anthropic")
    model = config.get("model", "claude-sonnet-4-20250514")
    pc = {"max_tokens": config.get("max_tokens", 8192), "temperature": config.get("temperature", 0.7)}

    if provider_type == "anthropic":
        return AnthropicProvider(model=model, api_key=config.get("api_key", ""), config=pc)

    elif provider_type == "ollama":
        return OllamaProvider(
            model=config.get("ollama_model", model),
            host=config.get("ollama_host", OllamaProvider.DEFAULT_HOST),
            config=pc,
        )

    elif provider_type == "llama.cpp":
        return LlamaCppProvider(
            model=config.get("llama_model", model),
            host=config.get("llama_host", LlamaCppProvider.DEFAULT_HOST),
            api_key=config.get("llama_api_key", ""),
            config=pc,
        )

    elif provider_type == "openrouter":
        return OpenRouterProvider(model=model, api_key=config.get("api_key", ""), config=pc)

    else:
        raise ValueError(f"Unknown provider: {provider_type}. Available: {list(PROVIDER_REGISTRY.keys())}")
