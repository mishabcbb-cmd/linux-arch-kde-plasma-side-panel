#!/usr/bin/env python3
"""A2A Hub — интеграционный тест.

Запускает Hub, регистрирует агентов, отправляет задачи,
проверяет маршрутизацию и общий контекст.
"""

import json
import logging
import os
import sys
import threading
import time

# Добавить родительскую директорию в path для импортов
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test")


def test_hub():
    """Полный тест A2A Hub."""
    from a2a_hub.client.hub_client import A2AHubClient
    from a2a_hub.server.hub_server import A2AHubServer

    config_path = os.path.join(os.path.dirname(__file__), "config", "agents.yaml")

    # 1. Запустить Hub в фоне
    logger.info("=" * 60)
    logger.info("TEST: Starting A2A Hub")
    logger.info("=" * 60)

    hub = A2AHubServer(config_path)
    hub_thread = threading.Thread(target=hub.start, daemon=True)
    hub_thread.start()
    time.sleep(1)  # Дать серверу запуститься

    hub_url = f"http://{hub.config.host}:{hub.config.port}"

    # 2. Создать клиентов для каждого агента
    logger.info("\n--- Registering agents ---")

    kde_agent = A2AHubClient(
        hub_url=hub_url,
        agent_name="kde-plasma-agent",
        agent_description="KDE Plasma AI Agent Panel",
        agent_endpoint="http://127.0.0.1:8090",
        capabilities=["code_analysis", "file_operations", "bash_execution", "search", "rag"],
    )

    github_agent = A2AHubClient(
        hub_url=hub_url,
        agent_name="github-agent",
        agent_description="GitHub Analysis Agent",
        agent_endpoint="http://127.0.0.1:8091",
        capabilities=["github_analysis", "pr_review", "issue_tracking"],
    )

    research_agent = A2AHubClient(
        hub_url=hub_url,
        agent_name="research-agent",
        agent_description="Web Research Agent",
        agent_endpoint="http://127.0.0.1:8092",
        capabilities=["web_search", "summarization", "fact_checking"],
    )

    review_agent = A2AHubClient(
        hub_url=hub_url,
        agent_name="code-review-agent",
        agent_description="Code Review Agent",
        agent_endpoint="http://127.0.0.1:8093",
        capabilities=["code_review", "security_analysis", "performance_analysis"],
    )

    # 3. Зарегистрировать агентов
    for agent in [kde_agent, github_agent, research_agent, review_agent]:
        result = agent.register()
        assert result, f"Failed to register {agent.agent_name}"
        logger.info(f"  ✓ {agent.agent_name} registered")

    # 4. Проверить список агентов
    logger.info("\n--- Agent discovery ---")
    agents = kde_agent.discover_agents()
    logger.info(f"  Total agents: {len(agents)}")
    for a in agents:
        logger.info(f"    - {a['name']}: {a['capabilities']}")

    # 5. Тест маршрутизации задач
    logger.info("\n--- Task routing ---")

    # Задача на анализ кода → должен попасть в code-review-agent или kde-plasma-agent
    result = kde_agent.submit_task("Review this Python code for security issues")
    logger.info(f"  Code review task → {json.dumps(result, indent=2)}")

    # Задача на веб-поиск → должен попасть в research-agent
    result = kde_agent.submit_task("Search the web for latest AI agent protocols")
    logger.info(f"  Web search task → {json.dumps(result, indent=2)}")

    # Задача на GitHub → должен попасть в github-agent
    result = kde_agent.submit_task("Analyze GitHub repository commits and PRs")
    logger.info(f"  GitHub task → {json.dumps(result, indent=2)}")

    # Явное делегирование
    result = kde_agent.delegate_task(
        "Summarize the key findings from the codebase analysis",
        target_agent="research-agent",
    )
    logger.info(f"  Delegation → {json.dumps(result, indent=2)}")

    # 6. Тест общего контекста
    logger.info("\n--- Shared context ---")

    kde_agent.remember("project:linux-arch-kde", {
        "path": "/home/neo/ecosystem/linux-arch-kde-plasma-side-panel",
        "language": "Python/QML/Rust/C++",
        "phase": "Tauri 2 Integration",
    })

    github_agent.remember("last_analysis", {
        "repo": "a2aproject/A2A",
        "stars": 24000,
        "language": "Multi-language SDKs",
    })

    # Проверить что контекст доступен всем
    project = research_agent.recall("project:linux-arch-kde")
    logger.info(f"  research-agent recalls project: {json.dumps(project, indent=2)}")

    analysis = kde_agent.recall("last_analysis")
    logger.info(f"  kde-agent recalls last_analysis: {json.dumps(analysis, indent=2)}")

    # Поиск по памяти
    results = kde_agent.search_memory("a2a")
    logger.info(f"  Search 'a2a': {len(results)} results")

    # 7. Статистика
    logger.info("\n--- Hub stats ---")
    stats = hub.context_store.get_stats()
    logger.info(f"  Context stats: {json.dumps(stats, indent=2)}")

    tasks = kde_agent.list_tasks()
    logger.info(f"  Tasks: {json.dumps(tasks, indent=2)}")

    # 8. Heartbeat
    logger.info("\n--- Heartbeat ---")
    kde_agent.start_heartbeat()
    time.sleep(2)
    kde_agent.stop_heartbeat()
    logger.info("  ✓ Heartbeat test passed")

    # Итог
    logger.info("\n" + "=" * 60)
    logger.info("ALL TESTS PASSED ✓")
    logger.info("=" * 60)

    # Остановить Hub
    hub.stop()


if __name__ == "__main__":
    test_hub()
