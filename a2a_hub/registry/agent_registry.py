"""A2A Hub — реестр агентов.

Хранит информацию о всех зарегистрированных агентах,
обрабатывает регистрацию/дерегистрацию, heartbeat.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ..server.models import AgentInfo, AgentRole, AgentStatus

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Реестр агентов — хранит и управляет информацией обо всех агентах."""

    def __init__(self, config_path: str):
        self._config_path = config_path
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = threading.Lock()
        self._heartbeat_interval = 30  # секунд
        self._heartbeat_timeout = 90   # секунд без heartbeat = inactive
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

        # Загрузить агентов из конфигурации
        self._load_from_config()

    def _load_from_config(self) -> None:
        """Загрузить агентов из YAML конфигурации."""
        config_file = Path(self._config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {self._config_path}")
            return

        with open(config_file) as f:
            config = yaml.safe_load(f)

        for agent_data in config.get("agents", []):
            metadata = agent_data.get("metadata", {})
            if "model_name" in agent_data:
                metadata["model_name"] = agent_data["model_name"]
            agent = AgentInfo(
                name=agent_data["name"],
                description=agent_data["description"],
                role=AgentRole(agent_data["role"]),
                endpoint=agent_data["endpoint"],
                agent_card_url=agent_data.get("agent_card_url", ""),
                capabilities=agent_data.get("capabilities", []),
                auth_type=agent_data.get("auth_type", "none"),
                status=AgentStatus.ACTIVE if agent_data.get("status") == "active" else AgentStatus.INACTIVE,
                last_seen=datetime.now(),
                metadata=metadata,
            )
            self._agents[agent.name] = agent
            logger.info(f"Loaded agent from config: {agent.name}")

    def register(self, agent: AgentInfo) -> bool:
        """Зарегистрировать нового агента."""
        with self._lock:
            if agent.name in self._agents:
                logger.warning(f"Agent '{agent.name}' already registered, updating")
            agent.last_seen = datetime.now()
            agent.status = AgentStatus.ACTIVE
            self._agents[agent.name] = agent
            logger.info(f"Agent registered: {agent.name} at {agent.endpoint}")
            return True

    def unregister(self, name: str) -> bool:
        """Удалить агента из реестра."""
        with self._lock:
            if name in self._agents:
                del self._agents[name]
                logger.info(f"Agent unregistered: {name}")
                return True
            return False

    def heartbeat(self, name: str) -> bool:
        """Обновить heartbeat агента."""
        with self._lock:
            if name in self._agents:
                self._agents[name].last_seen = datetime.now()
                if self._agents[name].status == AgentStatus.INACTIVE:
                    self._agents[name].status = AgentStatus.ACTIVE
                    logger.info(f"Agent reactivated: {name}")
                return True
            return False

    def get_agent(self, name: str) -> Optional[AgentInfo]:
        """Получить информацию об агенте по имени."""
        return self._agents.get(name)

    def get_all_agents(self) -> List[AgentInfo]:
        """Получить список всех агентов."""
        return list(self._agents.values())

    def get_active_agents(self) -> List[AgentInfo]:
        """Получить только активных агентов."""
        return [a for a in self._agents.values() if a.status == AgentStatus.ACTIVE]

    def get_agents_by_capability(self, capability: str) -> List[AgentInfo]:
        """Найти агентов с определённым capability."""
        return [
            a for a in self._agents.values()
            if capability in a.capabilities and a.status == AgentStatus.ACTIVE
        ]

    def set_agent_status(self, name: str, status: AgentStatus) -> bool:
        """Установить статус агента."""
        with self._lock:
            if name in self._agents:
                self._agents[name].status = status
                logger.info(f"Agent '{name}' status → {status.value}")
                return True
            return False

    def start_monitoring(self) -> None:
        """Запустить мониторинг heartbeat в фоне."""
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Agent heartbeat monitoring started")

    def stop_monitoring(self) -> None:
        """Остановить мониторинг."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)

    def _monitor_loop(self) -> None:
        """Фоновый цикл проверки heartbeat."""
        while self._running:
            time.sleep(self._heartbeat_interval)
            now = datetime.now()
            with self._lock:
                for agent in self._agents.values():
                    if agent.last_seen:
                        delta = (now - agent.last_seen).total_seconds()
                        if delta > self._heartbeat_timeout and agent.status == AgentStatus.ACTIVE:
                            agent.status = AgentStatus.INACTIVE
                            logger.warning(
                                f"Agent '{agent.name}' marked INACTIVE "
                                f"(last heartbeat: {delta:.0f}s ago)"
                            )

    def to_dict(self) -> Dict:
        """Сериализовать реестр в dict."""
        return {
            "agents": {name: agent.to_dict() for name, agent in self._agents.items()},
            "total": len(self._agents),
            "active": len(self.get_active_agents()),
        }
