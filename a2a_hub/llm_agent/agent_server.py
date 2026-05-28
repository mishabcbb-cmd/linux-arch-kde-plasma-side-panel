#!/usr/bin/env python3
"""A2A LLM Agent Server — оборачивает LLM провайдер в A2A Server.

Каждый агент это:
1. HTTP сервер (A2A Server) — принимает задачи
2. A2A Hub Client — регистрируется в Hub
3. LLM Provider — OpenRouter или llama.cpp

Запуск:
    python agent_server.py --name owl-1 --provider openrouter --model openrouter/owl-alpha --port 8091
    python agent_server.py --name owl-2 --provider openrouter --model openrouter/owl-alpha --port 8092
    python agent_server.py --name qwen --provider llama.cpp --model Qwen3.6-35B --port 8093
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, List, Optional

# Добавить корневую директорию проекта в path
# a2a_hub/llm_agent/agent_server.py -> a2a_hub/ -> project_root
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)
# Добавить директорию agent/ для импорта llm_client
sys.path.insert(0, os.path.join(_project_root, "agent"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("llm-agent")


class LLMProvider:
    """Простой wrapper над llm_client провайдерами."""

    def __init__(self, provider_type: str, model: str, **kwargs):
        self.provider_type = provider_type
        self.model = model
        self.kwargs = kwargs
        self._provider = None

    def _get_provider(self):
        if self._provider is None:
            from llm_client import create_provider_from_config
            config = {
                "provider": self.provider_type,
                "model": self.model,
                "max_tokens": self.kwargs.get("max_tokens", 8192),
                "temperature": self.kwargs.get("temperature", 0.7),
            }
            if self.provider_type == "openrouter":
                api_key = self.kwargs.get("api_key", os.environ.get("OPENROUTER_API_KEY", ""))
                config["api_key"] = api_key
                # OpenRouterProvider читает из переменной окружения
                if api_key:
                    os.environ["OPENROUTER_API_KEY"] = api_key
            elif self.provider_type == "llama.cpp":
                config["llama_host"] = self.kwargs.get("llama_host", "http://localhost:8085")
            self._provider = create_provider_from_config(config)
        return self._provider

    def send_message(self, messages: List[Dict[str, str]], system_prompt: str = "") -> str:
        """Отправить сообщение в LLM и получить ответ."""
        from llm_client import Message

        msgs = [Message(role=m["role"], content=m["content"]) for m in messages]
        provider = self._get_provider()

        response = provider.send_message(
            messages=msgs,
            system_prompt=system_prompt or self._default_system_prompt(),
        )
        return response.content

    def _default_system_prompt(self) -> str:
        return (
            "You are an AI agent in a multi-agent A2A (Agent-to-Agent) network. "
            "You collaborate with other agents through a central Hub. "
            "Be concise, direct, and helpful. "
            "When you complete a task, provide clear structured output."
        )


class AgentHTTPHandler(BaseHTTPRequestHandler):
    """A2A Agent HTTP Server — принимает задачи и возвращает результаты."""

    agent_server: "LLMAgentServer" = None

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {format % args}")

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False, default=str).encode())

    def _read_json(self) -> Optional[Dict]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return None
        return None

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/" or path == "":
            self._send_json({
                "agent": self.agent_server.agent_name,
                "model": self.agent_server.model,
                "provider": self.agent_server.provider_type,
                "status": "running",
                "capabilities": self.agent_server.capabilities,
            })

        elif path == "/.well-known/agent-card.json":
            self._send_json(self.agent_server.get_agent_card())

        elif path == "/health":
            self._send_json({"status": "healthy", "agent": self.agent_server.agent_name})

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = self.path.rstrip("/")
        data = self._read_json()

        if path == "/tasks/execute":
            self._handle_execute(data)
        elif path == "/message":
            self._handle_message(data)
        else:
            self._send_json({"error": "Not found"}, 404)

    def _handle_execute(self, data: Optional[Dict]) -> None:
        """Выполнить задачу — отправить в LLM и вернуть результат."""
        if not data or "text" not in data:
            self._send_json({"error": "Missing 'text' in request"}, 400)
            return

        task_text = data["text"]
        context = data.get("context", {})
        system_prompt = data.get("system_prompt", "")

        logger.info(f"Executing task: {task_text[:100]}...")

        try:
            # Сформировать сообщения
            messages = []
            if context.get("history"):
                messages = context["history"]
            messages.append({"role": "user", "content": task_text})

            # Добавить контекст от других агентов
            if context.get("shared_memory"):
                memory_text = "\n\nShared context from other agents:\n"
                for key, value in context["shared_memory"].items():
                    memory_text += f"- {key}: {value}\n"
                messages.append({"role": "user", "content": memory_text})

            # Отправить в LLM
            response = self.agent_server.llm.send_message(
                messages=messages,
                system_prompt=system_prompt,
            )

            result = {
                "status": "completed",
                "agent": self.agent_server.agent_name,
                "model": self.agent_server.model,
                "response": response,
            }

            # Сохранить полный лог переписки в Hub context
            if self.agent_server.hub_client:
                task_id = self.agent_server.current_task_id or str(hash(task_text) % 10000)
                # Записать входящее сообщение пользователя
                self.agent_server.hub_client._post_conversation_message(
                    task_id=task_id, role="user", content=task_text[:500], agent="user"
                )
                # Записать ответ агента
                self.agent_server.hub_client._post_conversation_message(
                    task_id=task_id, role="assistant", content=response[:2000],
                    agent=self.agent_server.agent_name,
                    metadata={"model": self.agent_server.model}
                )

            self._send_json(result)
            logger.info(f"Task completed by {self.agent_server.agent_name}")

        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self._send_json({
                "status": "error",
                "error": str(e),
                "agent": self.agent_server.agent_name,
            }, 500)

    def _handle_message(self, data: Optional[Dict]) -> None:
        """Простой chat — отправить сообщение в LLM."""
        if not data or "message" not in data:
            self._send_json({"error": "Missing 'message' in request"}, 400)
            return

        try:
            messages = [{"role": "user", "content": data["message"]}]
            response = self.agent_server.llm.send_message(
                messages=messages,
                system_prompt=data.get("system_prompt", ""),
            )
            self._send_json({
                "response": response,
                "agent": self.agent_server.agent_name,
                "model": self.agent_server.model,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


class LLMAgentServer:
    """A2A LLM Agent Server — оборачивает LLM провайдер."""

    def __init__(
        self,
        name: str,
        provider_type: str,
        model: str,
        port: int,
        hub_url: str = "http://127.0.0.1:9000",
        capabilities: Optional[List[str]] = None,
        **provider_kwargs,
    ):
        self.agent_name = name
        self.provider_type = provider_type
        self.model = model
        self.port = port
        self.hub_url = hub_url
        self.capabilities = capabilities or ["chat", "code_analysis", "reasoning"]
        self.llm = LLMProvider(provider_type, model, **provider_kwargs)
        self.hub_client = None
        self._server: Optional[HTTPServer] = None
        self.current_task_id: Optional[str] = None

    def get_agent_card(self) -> Dict:
        """A2A Agent Card — описание агента."""
        return {
            "name": self.agent_name,
            "description": f"LLM Agent: {self.model} via {self.provider_type}",
            "url": f"http://127.0.0.1:{self.port}",
            "version": "1.0.0",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
            },
            "skills": [
                {
                    "id": cap,
                    "name": cap.replace("_", " ").title(),
                    "description": f"Can perform {cap.replace('_', ' ')}",
                }
                for cap in self.capabilities
            ],
            "defaultInputModes": ["text"],
            "defaultOutputModes": ["text"],
        }

    def register_with_hub(self) -> bool:
        """Зарегистрировать агента в A2A Hub."""
        try:
            from a2a_hub.client.hub_client import A2AHubClient
            self.hub_client = A2AHubClient(
                hub_url=self.hub_url,
                agent_name=self.agent_name,
                agent_description=f"LLM Agent: {self.model}",
                agent_endpoint=f"http://127.0.0.1:{self.port}",
                capabilities=self.capabilities,
            )
            result = self.hub_client.register()
            if result:
                self.hub_client.start_heartbeat()
                logger.info(f"Registered with A2A Hub: {self.agent_name}")
            return result
        except Exception as e:
            logger.warning(f"Could not register with Hub: {e}")
            return False

    def start(self) -> None:
        """Запустить A2A Agent Server."""
        AgentHTTPHandler.agent_server = self
        self._server = HTTPServer(("127.0.0.1", self.port), AgentHTTPHandler)

        # Зарегистрировать в Hub
        self.register_with_hub()

        logger.info(f"╔══════════════════════════════════════════╗")
        logger.info(f"║  A2A LLM Agent: {self.agent_name:<22} ║")
        logger.info(f"║  Model: {self.model:<30} ║")
        logger.info(f"║  Port: {self.port:<31} ║")
        logger.info(f"║  Hub: {self.hub_url:<31} ║")
        logger.info(f"╚══════════════════════════════════════════╝")

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info(f"Shutting down {self.agent_name}...")
        finally:
            self.stop()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
        if self.hub_client:
            self.hub_client.stop_heartbeat()
            self.hub_client.unregister()
        logger.info(f"Agent {self.agent_name} stopped.")


def main():
    parser = argparse.ArgumentParser(description="A2A LLM Agent Server")
    parser.add_argument("--name", required=True, help="Agent name")
    parser.add_argument("--provider", required=True, choices=["openrouter", "llama.cpp", "ollama", "anthropic"])
    parser.add_argument("--model", required=True, help="Model name")
    parser.add_argument("--port", type=int, required=True, help="HTTP port")
    parser.add_argument("--hub-url", default="http://127.0.0.1:9000", help="A2A Hub URL")
    parser.add_argument("--capabilities", nargs="+", default=["chat", "code_analysis", "reasoning"])
    parser.add_argument("--llama-host", default="http://localhost:8085", help="llama.cpp host")
    parser.add_argument("--api-key", default="", help="API key")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    kwargs = {
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
    }
    if args.provider == "openrouter":
        kwargs["api_key"] = args.api_key
    elif args.provider == "llama.cpp":
        kwargs["llama_host"] = args.llama_host

    agent = LLMAgentServer(
        name=args.name,
        provider_type=args.provider,
        model=args.model,
        port=args.port,
        hub_url=args.hub_url,
        capabilities=args.capabilities,
        **kwargs,
    )
    agent.start()


if __name__ == "__main__":
    main()
