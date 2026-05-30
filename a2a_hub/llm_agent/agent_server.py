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

    def send_message(self, messages: List[Dict[str, str]], system_prompt: str = "", tools: Optional[List[Dict]] = None) -> Any:
        """Отправить сообщение в LLM и получить ответ. Возвращает ProviderResponse."""
        from llm_client import Message

        # Конвертируем сообщения сохраняя tool_calls и tool_call_id
        msgs = []
        for m in messages:
            msg = Message(role=m["role"], content=m.get("content", ""))
            if m.get("tool_calls"):
                msg.tool_calls = m["tool_calls"]
            if m.get("tool_call_id"):
                msg.tool_call_id = m["tool_call_id"]
            if m.get("name"):
                msg.name = m["name"]
            msgs.append(msg)

        provider = self._get_provider()

        response = provider.send_message(
            messages=msgs,
            tools=tools,
            system_prompt=system_prompt or self._default_system_prompt(),
        )
        # send_message uses stream=True by default, but we need non-streaming for tool calling
        # Re-send with stream=False if we got an error
        if response.finish_reason == "error" and "401" in (response.content or ""):
            response = provider.send_message(
                messages=msgs,
                tools=tools,
                system_prompt=system_prompt or self._default_system_prompt(),
            )
        return response

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
        elif path == "/tools/web_search":
            self._handle_tool_web_search(data)
        elif path == "/tools/web_fetch":
            self._handle_tool_web_fetch(data)
        elif path == "/tools/memory_search":
            self._handle_tool_memory_search(data)
        elif path == "/tools/memory_save":
            self._handle_tool_memory_save(data)
        elif path == "/tools/codebase_search":
            self._handle_tool_codebase_search(data)
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

    def _a2a_system_prompt(self) -> str:
        """Краткий system prompt для A2A делегирования."""
        return (
            f"You are '{self.agent_server.agent_name}'. "
            f"Capabilities: {', '.join(self.agent_server.capabilities)}. "
            "If task is outside your capabilities, use delegate_task tool. "
            "Available agents: owl-coder (code), owl-researcher (search), "
            "owl-commander (orchestration), qwen-reviewer (quick review)."
        )

    def _a2a_tools(self) -> List[Dict[str, Any]]:
        """A2A tool definitions для LLM. Только delegate_task — остальные инструменты через HTTP endpoints."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "delegate_task",
                    "description": "Delegate a task to another agent via the A2A Hub. Use when the task is outside your capabilities or requires specialization. You can also use this to chain: delegate to B, then B delegates to C.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "The task description for the target agent. Be specific about what you need."
                            },
                            "target_agent": {
                                "type": "string",
                                "description": "Name of the target agent: owl-coder (code), owl-researcher (search), owl-commander (orchestration), qwen-reviewer (quick review)"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context, background info, or constraints for the target agent"
                            }
                        },
                        "required": ["task", "target_agent"]
                    }
                }
            }
        ]

    def _handle_message(self, data: Optional[Dict]) -> None:
        """Chat с A2A tool calling — агент может делегировать задачи другим агентам."""
        if not data or "message" not in data:
            self._send_json({"error": "Missing 'message' in request"}, 400)
            return

        try:
            user_message = data["message"]
            system_prompt = data.get("system_prompt", "") or self._a2a_system_prompt()
            # Убираем tools для уменьшения размера промпта (экономия токенов)
            # Tools доступны через HTTP endpoints агента
            tools = None
            task_id = data.get("task_id", "")

            # Цикл tool calling (макс 5 итераций чтобы избежать бесконечного цикла)
            messages = [{"role": "user", "content": user_message}]
            final_response = ""
            delegation_chain = []

            for iteration in range(5):
                # Отправить в LLM с tools
                from llm_client import Message
                msgs = [Message(role=m["role"], content=m["content"]) for m in messages]
                provider = self.agent_server.llm._get_provider()
                response = provider.send_message(
                    messages=msgs,
                    tools=tools,
                    system_prompt=system_prompt,
                )

                # Проверить есть ли tool_calls
                if not response.tool_calls:
                    # Финальный ответ — нет tool calls
                    final_response = response.content
                    break

                # Обработать tool calls
                tool_results = []
                for tc in response.tool_calls:
                    func_name = tc.get("function", {}).get("name", "")
                    func_args_str = tc.get("function", {}).get("arguments", "{}")
                    try:
                        func_args = json.loads(func_args_str)
                    except json.JSONDecodeError:
                        func_args = {}

                    # Вызвать соответствующий tool
                    tool_result = self._execute_tool(func_name, func_args, task_id)
                    tool_results.append({
                        "tool_call_id": tc.get("id", ""),
                        "role": "tool",
                        "name": func_name,
                        "content": json.dumps(tool_result, ensure_ascii=False)[:2000],
                    })

                    # Отследить делегацию
                    if func_name == "delegate_task":
                        delegation_chain.append({
                            "from": self.agent_server.agent_name,
                            "to": func_args.get("target_agent", "unknown"),
                            "task": func_args.get("task", "")[:100],
                        })

                # Добавить assistant message с tool_calls и tool results
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": response.tool_calls,
                })
                for tr in tool_results:
                    messages.append(tr)

            # Если цикл завершился без финального ответа
            if not final_response:
                final_response = messages[-1].get("content", "Task completed via delegation.")

            result = {
                "response": final_response,
                "agent": self.agent_server.agent_name,
                "model": self.agent_server.model,
                "delegation_chain": delegation_chain,
            }

            # Сохранить в conversation log
            if self.agent_server.hub_client:
                if not task_id:
                    import uuid as _uuid
                    task_id = f"chat-{_uuid.uuid4().hex[:8]}"
                self.agent_server.hub_client._post_conversation_message(
                    task_id=task_id, role="user",
                    content=user_message[:500], agent="user"
                )
                self.agent_server.hub_client._post_conversation_message(
                    task_id=task_id, role="assistant",
                    content=final_response[:2000],
                    agent=self.agent_server.agent_name,
                    metadata={"model": self.agent_server.model, "delegations": delegation_chain}
                )

            self._send_json(result)
        except Exception as e:
            logger.error(f"A2A message error: {e}", exc_info=True)
            self._send_json({"error": str(e)}, 500)

    def _execute_tool(self, tool_name: str, args: Dict[str, Any], task_id: str) -> Any:
        """Вызвать A2A tool и вернуть результат."""
        if tool_name == "delegate_task":
            return self._tool_delegate(args, task_id)
        else:
            return {"error": f"Unknown tool: {tool_name}. Available: delegate_task"}

    def _tool_delegate(self, args: Dict[str, Any], task_id: str) -> Dict[str, Any]:
        """Делегировать задачу другому агенту через Hub."""
        target = args.get("target_agent", "")
        task = args.get("task", "")
        context = args.get("context", "")

        if not self.agent_server.hub_client:
            return {"error": "No Hub connection"}

        try:
            full_task = task
            if context:
                full_task = f"{task}\n\nContext: {context}"

            result = self.agent_server.hub_client.delegate_task(
                text=full_task,
                target_agent=target,
                context={"delegated_by": self.agent_server.agent_name, "original_task_id": task_id},
            )
            return {
                "status": "delegated",
                "target_agent": target,
                "result": result,
            }
        except Exception as e:
            return {"error": f"Delegation failed: {e}"}

    # --- Tool Handlers ---

    def _handle_tool_web_search(self, data: Optional[Dict]) -> None:
        """Поиск через SearXNG HTTP API."""
        if not data or "query" not in data:
            self._send_json({"error": "Missing 'query'"}, 400)
            return
        try:
            import httpx
            params = {"q": data["query"], "format": "json"}
            if data.get("language"):
                params["language"] = data["language"]
            if data.get("time_range"):
                params["time_range"] = data["time_range"]
            resp = httpx.get("http://127.0.0.1:8888/search", params=params, timeout=30)
            results = resp.json().get("results", [])[:10]
            self._send_json({"results": [
                {"title": r.get("title",""), "url": r.get("url",""), "snippet": r.get("content","")[:300]}
                for r in results
            ]})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tool_web_fetch(self, data: Optional[Dict]) -> None:
        """Получить содержимое веб-страницы."""
        if not data or "url" not in data:
            self._send_json({"error": "Missing 'url'"}, 400)
            return
        try:
            import httpx
            max_len = data.get("max_length", 5000)
            resp = httpx.get(data["url"], timeout=30, follow_redirects=True)
            self._send_json({"url": data["url"], "status": resp.status_code, "content": resp.text[:max_len]})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tool_memory_search(self, data: Optional[Dict]) -> None:
        """Поиск в engram памяти через CLI."""
        if not data or "query" not in data:
            self._send_json({"error": "Missing 'query'"}, 400)
            return
        try:
            import subprocess
            query = data["query"].replace('"', '\\"')
            limit = data.get("limit", 10)
            result = subprocess.run(
                ["engram", "search", query, "--limit", str(limit), "--project", "linux-arch-kde-plasma-side-panel"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self._send_json({"results": result.stdout.strip()})
            else:
                self._send_json({"error": result.stderr}, 500)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tool_memory_save(self, data: Optional[Dict]) -> None:
        """Сохранить в engram память через CLI."""
        if not data or "title" not in data or "content" not in data:
            self._send_json({"error": "Missing 'title' or 'content'"}, 400)
            return
        try:
            import subprocess
            title = data["title"]
            content = data["content"]
            mem_type = data.get("type", "manual")
            result = subprocess.run(
                ["engram", "save", title, content, "--type", mem_type, "--project", "linux-arch-kde-plasma-side-panel"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self._send_json({"status": "saved", "result": result.stdout.strip()})
            else:
                self._send_json({"error": result.stderr}, 500)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_tool_codebase_search(self, data: Optional[Dict]) -> None:
        """Поиск по кодовой базе через grep."""
        if not data or "query" not in data:
            self._send_json({"error": "Missing 'query'"}, 400)
            return
        try:
            import subprocess
            query = data["query"]
            file_pattern = data.get("file_pattern", "*")
            limit = data.get("limit", 10)
            cmd = f'cd {_project_root} && grep -r -n --include="{file_pattern}" -m {limit} "{query}" --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=build --exclude-dir=.venv 2>/dev/null | head -{limit}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            self._send_json({"results": [{"line": l} for l in lines[:limit]]})
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
