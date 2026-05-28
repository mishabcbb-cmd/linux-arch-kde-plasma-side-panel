#!/usr/bin/env python3
"""A2A Hub MCP Server — объединяет MCP протокол с A2A Hub.

MCP (Model Context Protocol) — для инструментов и ресурсов.
A2A (Agent2Agent) — для коммуникации между агентами.

Архитектура:
    VS Code / Claude → MCP → A2A Hub → Агенты (OWL, Qwen)
                                  ↓
                            MCP Tools:
                              - list_agents
                              - delegate_task
                              - get_shared_context
                              - remember / recall
                              - get_agent_card
"""

import json
import logging
import os
import sys
import threading
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("mcp-server")


class A2AMCPServer:
    """MCP Server который оборачивает A2A Hub.

    Реализует MCP протокол (JSON-RPC 2.0 over stdio/SSE)
    и предоставляет инструменты для работы с A2A Hub.
    """

    def __init__(self, hub_url: str = "http://127.0.0.1:9000"):
        self.hub_url = hub_url
        self._client = None
        self._tools = self._build_tools()

    def _get_client(self):
        if self._client is None:
            from a2a_hub.client.hub_client import A2AHubClient
            self._client = A2AHubClient(
                hub_url=self.hub_url,
                agent_name="mcp-server",
                agent_description="A2A Hub MCP Server",
                agent_endpoint="",
                capabilities=["mcp", "orchestration"],
            )
            self._client.register()
        return self._client

    def _build_tools(self) -> List[Dict[str, Any]]:
        """Определить MCP tools — инструменты доступные через MCP."""
        return [
            {
                "name": "list_agents",
                "description": "Список всех зарегистрированных агентов в A2A Hub с их capabilities и статусом",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "filter_capability": {
                            "type": "string",
                            "description": "Фильтр по capability (например 'code_analysis')",
                        },
                        "active_only": {
                            "type": "boolean",
                            "description": "Только активные агенты",
                            "default": True,
                        },
                    },
                },
            },
            {
                "name": "delegate_task",
                "description": "Делегировать задачу агенту через A2A Hub. Hub автоматически выберет лучшего агента или можно указать явно.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Текст задачи для выполнения",
                        },
                        "target_agent": {
                            "type": "string",
                            "description": "Имя конкретного агента (опционально)",
                        },
                        "context": {
                            "type": "object",
                            "description": "Дополнительный контекст для агента",
                        },
                    },
                    "required": ["task"],
                },
            },
            {
                "name": "get_agent_card",
                "description": "Получить Agent Card — описание возможностей агента",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "Имя агента",
                        },
                    },
                    "required": ["agent_name"],
                },
            },
            {
                "name": "get_shared_context",
                "description": "Получить общий контекст (память) из A2A Hub — все факты, которые агенты сохранили",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "search": {
                            "type": "string",
                            "description": "Поисковый запрос для фильтрации",
                        },
                    },
                },
            },
            {
                "name": "remember",
                "description": "Сохранить факт в общую память A2A Hub — доступен всем агентам",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Ключ для сохранения",
                        },
                        "value": {
                            "type": "string",
                            "description": "Значение (строка или JSON)",
                        },
                    },
                    "required": ["key", "value"],
                },
            },
            {
                "name": "recall",
                "description": "Получить факт из общей памяти A2A Hub",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "Ключ для поиска",
                        },
                    },
                    "required": ["key"],
                },
            },
            {
                "name": "get_task_history",
                "description": "Получить историю задач из A2A Hub — кто что делал",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Максимум задач",
                            "default": 20,
                        },
                    },
                },
            },
        ]

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Обработать MCP JSON-RPC запрос."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        try:
            if method == "initialize":
                return self._response(req_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "a2a-hub-mcp",
                        "version": "1.0.0",
                    },
                })

            elif method == "tools/list":
                return self._response(req_id, {"tools": self._tools})

            elif method == "tools/call":
                result = self._call_tool(params.get("name", ""), params.get("arguments", {}))
                return self._response(req_id, {"content": [{"type": "text", "text": result}]})

            elif method == "notifications/initialized":
                logger.info("MCP client initialized")
                return None

            else:
                return self._error(req_id, -32601, f"Method not found: {method}")

        except Exception as e:
            logger.error(f"MCP error: {e}")
            return self._error(req_id, -32603, str(e))

    def _call_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Вызвать MCP tool."""
        client = self._get_client()

        if name == "list_agents":
            agents = client.discover_agents()
            if args.get("active_only", True):
                agents = [a for a in agents if a.get("status") == "active"]
            if args.get("filter_capability"):
                cap = args["filter_capability"]
                agents = [a for a in agents if cap in a.get("capabilities", [])]
            return json.dumps(agents, indent=2, ensure_ascii=False)

        elif name == "delegate_task":
            task = args["task"]
            target = args.get("target_agent")
            context = args.get("context", {})

            if target:
                result = client.delegate_task(task, target, context)
            else:
                result = client.submit_task(task, context=context)
            return json.dumps(result, indent=2, ensure_ascii=False)

        elif name == "get_agent_card":
            agents = client.discover_agents()
            for a in agents:
                if a["name"] == args["agent_name"]:
                    return json.dumps(a, indent=2, ensure_ascii=False)
            return json.dumps({"error": f"Agent '{args['agent_name']}' not found"})

        elif name == "get_shared_context":
            if args.get("search"):
                results = client.search_memory(args["search"])
                return json.dumps(results, indent=2, ensure_ascii=False)
            memory = client._client._get_client()._client.get_all_memory() if hasattr(client, '_client') else {}
            # Fallback: получить через HTTP
            import httpx
            resp = httpx.get(f"{self.hub_url}/context")
            return json.dumps(resp.json(), indent=2, ensure_ascii=False)

        elif name == "remember":
            client.remember(args["key"], args["value"])
            return json.dumps({"status": "ok", "key": args["key"]})

        elif name == "recall":
            value = client.recall(args["key"])
            return json.dumps({"key": args["key"], "value": value})

        elif name == "get_task_history":
            import httpx
            resp = httpx.get(f"{self.hub_url}/tasks")
            tasks = resp.json().get("tasks", [])
            limit = args.get("limit", 20)
            return json.dumps(tasks[:limit], indent=2, ensure_ascii=False)

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    def _response(self, req_id: Any, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id: Any, code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    def run_stdio(self):
        """Запустить MCP Server на stdio (для VS Code / Claude Desktop)."""
        logger.info("A2A Hub MCP Server starting on stdio...")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                if response:
                    print(json.dumps(response, ensure_ascii=False), flush=True)
            except json.JSONDecodeError:
                pass

    def run_sse(self, host: str = "127.0.0.1", port: int = 9001):
        """Запустить MCP Server на SSE (для веб-клиентов)."""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        server = self

        class SSEHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                try:
                    request = json.loads(body)
                    response = server.handle_request(request)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    if response:
                        self.wfile.write(json.dumps(response).encode())
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.end_headers()

            def log_message(self, fmt, *args):
                logger.debug(f"MCP SSE: {fmt % args}")

        httpd = HTTPServer((host, port), SSEHandler)
        logger.info(f"A2A Hub MCP Server starting on http://{host}:{port}")
        httpd.serve_forever()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="A2A Hub MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--hub-url", default="http://127.0.0.1:9000")
    args = parser.parse_args()

    server = A2AMCPServer(hub_url=args.hub_url)

    if args.transport == "stdio":
        server.run_stdio()
    else:
        server.run_sse(args.host, args.port)


if __name__ == "__main__":
    main()
