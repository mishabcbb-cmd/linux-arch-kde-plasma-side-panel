# A2A Hub — Agent-to-Agent Orchestration Server

Центральный оркестратор для AI-агентов. Позволяет агентам регистрироваться,
находить друг друга, делегировать задачи и делиться контекстом.

## Архитектура

```
┌─────────────────────────────────────────────────┐
│                  A2A Hub Server                  │
│  ┌──────────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Agent Registry│  │  Router  │  │  Context  │  │
│  │              │  │          │  │   Store   │  │
│  └──────────────┘  └──────────┘  └───────────┘  │
│                                                  │
│  HTTP API: http://127.0.0.1:9000                 │
└──────────┬──────────┬──────────┬─────────────────┘
           │          │          │
     ┌─────▼──┐ ┌─────▼──┐ ┌────▼─────┐
     │  KDE   │ │ GitHub │ │ Research │
     │ Agent  │ │ Agent  │ │  Agent   │
     └────────┘ └────────┘ └──────────┘
```

## Быстрый старт

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить Hub
python run.py

# Или с указанием конфигурации
python run.py --config config/agents.yaml --port 9000 -v

# Запустить тест
python test_hub.py
```

## Установка как systemd service

```bash
# Копировать service файл
sudo cp systemd/a2a-hub.service /etc/systemd/system/a2a-hub@.service

# Включить и запустить (замени $USER на имя пользователя)
sudo systemctl enable a2a-hub@$USER
sudo systemctl start a2a-hub@$USER

# Проверить статус
sudo systemctl status a2a-hub@$USER
journalctl -u a2a-hub@$USER -f
```

## API Endpoints

### Агенты

| Method | Path | Description |
|--------|------|-------------|
| GET | `/agents` | Список всех агентов |
| GET | `/agents/active` | Только активные агенты |
| GET | `/agents/{name}` | Информация об агенте |
| POST | `/agents/register` | Регистрация агента |
| POST | `/agents/heartbeat` | Heartbeat |
| DELETE | `/agents/{name}` | Удаление агента |

### Задачи

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tasks` | Список задач |
| GET | `/tasks/{id}` | Статус задачи |
| POST | `/tasks/submit` | Отправить задачу (авто-маршрутизация) |
| POST | `/tasks/delegate` | Делегировать задачу конкретному агенту |

### Контекст

| Method | Path | Description |
|--------|------|-------------|
| GET | `/context` | Вся общая память |
| GET | `/context/files` | Файлы рабочего пространства |
| GET | `/context/tasks` | Сохранённые задачи |
| GET | `/context/projects` | Проекты |
| GET | `/context/stats` | Статистика |
| POST | `/context/remember` | Сохранить факт |
| POST | `/context/recall` | Получить факт |

## Использование из кода

```python
from client.hub_client import A2AHubClient

# Подключиться к Hub
client = A2AHubClient(
    hub_url="http://127.0.0.1:9000",
    agent_name="my-agent",
    agent_description="My AI Agent",
    agent_endpoint="http://127.0.0.1:8080",
    capabilities=["code_analysis", "search"],
)

# Зарегистрироваться
client.register()

# Запустить heartbeat
client.start_heartbeat()

# Отправить задачу (авто-маршрутизация)
result = client.submit_task("Analyze this code for bugs")
print(result)  # {"task_id": "abc123", "routed_to": "code-review-agent", ...}

# Делегировать конкретному агенту
result = client.delegate_task(
    "Summarize the findings",
    target_agent="research-agent",
)

# Работа с общим контекстом
client.remember("project:status", {"phase": "testing", "progress": 75})
status = client.recall("project:status")

# Найти агента по capability
agent = client.find_agent("web_search")
if agent:
    print(f"Found: {agent['name']} at {agent['endpoint']}")
```

## Конфигурация

Агенты настраиваются в [`config/agents.yaml`](config/agents.yaml):

```yaml
agents:
  - name: "my-agent"
    description: "Description"
    role: "local"  # local или api
    endpoint: "http://127.0.0.1:8080"
    capabilities:
      - "code_analysis"
      - "search"
    auth_type: "none"
    status: "active"
```

## Маршрутизация

Hub автоматически маршрутизирует задачи на основе:
1. **Явного указания** — `target_agent` в запросе
2. **Capability matching** — по ключевым словам в тексте задачи
3. **Стратегии** — `capability_based` (по умолчанию)

## Conversation Log

Полный лог переписки между пользователем и агентами:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/conversations` | Список всех разговоров |
| GET | `/conversations/{task_id}` | Полный лог переписки |
| POST | `/conversations/message` | Добавить сообщение |

Каждое сообщение содержит: `role` (user/assistant), `content`, `agent`, `timestamp`, `metadata`.

## D-Bus интеграция

D-Bus сервис: `org.kde.a2ahub` на сессионной шине.

**Методы:**
- `GetStatus()` → JSON статуса Hub
- `GetAgents()` → список агентов
- `GetConversations()` → список разговоров
- `GetConversation(task_id)` → полный лог
- `SendMessage(task_id, message)` → отправить сообщение
- `DelegateTask(task_json)` → делегировать задачу

**Сигналы:**
- `ConversationUpdated(task_id, message_count)`
- `NewMessage(task_id, role, content, agent)`
- `AgentStatusChanged(agent_name, status)`

## KDE Plasma Side Panel интеграция

A2A Chat интегрирован в боковую панель KDE Plasma через:
- `A2AChatView.qml` — QML компонент для отображения conversation log
- `dbus_listener.py` — слушатель D-Bus сигналов для QML
- TabBar в SidePanelWindow.qml для переключения между Agent и A2A Hub

**Запуск D-Bus сервиса:**
```bash
python a2a_hub_dbus.py --hub-url http://127.0.0.1:9000
```

**Запуск D-Bus listener:**
```bash
python dbus_listener.py
```
