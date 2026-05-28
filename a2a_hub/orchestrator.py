#!/usr/bin/env python3
"""A2A Hub Orchestrator — координирует работу нескольких агентов.

Принимает задачу от пользователя, разбивает на подзадачи,
делегирует агентам через Hub, собирает результаты.

Использование:
    python orchestrator.py "Review the code in src/ and find security issues"
    python orchestrator.py --interactive
"""

import argparse
import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("orchestrator")


class MultiAgentOrchestrator:
    """Оркестратор — разбивает задачи и делегирует агентам через A2A Hub."""

    def __init__(self, hub_url: str = "http://127.0.0.1:9000"):
        self.hub_url = hub_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            from a2a_hub.client.hub_client import A2AHubClient
            self._client = A2AHubClient(
                hub_url=self.hub_url,
                agent_name="orchestrator",
                agent_description="Multi-Agent Orchestrator",
                agent_endpoint="",
                capabilities=["orchestration"],
            )
            self._client.register()
        return self._client

    def discover_agents(self) -> List[Dict]:
        """Получить список всех агентов из Hub."""
        client = self._get_client()
        return client.discover_agents()

    def delegate_to_agent(self, agent_name: str, task: str, context: Optional[Dict] = None) -> Dict:
        """Делегировать задачу конкретному агенту."""
        client = self._get_client()

        # Получить endpoint агента
        agent = None
        for a in client.discover_agents():
            if a["name"] == agent_name:
                agent = a
                break

        if not agent:
            return {"error": f"Agent '{agent_name}' not found"}

        # Отправить задачу напрямую агенту
        import httpx
        try:
            resp = httpx.post(
                f"{agent['endpoint']}/tasks/execute",
                json={"text": task, "context": context or {}},
                timeout=120,
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def orchestrate(self, task: str) -> Dict:
        """Оркестрировать задачу — разбить и делегировать."""
        logger.info(f"Orchestrating task: {task}")

        agents = self.discover_agents()
        active = [a for a in agents if a.get("status") == "active"]
        logger.info(f"Active agents: {[a['name'] for a in active]}")

        results = {}

        # Определить какие агенты нужны
        task_lower = task.lower()

        # Анализ кода → owl-coder
        if any(kw in task_lower for kw in ["code", "write", "create", "implement", "refactor", "debug"]):
            logger.info("→ Delegating to owl-coder")
            result = self.delegate_to_agent("owl-coder", task)
            results["owl-coder"] = result

        # Исследование → owl-researcher
        if any(kw in task_lower for kw in ["research", "search", "find", "summarize", "explain"]):
            logger.info("→ Delegating to owl-researcher")
            result = self.delegate_to_agent("owl-researcher", task)
            results["owl-researcher"] = result

        # Ревью/безопасность → qwen-reviewer
        if any(kw in task_lower for kw in ["review", "security", "vulnerability", "check", "analyze"]):
            logger.info("→ Delegating to qwen-reviewer")
            result = self.delegate_to_agent("qwen-reviewer", task)
            results["qwen-reviewer"] = result

        # Если не определили — отправить всем
        if not results:
            logger.info("→ No specific match, sending to all agents")
            for agent in active:
                result = self.delegate_to_agent(agent["name"], task)
                results[agent["name"]] = result

        # Сохранить результаты в Hub context
        client = self._get_client()
        client.remember(f"orchestration:{hash(task) % 10000}", {
            "task": task,
            "results": {k: v.get("response", v.get("error", "no response"))[:200] for k, v in results.items()},
            "agents_used": list(results.keys()),
        })

        return {
            "task": task,
            "agents_used": list(results.keys()),
            "results": results,
        }

    def interactive(self):
        """Интерактивный режим — чат с оркестратором."""
        print("╔══════════════════════════════════════════╗")
        print("║     A2A Multi-Agent Orchestrator         ║")
        print(f"║  Hub: {self.hub_url:<33}║")
        print("╚══════════════════════════════════════════╝")
        print()
        print("Commands:")
        print("  /agents — list all agents")
        print("  /status — Hub status")
        print("  /quit   — exit")
        print()

        while True:
            try:
                task = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            if not task:
                continue

            if task == "/quit":
                break
            elif task == "/agents":
                agents = self.discover_agents()
                for a in agents:
                    status = "🟢" if a.get("status") == "active" else "🔴"
                    print(f"  {status} {a['name']}: {a.get('description', '')[:60]}")
                    print(f"     caps: {', '.join(a.get('capabilities', []))}")
                continue
            elif task == "/status":
                import httpx
                try:
                    resp = httpx.get(f"{self.hub_url}/")
                    print(json.dumps(resp.json(), indent=2))
                except Exception as e:
                    print(f"Hub unavailable: {e}")
                continue

            print("\nOrchestrating...")
            result = self.orchestrate(task)

            print(f"\nAgents used: {', '.join(result['agents_used'])}")
            for agent_name, agent_result in result["results"].items():
                response = agent_result.get("response", agent_result.get("error", "No response"))
                print(f"\n{'='*50}")
                print(f"📡 {agent_name}:")
                print(f"{'='*50}")
                print(response)
            print()


def main():
    parser = argparse.ArgumentParser(description="A2A Multi-Agent Orchestrator")
    parser.add_argument("task", nargs="?", help="Task to orchestrate")
    parser.add_argument("--hub-url", default="http://127.0.0.1:9000")
    parser.add_argument("--interactive", "-i", action="store_true")
    parser.add_argument("--list-agents", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    orch = MultiAgentOrchestrator(hub_url=args.hub_url)

    if args.list_agents:
        agents = orch.discover_agents()
        print(json.dumps(agents, indent=2))
    elif args.interactive:
        orch.interactive()
    elif args.task:
        result = orch.orchestrate(args.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
