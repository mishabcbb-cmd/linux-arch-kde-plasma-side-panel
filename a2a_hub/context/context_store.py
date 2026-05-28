"""A2A Hub — общее хранилище контекста для агентов.

Позволяет агентам делиться информацией:
- Файлы рабочего пространства
- Память (facts, observations)
- Результаты задач
- Метаданные проектов
"""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ContextStore:
    """Общее хранилище контекста для всех агентов."""

    def __init__(self, store_path: str):
        self._store_path = Path(store_path).expanduser()
        self._store_path.mkdir(parents=True, exist_ok=True)
        self._memory: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._dirty = False
        self._autosave_interval = 10  # секунд

        # Поддиректории
        (self._store_path / "files").mkdir(exist_ok=True)
        (self._store_path / "memory").mkdir(exist_ok=True)
        (self._store_path / "tasks").mkdir(exist_ok=True)
        (self._store_path / "projects").mkdir(exist_ok=True)

        # Загрузить существующий контекст
        self._load()

    def _load(self) -> None:
        """Загрузить контекст с диска."""
        memory_file = self._store_path / "memory" / "shared.json"
        if memory_file.exists():
            try:
                with open(memory_file) as f:
                    self._memory = json.load(f)
                logger.info(f"Loaded context: {len(self._memory)} entries")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load context: {e}")
                self._memory = {}

    def save(self) -> None:
        """Сохранить контекст на диск."""
        with self._lock:
            memory_file = self._store_path / "memory" / "shared.json"
            try:
                with open(memory_file, "w") as f:
                    json.dump(self._memory, f, indent=2, ensure_ascii=False, default=str)
                self._dirty = False
            except IOError as e:
                logger.error(f"Failed to save context: {e}")

    # --- Memory API ---

    def remember(self, key: str, value: Any, agent: str = "system") -> None:
        """Сохранить факт в общую память."""
        with self._lock:
            self._memory[key] = {
                "value": value,
                "agent": agent,
                "timestamp": datetime.now().isoformat(),
            }
            self._dirty = True
        logger.debug(f"Context: {agent} → remember('{key}')")

    def recall(self, key: str) -> Optional[Any]:
        """Получить факт из общей памяти."""
        entry = self._memory.get(key)
        if entry:
            return entry["value"]
        return None

    def search_memory(self, query: str) -> List[Dict[str, Any]]:
        """Поиск по ключевым словам в памяти."""
        results = []
        query_lower = query.lower()
        for key, entry in self._memory.items():
            if query_lower in key.lower() or query_lower in str(entry["value"]).lower():
                results.append({"key": key, **entry})
        return results

    def get_all_memory(self) -> Dict[str, Any]:
        """Получить всю память."""
        return dict(self._memory)

    def forget(self, key: str) -> bool:
        """Удалить факт из памяти."""
        with self._lock:
            if key in self._memory:
                del self._memory[key]
                self._dirty = True
                return True
            return False

    # --- Files API ---

    def save_file(self, filename: str, content: str, agent: str = "system") -> str:
        """Сохранить файл в общее рабочее пространство."""
        file_path = self._store_path / "files" / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        self.remember(f"file:{filename}", {"path": str(file_path), "agent": agent}, agent)
        logger.info(f"File saved: {filename} by {agent}")
        return str(file_path)

    def read_file(self, filename: str) -> Optional[str]:
        """Прочитать файл из общего рабочего пространства."""
        file_path = self._store_path / "files" / filename
        if file_path.exists():
            with open(file_path) as f:
                return f.read()
        return None

    def list_files(self) -> List[str]:
        """Список файлов в рабочем пространстве."""
        files_dir = self._store_path / "files"
        if files_dir.exists():
            return [str(p.relative_to(files_dir)) for p in files_dir.rglob("*") if p.is_file()]
        return []

    # --- Tasks API ---

    def save_task_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """Сохранить результат задачи."""
        task_file = self._store_path / "tasks" / f"{task_id}.json"
        result["saved_at"] = datetime.now().isoformat()
        with open(task_file, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получить результат задачи."""
        task_file = self._store_path / "tasks" / f"{task_id}.json"
        if task_file.exists():
            with open(task_file) as f:
                return json.load(f)
        return None

    def list_tasks(self) -> List[Dict[str, Any]]:
        """Список всех сохранённых задач."""
        tasks_dir = self._store_path / "tasks"
        tasks = []
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("*.json"):
                with open(task_file) as f:
                    tasks.append(json.load(f))
        return tasks

    # --- Projects API ---

    def set_project(self, project_name: str, metadata: Dict[str, Any]) -> None:
        """Сохранить метаданные проекта."""
        project_file = self._store_path / "projects" / f"{project_name}.json"
        metadata["updated_at"] = datetime.now().isoformat()
        with open(project_file, "w") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def get_project(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Получить метаданные проекта."""
        project_file = self._store_path / "projects" / f"{project_name}.json"
        if project_file.exists():
            with open(project_file) as f:
                return json.load(f)
        return None

    def list_projects(self) -> List[str]:
        """Список проектов."""
        projects_dir = self._store_path / "projects"
        if projects_dir.exists():
            return [p.stem for p in projects_dir.glob("*.json")]
        return []

    # --- Conversation Log API ---

    def add_conversation_message(self, task_id: str, role: str, content: str, agent: str = "", metadata: Optional[Dict] = None) -> None:
        """Добавить сообщение в лог переписки."""
        with self._lock:
            conv_key = f"conversation:{task_id}"
            if conv_key not in self._memory:
                self._memory[conv_key] = {
                    "task_id": task_id,
                    "messages": [],
                    "created_at": datetime.now().isoformat(),
                }
            msg = {
                "role": role,  # "user", "assistant", "system"
                "content": content[:2000],  # limit message size
                "agent": agent,
                "timestamp": datetime.now().isoformat(),
            }
            if metadata:
                msg["metadata"] = metadata
            self._memory[conv_key]["messages"].append(msg)
            self._memory[conv_key]["updated_at"] = datetime.now().isoformat()
            self._dirty = True
        logger.debug(f"Conversation {task_id}: {role} [{agent}] → {content[:50]}...")

    def get_conversation(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Получить полный лог переписки для задачи."""
        conv_key = f"conversation:{task_id}"
        return self._memory.get(conv_key)

    def list_conversations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Список всех разговоров (последние first)."""
        conversations = []
        for key, entry in self._memory.items():
            if key.startswith("conversation:"):
                conversations.append(entry)
        # Sort by updated_at descending
        conversations.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return conversations[:limit]

    def get_conversation_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Краткая сводка разговора (для списка)."""
        conv = self.get_conversation(task_id)
        if not conv:
            return None
        messages = conv.get("messages", [])
        user_msgs = [m for m in messages if m["role"] == "user"]
        agent_msgs = [m for m in messages if m["role"] == "assistant"]
        return {
            "task_id": task_id,
            "total_messages": len(messages),
            "user_messages": len(user_msgs),
            "agent_messages": len(agent_msgs),
            "agents_involved": list(set(m.get("agent", "") for m in agent_msgs)),
            "created_at": conv.get("created_at"),
            "updated_at": conv.get("updated_at"),
            "last_message": messages[-1] if messages else None,
        }

    # --- Stats ---

    def get_stats(self) -> Dict[str, Any]:
        """Статистика хранилища."""
        return {
            "memory_entries": len(self._memory),
            "files": len(self.list_files()),
            "tasks": len(self.list_tasks()),
            "projects": len(self.list_projects()),
            "conversations": len([k for k in self._memory if k.startswith("conversation:")]),
            "store_path": str(self._store_path),
        }
