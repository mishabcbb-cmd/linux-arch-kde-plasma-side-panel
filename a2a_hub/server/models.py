"""A2A Hub — модели данных."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentRole(str, Enum):
    LOCAL = "local"
    API = "api"


class AgentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BUSY = "busy"
    ERROR = "error"


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    INPUT_REQUIRED = "input-required"


@dataclass
class AgentInfo:
    """Информация о зарегистрированном агенте."""
    name: str
    description: str
    role: AgentRole
    endpoint: str
    agent_card_url: str
    capabilities: List[str] = field(default_factory=list)
    auth_type: str = "none"
    status: AgentStatus = AgentStatus.ACTIVE
    last_seen: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "role": self.role.value,
            "endpoint": self.endpoint,
            "agent_card_url": self.agent_card_url,
            "capabilities": self.capabilities,
            "auth_type": self.auth_type,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "metadata": self.metadata,
        }


@dataclass
class HubConfig:
    """Конфигурация A2A Hub."""
    host: str = "127.0.0.1"
    port: int = 9000
    workspace: str = "~/.local/share/a2a_hub/workspace"
    context_store: str = "~/.local/share/a2a_hub/context"
    log_level: str = "info"
    max_hops: int = 3
    agent_timeout: int = 120
    routing_strategy: str = "capability_based"


@dataclass
class TaskRoute:
    """Маршрут задачи — кто должен выполнить."""
    task_id: str
    source_agent: str
    target_agent: str
    task_text: str
    context: Dict[str, Any] = field(default_factory=dict)
    state: TaskState = TaskState.SUBMITTED
    created_at: datetime = field(default_factory=datetime.now)
    result: Optional[str] = None
    error: Optional[str] = None


@dataclass
class HubTask:
    """Задача в Hub — полный жизненный цикл."""
    task_id: str
    text: str
    context: Dict[str, Any] = field(default_factory=dict)
    routes: List[TaskRoute] = field(default_factory=list)
    state: TaskState = TaskState.SUBMITTED
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
