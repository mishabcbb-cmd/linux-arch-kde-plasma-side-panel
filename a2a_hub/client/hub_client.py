"""A2A Hub Client — SDK для подключения агентов к Hub.

Используется агентами для:
- Регистрации в Hub
- Отправки heartbeat
- Делегирования задач другим агентам
- Доступа к общему контексту
"""

import json
import logging
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class A2AHubClient:
    """Клиент для взаимодействия с A2A Hub."""

    def __init__(
        self,
        hub_url: str = "http://127.0.0.1:9000",
        agent_name: str = "",
        agent_description: str = "",
        agent_endpoint: str = "",
        capabilities: Optional[List[str]] = None,
        heartbeat_interval: int = 15,
    ):
        self.hub_url = hub_url.rstrip("/")
        self.agent_name = agent_name
        self.agent_description = agent_description
        self.agent_endpoint = agent_endpoint
        self.capabilities = capabilities or []
        self._heartbeat_interval = heartbeat_interval
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._running = False
        self._client = httpx.Client(timeout=30.0)

    def _request(self, method: str, path: str, data: Optional[Dict] = None) -> Dict:
        """Отправить HTTP запрос к Hub."""
        url = f"{self.hub_url}{path}"
        try:
            if method == "GET":
                resp = self._client.get(url)
            elif method == "POST":
                resp = self._client.post(url, json=data)
            elif method == "DELETE":
                resp = self._client.delete(url)
            else:
                return {"error": f"Unsupported method: {method}"}

            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": resp.text, "status": resp.status_code}
        except httpx.ConnectError:
            return {"error": f"Cannot connect to Hub at {self.hub_url}"}
        except httpx.TimeoutException:
            return {"error": "Hub request timed out"}

    # --- Registration ---

    def register(self) -> bool:
        """Зарегистрировать агента в Hub."""
        result = self._request("POST", "/agents/register", {
            "name": self.agent_name,
            "description": self.agent_description,
            "role": "local" if "localhost" in self.agent_endpoint else "api",
            "endpoint": self.agent_endpoint,
            "agent_card_url": f"{self.agent_endpoint}/.well-known/agent-card.json",
            "capabilities": self.capabilities,
            "auth_type": "none",
        })

        if "error" in result:
            logger.error(f"Registration failed: {result['error']}")
            return False

        logger.info(f"Registered in A2A Hub: {self.agent_name}")
        return True

    def unregister(self) -> bool:
        """Удалить агента из Hub."""
        result = self._request("DELETE", f"/agents/{self.agent_name}")
        return "error" not in result

    # --- Heartbeat ---

    def heartbeat(self) -> bool:
        """Отправить heartbeat в Hub."""
        result = self._request("POST", "/agents/heartbeat", {"name": self.agent_name})
        return "error" not in result

    def start_heartbeat(self) -> None:
        """Запустить автоматический heartbeat в фоне."""
        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        logger.info(f"Heartbeat started (interval: {self._heartbeat_interval}s)")

    def stop_heartbeat(self) -> None:
        """Остановить heartbeat."""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)

    def _heartbeat_loop(self) -> None:
        while self._running:
            self.heartbeat()
            time.sleep(self._heartbeat_interval)

    # --- Tasks ---

    def submit_task(self, text: str, target_agent: Optional[str] = None, context: Optional[Dict] = None) -> Dict:
        """Отправить задачу в Hub для маршрутизации."""
        data = {
            "text": text,
            "source_agent": self.agent_name,
            "context": context or {},
        }
        if target_agent:
            data["target_agent"] = target_agent

        return self._request("POST", "/tasks/submit", data)

    def _post_conversation_message(self, task_id: str, role: str, content: str, agent: str = "", metadata: Optional[Dict] = None) -> Dict:
        """Добавить сообщение в conversation log (внутренний метод)."""
        data = {
            "task_id": task_id,
            "role": role,
            "content": content,
            "agent": agent,
        }
        if metadata:
            data["metadata"] = metadata
        return self._request("POST", "/conversations/message", data)

    def delegate_task(self, text: str, target_agent: str, context: Optional[Dict] = None) -> Dict:
        """Делегировать подзадачу конкретному агенту через Hub."""
        return self._request("POST", "/tasks/delegate", {
            "text": text,
            "source_agent": self.agent_name,
            "target_agent": target_agent,
            "context": context or {},
        })

    def get_task(self, task_id: str) -> Dict:
        """Получить статус задачи."""
        return self._request("GET", f"/tasks/{task_id}")

    def list_tasks(self) -> Dict:
        """Список всех задач в Hub."""
        return self._request("GET", "/tasks")

    # --- Context ---

    def remember(self, key: str, value: Any) -> bool:
        """Сохранить факт в общую память."""
        result = self._request("POST", "/context/remember", {
            "key": key,
            "value": value,
            "agent": self.agent_name,
        })
        return "error" not in result

    def recall(self, key: str) -> Optional[Any]:
        """Получить факт из общей памяти."""
        result = self._request("POST", "/context/recall", {"key": key})
        if "error" not in result:
            return result.get("value")
        return None

    def search_memory(self, query: str) -> List[Dict]:
        """Поиск по общей памяти."""
        # Получаем всю память и фильтруем локально
        result = self._request("GET", "/context")
        if "error" in result:
            return []
        query_lower = query.lower()
        matches = []
        for key, entry in result.items():
            if query_lower in key.lower() or query_lower in str(entry.get("value", "")).lower():
                matches.append({"key": key, **entry})
        return matches

    def save_file(self, filename: str, content: str) -> bool:
        """Сохранить файл в общее рабочее пространство."""
        result = self._request("POST", "/context/remember", {
            "key": f"file:{filename}",
            "value": {"content": content, "agent": self.agent_name},
            "agent": self.agent_name,
        })
        return "error" not in result

    # --- Discovery ---

    def discover_agents(self) -> List[Dict]:
        """Получить список всех агентов."""
        result = self._request("GET", "/agents")
        return result.get("agents", [])

    def find_agent(self, capability: str) -> Optional[Dict]:
        """Найти агента по capability."""
        agents = self.discover_agents()
        for agent in agents:
            if capability in agent.get("capabilities", []):
                return agent
        return None

    # --- Lifecycle ---

    def close(self) -> None:
        """Закрыть клиент."""
        self.stop_heartbeat()
        self._client.close()
