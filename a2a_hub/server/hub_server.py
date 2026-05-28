"""A2A Hub Server — центральный оркестратор.

Реализует HTTP API для:
- Регистрации/дерегистрации агентов
- Маршрутизации задач между агентами
- Доступа к общему контексту
- Мониторинга состояния агентов
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs

import yaml

from .models import AgentInfo, AgentRole, AgentStatus, HubConfig, HubTask, TaskState
from .router import TaskRouter
from ..registry.agent_registry import AgentRegistry
from ..context.context_store import ContextStore

logger = logging.getLogger(__name__)


class HubHTTPHandler(BaseHTTPRequestHandler):
    """HTTP обработчик для A2A Hub API."""

    # Ссылка на Hub Server (устанавливается при создании)
    hub_server: "A2AHubServer" = None

    def log_message(self, format, *args):
        """Перенаправить логи HTTP сервера в наш логгер."""
        logger.debug(f"HTTP: {format % args}")

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Отправить JSON ответ."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False, default=str).encode())

    def _read_json(self) -> Optional[Dict]:
        """Прочитать JSON из тела запроса."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body = self.rfile.read(content_length)
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return None
        return None

    # --- GET ---

    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "":
            path = "/"

        if path == "/":
            agents = self.hub_server.registry.get_all_agents()
            active = [a for a in agents if a.status == AgentStatus.ACTIVE]
            conversations = self.hub_server.context_store.list_conversations(limit=5)
            self._send_json({
                "service": "A2A Hub",
                "version": "1.0.0",
                "status": "running",
                "uptime": self.hub_server.uptime,
                "agents": {
                    "total": len(agents),
                    "active": len(active),
                    "list": [{"name": a.name, "status": a.status.value, "capabilities": a.capabilities, "endpoint": a.endpoint} for a in agents],
                },
                "conversations": {
                    "total": len(self.hub_server.context_store.list_conversations(limit=1000)),
                    "recent": [{"task_id": c.get("task_id"), "messages": len(c.get("messages", [])), "updated_at": c.get("updated_at")} for c in conversations],
                },
                "endpoints": [
                    "GET  /health",
                    "GET  /agents",
                    "GET  /agents/active",
                    "GET  /agents/{name}",
                    "POST /agents/register",
                    "POST /agents/heartbeat",
                    "POST /tasks/submit",
                    "POST /tasks/delegate",
                    "GET  /tasks",
                    "GET  /tasks/{id}",
                    "GET  /context",
                    "GET  /conversations",
                    "GET  /conversations/{task_id}",
                    "POST /conversations/message",
                    "GET  /context/stats",
                ],
            })

        elif path == "/agents":
            agents = self.hub_server.registry.get_all_agents()
            self._send_json({"agents": [a.to_dict() for a in agents]})

        elif path == "/agents/active":
            agents = self.hub_server.registry.get_active_agents()
            self._send_json({"agents": [a.to_dict() for a in agents]})

        elif path.startswith("/agents/"):
            name = path[len("/agents/"):]
            agent = self.hub_server.registry.get_agent(name)
            if agent:
                self._send_json(agent.to_dict())
            else:
                self._send_json({"error": f"Agent '{name}' not found"}, 404)

        elif path == "/context":
            self._send_json(self.hub_server.context_store.get_all_memory())

        elif path == "/context/files":
            self._send_json({"files": self.hub_server.context_store.list_files()})

        elif path == "/context/tasks":
            self._send_json({"tasks": self.hub_server.context_store.list_tasks()})

        elif path == "/context/projects":
            self._send_json({"projects": self.hub_server.context_store.list_projects()})

        elif path == "/context/stats":
            self._send_json(self.hub_server.context_store.get_stats())

        elif path == "/conversations":
            # GET /conversations — список всех разговоров
            limit = int(self.path.split("limit=")[1]) if "limit=" in self.path else 50
            conversations = self.hub_server.context_store.list_conversations(limit=limit)
            self._send_json({"conversations": conversations, "total": len(conversations)})

        elif path.startswith("/conversations/"):
            # GET /conversations/{task_id} — полный лог переписки
            task_id = path[len("/conversations/"):]
            conv = self.hub_server.context_store.get_conversation(task_id)
            if conv:
                self._send_json(conv)
            else:
                self._send_json({"error": f"Conversation '{task_id}' not found"}, 404)

        elif path == "/tasks":
            self._send_json({"tasks": self.hub_server.list_tasks()})

        elif path.startswith("/tasks/"):
            task_id = path[len("/tasks/"):]
            task = self.hub_server.get_task(task_id)
            if task:
                self._send_json(self._task_to_dict(task))
            else:
                # Проверить сохранённые результаты
                result = self.hub_server.context_store.get_task_result(task_id)
                if result:
                    self._send_json(result)
                else:
                    self._send_json({"error": f"Task '{task_id}' not found"}, 404)

        elif path == "/health":
            self._send_json({
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": self.hub_server.uptime,
            })

        else:
            self._send_json({"error": "Not found"}, 404)

    # --- POST ---

    def do_POST(self):
        path = self.path.rstrip("/")
        data = self._read_json()

        if path == "/agents/register":
            self._handle_register(data)

        elif path == "/agents/heartbeat":
            self._handle_heartbeat(data)

        elif path == "/tasks/submit":
            self._handle_submit_task(data)

        elif path == "/tasks/delegate":
            self._handle_delegate_task(data)

        elif path == "/context/remember":
            self._handle_remember(data)

        elif path == "/context/recall":
            self._handle_recall(data)

        elif path == "/conversations/message":
            # POST /conversations/message — добавить сообщение в лог
            task_id = data.get("task_id", "")
            role = data.get("role", "user")
            content = data.get("content", "")
            agent = data.get("agent", "")
            metadata = data.get("metadata", None)
            if not task_id or not content:
                self._send_json({"error": "Missing 'task_id' or 'content'"}, 400)
                return
            self.hub_server.context_store.add_conversation_message(
                task_id=task_id, role=role, content=content, agent=agent, metadata=metadata
            )
            self._send_json({"status": "ok", "task_id": task_id})

        else:
            self._send_json({"error": "Not found"}, 404)

    # --- DELETE ---

    def do_DELETE(self):
        path = self.path.rstrip("/")

        if path.startswith("/agents/"):
            name = path[len("/agents/"):]
            if self.hub_server.registry.unregister(name):
                self.hub_server.router.unregister_agent(name)
                self._send_json({"status": "unregistered", "name": name})
            else:
                self._send_json({"error": f"Agent '{name}' not found"}, 404)

        else:
            self._send_json({"error": "Not found"}, 404)

    # --- Handlers ---

    def _handle_register(self, data: Optional[Dict]) -> None:
        if not data or "name" not in data:
            self._send_json({"error": "Missing 'name' in request"}, 400)
            return

        agent = AgentInfo(
            name=data["name"],
            description=data.get("description", ""),
            role=AgentRole(data.get("role", "api")),
            endpoint=data.get("endpoint", ""),
            agent_card_url=data.get("agent_card_url", ""),
            capabilities=data.get("capabilities", []),
            auth_type=data.get("auth_type", "none"),
            metadata=data.get("metadata", {}),
        )

        self.hub_server.registry.register(agent)
        self.hub_server.router.register_agent(agent)
        self._send_json({"status": "registered", "agent": agent.to_dict()})

    def _handle_heartbeat(self, data: Optional[Dict]) -> None:
        if not data or "name" not in data:
            self._send_json({"error": "Missing 'name' in request"}, 400)
            return

        name = data["name"]
        if self.hub_server.registry.heartbeat(name):
            self._send_json({"status": "ok", "name": name})
        else:
            self._send_json({"error": f"Agent '{name}' not registered"}, 404)

    def _handle_submit_task(self, data: Optional[Dict]) -> None:
        if not data or "text" not in data:
            self._send_json({"error": "Missing 'text' in request"}, 400)
            return

        task_text = data["text"]
        source_agent = data.get("source_agent", "anonymous")
        context = data.get("context", {})
        target_agent = data.get("target_agent")

        task_id = str(uuid.uuid4())[:8]

        # Создать задачу
        task = HubTask(
            task_id=task_id,
            text=task_text,
            context=context,
        )

        # Определить целевого агента
        if target_agent:
            agent = self.hub_server.registry.get_agent(target_agent)
            if not agent:
                self._send_json({"error": f"Target agent '{target_agent}' not found"}, 404)
                return
        else:
            # Автоматическая маршрутизация по capabilities
            required_caps = self.hub_server.router.infer_capabilities_from_text(task_text)
            agent = self.hub_server.router.find_agent_for_task(required_caps)

        if not agent:
            self._send_json({"error": "No suitable agent found for this task"}, 503)
            return

        # Создать маршрут
        route = self.hub_server.router.create_route(
            task_id=task_id,
            source_agent=source_agent,
            target_agent=agent.name,
            task_text=task_text,
            context=context,
        )
        task.routes.append(route)
        task.state = TaskState.WORKING

        # Сохранить задачу
        self.hub_server.add_task(task)

        self._send_json({
            "task_id": task_id,
            "state": task.state.value,
            "routed_to": agent.name,
            "endpoint": agent.endpoint,
            "message": f"Task routed to {agent.name} at {agent.endpoint}",
        })

    def _handle_delegate_task(self, data: Optional[Dict]) -> None:
        """Агент делегирует подзадачу другому агенту через Hub."""
        if not data or "text" not in data or "target_agent" not in data:
            self._send_json({"error": "Missing 'text' or 'target_agent'"}, 400)
            return

        task_id = str(uuid.uuid4())[:8]
        source = data.get("source_agent", "anonymous")
        target_name = data["target_agent"]
        task_text = data["text"]

        target = self.hub_server.registry.get_agent(target_name)
        if not target:
            self._send_json({"error": f"Agent '{target_name}' not found"}, 404)
            return

        route = self.hub_server.router.create_route(
            task_id=task_id,
            source_agent=source,
            target_agent=target_name,
            task_text=task_text,
            context=data.get("context", {}),
        )

        task = HubTask(
            task_id=task_id,
            text=task_text,
            context=data.get("context", {}),
            routes=[route],
            state=TaskState.WORKING,
        )
        self.hub_server.add_task(task)

        self._send_json({
            "task_id": task_id,
            "delegated_to": target_name,
            "endpoint": target.endpoint,
            "state": "working",
        })

    def _handle_remember(self, data: Optional[Dict]) -> None:
        if not data or "key" not in data:
            self._send_json({"error": "Missing 'key'"}, 400)
            return

        self.hub_server.context_store.remember(
            key=data["key"],
            value=data.get("value"),
            agent=data.get("agent", "anonymous"),
        )
        self._send_json({"status": "ok", "key": data["key"]})

    def _handle_recall(self, data: Optional[Dict]) -> None:
        if not data or "key" not in data:
            self._send_json({"error": "Missing 'key'"}, 400)
            return

        value = self.hub_server.context_store.recall(data["key"])
        self._send_json({"key": data["key"], "value": value})

    # --- Helpers ---

    def _task_to_dict(self, task: HubTask) -> Dict:
        return {
            "task_id": task.task_id,
            "text": task.text,
            "state": task.state.value,
            "context": task.context,
            "routes": [
                {
                    "source": r.source_agent,
                    "target": r.target_agent,
                    "state": r.state.value,
                    "result": r.result,
                    "error": r.error,
                }
                for r in task.routes
            ],
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "artifacts": task.artifacts,
        }


class A2AHubServer:
    """A2A Hub — центральный оркестратор агентов."""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self._load_config(config_path)

        # Компоненты
        self.registry = AgentRegistry(config_path)
        self.router = TaskRouter(max_hops=self.config.max_hops)
        self.context_store = ContextStore(self.config.context_store)

        # Задачи
        self._tasks: Dict[str, HubTask] = {}
        self._tasks_lock = threading.Lock()

        # HTTP сервер
        self._server: Optional[HTTPServer] = None
        self._running = False
        self._start_time: Optional[datetime] = None

        # Инициализировать роутер из реестра
        for agent in self.registry.get_all_agents():
            self.router.register_agent(agent)

    def _load_config(self, config_path: str) -> HubConfig:
        """Загрузить конфигурацию Hub."""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file) as f:
                raw = yaml.safe_load(f)
            hub_raw = raw.get("hub", {})
            routing_raw = raw.get("routing", {})
            return HubConfig(
                host=hub_raw.get("host", "127.0.0.1"),
                port=hub_raw.get("port", 9000),
                workspace=hub_raw.get("workspace", "~/.local/share/a2a_hub/workspace"),
                context_store=hub_raw.get("context_store", "~/.local/share/a2a_hub/context"),
                log_level=hub_raw.get("log_level", "info"),
                max_hops=routing_raw.get("max_hops", 3),
                agent_timeout=routing_raw.get("agent_timeout", 120),
                routing_strategy=routing_raw.get("default_strategy", "capability_based"),
            )
        return HubConfig()

    @property
    def uptime(self) -> str:
        if self._start_time:
            delta = datetime.now() - self._start_time
            return str(delta).split(".")[0]
        return "not started"

    def add_task(self, task: HubTask) -> None:
        with self._tasks_lock:
            self._tasks[task.task_id] = task

    def get_task(self, task_id: str) -> Optional[HubTask]:
        with self._tasks_lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict]:
        with self._tasks_lock:
            return [
                {
                    "task_id": t.task_id,
                    "text": t.text[:100],
                    "state": t.state.value,
                    "routes": len(t.routes),
                    "created_at": t.created_at.isoformat(),
                }
                for t in self._tasks.values()
            ]

    def start(self) -> None:
        """Запустить A2A Hub."""
        host = self.config.host
        port = self.config.port

        # Настроить HTTP handler
        HubHTTPHandler.hub_server = self

        self._server = HTTPServer((host, port), HubHTTPHandler)
        self._running = True
        self._start_time = datetime.now()

        # Запустить мониторинг heartbeat
        self.registry.start_monitoring()

        logger.info(f"╔══════════════════════════════════════════╗")
        logger.info(f"║         A2A Hub Server v1.0.0            ║")
        logger.info(f"║  http://{host}:{port}                      ║")
        logger.info(f"║  Agents: {len(self.registry.get_all_agents())} registered              ║")
        logger.info(f"╚══════════════════════════════════════════╝")

        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down A2A Hub...")
        finally:
            self.stop()

    def stop(self) -> None:
        """Остановить A2A Hub."""
        self._running = False
        if self._server:
            self._server.shutdown()
        self.registry.stop_monitoring()
        self.context_store.save()
        logger.info("A2A Hub stopped.")
