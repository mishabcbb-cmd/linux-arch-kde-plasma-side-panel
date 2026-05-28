"""A2A Hub — маршрутизатор задач между агентами."""

import logging
from typing import Dict, List, Optional

from .models import AgentInfo, AgentStatus, TaskRoute, TaskState

logger = logging.getLogger(__name__)


class TaskRouter:
    """Маршрутизирует задачи между агентами на основе capabilities."""

    def __init__(self, max_hops: int = 3):
        self._agents: Dict[str, AgentInfo] = {}
        self._max_hops = max_hops

    def register_agent(self, agent: AgentInfo) -> None:
        """Зарегистрировать агента для маршрутизации."""
        self._agents[agent.name] = agent
        logger.info(f"Agent registered for routing: {agent.name} (capabilities: {agent.capabilities})")

    def unregister_agent(self, name: str) -> None:
        """Удалить агента из маршрутизации."""
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Agent unregistered from routing: {name}")

    def find_agent_for_task(self, required_capabilities: List[str]) -> Optional[AgentInfo]:
        """Найти лучшего агента для задачи по требуемым capabilities."""
        best_match: Optional[AgentInfo] = None
        best_score = 0

        for agent in self._agents.values():
            if agent.status != AgentStatus.ACTIVE:
                continue

            # Считаем совпадения capabilities
            score = sum(1 for cap in required_capabilities if cap in agent.capabilities)
            if score > best_score:
                best_score = score
                best_match = agent

        if best_match:
            logger.info(
                f"Routed task (caps: {required_capabilities}) → {best_match.name} "
                f"(score: {best_score}/{len(required_capabilities)})"
            )
        else:
            logger.warning(f"No agent found for capabilities: {required_capabilities}")

        return best_match

    def get_all_agents(self) -> List[AgentInfo]:
        """Получить список всех зарегистрированных агентов."""
        return list(self._agents.values())

    def get_active_agents(self) -> List[AgentInfo]:
        """Получить только активных агентов."""
        return [a for a in self._agents.values() if a.status == AgentStatus.ACTIVE]

    def create_route(
        self,
        task_id: str,
        source_agent: str,
        target_agent: str,
        task_text: str,
        context: Optional[Dict] = None,
    ) -> TaskRoute:
        """Создать маршрут задачи."""
        route = TaskRoute(
            task_id=task_id,
            source_agent=source_agent,
            target_agent=target_agent,
            task_text=task_text,
            context=context or {},
        )
        logger.info(f"Route created: {source_agent} → {target_agent} (task: {task_id})")
        return route

    def infer_capabilities_from_text(self, text: str) -> List[str]:
        """Вывести необходимые capabilities из текста задачи."""
        text_lower = text.lower()
        capabilities = []

        # Маппинг ключевых слов → capabilities
        keyword_map = {
            "code_analysis": ["code", "analyze", "review", "refactor", "debug", "код", "анализ"],
            "file_operations": ["file", "read", "write", "edit", "файл", "прочитать", "записать"],
            "bash_execution": ["run", "execute", "command", "bash", "shell", "выполнить", "запустить"],
            "search": ["search", "find", "grep", "поиск", "найти"],
            "rag": ["context", "memory", "recall", "контекст", "память"],
            "github_analysis": ["github", "repo", "commit", "pull request", "pr", "гитхаб"],
            "pr_review": ["pull request", "pr review", "review pr", "ревью"],
            "issue_tracking": ["issue", "bug", "ticket", "issue", "баг"],
            "web_search": ["search web", "find online", "research", "поиск в интернете", "найти в сети"],
            "summarization": ["summarize", "summary", "суммаризировать", "кратко"],
            "fact_checking": ["verify", "fact check", "проверить факт"],
            "security_analysis": ["security", "vulnerability", "безопасность", "уязвимость"],
            "performance_analysis": ["performance", "optimize", "optimization", "производительность"],
        }

        for capability, keywords in keyword_map.items():
            if any(kw in text_lower for kw in keywords):
                capabilities.append(capability)

        return capabilities
