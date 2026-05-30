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
└──────────┬──────────┬──────────┬──────────┬──────┘
           │          │          │          │
     ┌─────▼──┐ ┌─────▼──┐ ┌────▼────┐ ┌───▼──────┐
     │  OWL   │ │  OWL   │ │  OWL    │ │  Qwen    │
     │ Coder  │ │Research│ │Commander│ │ Reviewer │
     │ :8091  │ │ :8092  │ │  :8094  │ │  :8093   │
     └────────┘ └────────┘ └─────────┘ └──────────┘
```

## Команда агентов

| # | Агент | Порт | Провайдер | Модель | Capabilities | Env Key |
|---|-------|------|-----------|--------|-------------|---------|
| 1 | **owl-coder** | 8091 | OpenRouter | openrouter/owl-alpha | code_analysis, code_generation, debugging, refactoring, architecture, complex_reasoning | `OPENROUTER_API_KEY_1` |
| 2 | **owl-researcher** | 8092 | OpenRouter | openrouter/owl-alpha | web_search, summarization, fact_checking, research, documentation | `OPENROUTER_API_KEY_2` |
| 3 | **owl-commander** | 8094 | OpenRouter | openrouter/owl-alpha | orchestration, task_decomposition, coordination, planning, delegation | `OPENROUTER_API_KEY_3` |
| 4 | **qwen-reviewer** | 8093 | llama.cpp | Qwen3.6-35B-A3B-wasserstein.IQ3_M | quick_tasks, simple_review, formatting, linting | `LLAMA_HOST` (default: `http://127.0.0.1:8085`) |

## Структура файлов

```
a2a_hub/
├── run.py                      # Точка входа для запуска Hub сервера
├── requirements.txt            # Python зависимости (pyyaml, httpx)
├── README.md                   # Этот файл
├── config/
│   └── agents.yaml             # Конфигурация всех агентов
├── server/
│   ├── hub_server.py           # HTTP сервер + API (15+ endpoints)
│   ├── models.py               # Модели данных (AgentInfo, HubTask, etc.)
│   └── router.py               # Маршрутизатор задач по capabilities
├── registry/
│   └── agent_registry.py       # Реестр агентов + heartbeat мониторинг
├── context/
│   └── context_store.py        # Общий контекст + conversation log
├── client/
│   └── hub_client.py           # Python SDK для агентов
├── llm_agent/
│   ├── agent_server.py         # A2A Server wrapper для LLM провайдеров
│   ├── start_agents.sh         # Скрипт запуска всех 4 агентов
│   └── stop_agents.sh          # Скрипт остановки всех агентов
├── mcp_server/
│   ├── server.py               # MCP Server (7 tools для Roo/VS Code)
│   └── __main__.py             # Точка входа MCP сервера
├── systemd/
│   ├── a2a-hub.service         # systemd service для Hub
│   └── a2a-agents.service      # systemd service для агентов
├── a2a_hub_dbus.py             # D-Bus сервис (org.kde.a2ahub)
├── dbus_listener.py            # D-Bus listener для QML интеграции
├── orchestrator.py             # Мульти-агентный оркестратор
└── test_hub.py                 # Тест Hub сервера
```

## Быстрый старт

### 1. Установить зависимости

```bash
cd /home/neo/ecosystem/linux-arch-kde-plasma-side-panel/a2a_hub
pip install -r requirements.txt
```

### 2. Запустить Hub

```bash
# Минимальный запуск
python run.py

# С указанием конфигурации и порта
python run.py --config config/agents.yaml --port 9000 -v

# Проверить что Hub работает
curl http://127.0.0.1:9000/health
```

### 3. Запустить агентов

```bash
export OPENROUTER_API_KEY_1="sk-or-v1-..."
export OPENROUTER_API_KEY_2="sk-or-v1-..."
export OPENROUTER_API_KEY_3="sk-or-v1-..."
./llm_agent/start_agents.sh
```

Скрипт проверяет наличие всех ключей, проверяет llama.cpp, запускает Hub (если ещё не запущен), затем запускает всех 4 агентов.

### 4. Остановить агентов

```bash
./llm_agent/stop_agents.sh
```

### 5. Проверить статус

```bash
# Список всех агентов
curl http://127.0.0.1:9000/agents

# Активные агенты
curl http://127.0.0.1:9000/agents/active

# Конкретный агент
curl http://127.0.0.1:9000/agents/owl-coder
```

## Установка как systemd service

```bash
# Копировать service файлы
sudo cp systemd/a2a-hub.service /etc/systemd/system/a2a-hub@.service
sudo cp systemd/a2a-agents.service /etc/systemd/system/a2a-agents@.service

# Включить и запустить Hub
sudo systemctl enable a2a-hub@$USER
sudo systemctl start a2a-hub@$USER

# Включить и запустить агентов (после Hub)
sudo systemctl enable a2a-agents@$USER
sudo systemctl start a2a-agents@$USER

# Проверить статус
sudo systemctl status a2a-hub@$USER
sudo systemctl status a2a-agents@$USER
journalctl -u a2a-hub@$USER -f
```

**Примечание:** В `a2a-agents.service` захардкожены API ключи. Для production используйте EnvironmentFile или другой безопасный способ хранения ключей.

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|-------------|
| `OPENROUTER_API_KEY_1` | API ключ для owl-coder | — |
| `OPENROUTER_API_KEY_2` | API ключ для owl-researcher | — |
| `OPENROUTER_API_KEY_3` | API ключ для owl-commander | — |
| `LLAMA_HOST` | Адрес llama.cpp сервера | `http://127.0.0.1:8085` |

## API Endpoints

### Агенты

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Статус Hub + список агентов |
| GET | `/health` | Health check |
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

### Conversation Log

| Method | Path | Description |
|--------|------|-------------|
| GET | `/conversations` | Список всех разговоров |
| GET | `/conversations/{task_id}` | Полный лог переписки |
| POST | `/conversations/message` | Добавить сообщение |

## Конфигурация агентов (agents.yaml)

Агенты настраиваются в [`config/agents.yaml`](config/agents.yaml). При запуске Hub автоматически загружает всех агентов из конфигурации в реестр.

```yaml
agents:
  - name: "owl-coder"
    description: "OWL Coder — сложные задачи: архитектура, код, отладка"
    role: "api"           # local или api
    endpoint: "http://127.0.0.1:8091"
    capabilities:
      - "code_analysis"
      - "code_generation"
    auth_type: "none"
    status: "active"       # active или inactive
```

**Добавление нового агента:**
1. Добавить запись в `config/agents.yaml`
2. Добавить запуск в `llm_agent/start_agents.sh`
3. Добавить порт в `llm_agent/stop_agents.sh`
4. Перезапустить Hub и агентов

## Маршрутизация

Hub автоматически маршрутизирует задачи на основе:
1. **Явного указания** — `target_agent` в запросе
2. **Capability matching** — по ключевым словам в тексте задачи
3. **Стратегии** — `capability_based` (по умолчанию)

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
client.start_heartbeat()

# Отправить задачу (авто-маршрутизация)
result = client.submit_task("Analyze this code for bugs")

# Делегировать конкретному агенту
result = client.delegate_task(
    "Summarize the findings",
    target_agent="owl-researcher",
)

# Работа с общим контекстом
client.remember("project:status", {"phase": "testing", "progress": 75})
status = client.recall("project:status")

# Найти агента по capability
agent = client.find_agent("web_search")
```

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

**Запуск D-Bus сервиса:**
```bash
python a2a_hub_dbus.py --hub-url http://127.0.0.1:9000
```

**Запуск D-Bus listener:**
```bash
python dbus_listener.py
```

## KDE Plasma Side Panel интеграция

A2A Chat интегрирован в боковую панель KDE Plasma через:
- `A2AChatView.qml` — QML компонент для отображения conversation log
- `dbus_listener.py` — слушатель D-Bus сигналов для QML
- TabBar в SidePanelWindow.qml для переключения между Agent и A2A Hub

## GUI Configurator

Простой графический конфигуратор на PyQt6 для управления агентами и сервисами.

**Запуск:**
```bash
python3 a2a_hub/configurator.py
```

Или из меню приложений: **A2A Hub Configurator**.

**Возможности:**
- Просмотр / добавление / редактирование / удаление агентов
- Настройка API ключей, портов, capabilities, моделей, провайдеров
- Запуск / остановка / перезапуск Hub и агентов
- Включение / отключение автозапуска (systemd)
- Просмотр логов сервисов (journalctl)
- Авто-обновление статуса каждые 5 секунд
- Контекстное меню на таблице агентов

## Roo Code интеграция (OpenAI-Compatible API)

A2A Hub предоставляет OpenAI-compatible endpoint для интеграции с Roo Code и другими AI-клиентами.

### Подключение к Roo Code

В `settings.json` Roo Code добавить кастомного провайдера:

```json
{
  "models": [
    {
      "provider": "openai-compatible",
      "baseUrl": "http://127.0.0.1:9000/v1",
      "apiKey": "not-needed",
      "model": "owl-coder",
      "name": "OWL Coder"
    },
    {
      "provider": "openai-compatible",
      "baseUrl": "http://127.0.0.1:9000/v1",
      "apiKey": "not-needed",
      "model": "owl-researcher",
      "name": "OWL Researcher"
    },
    {
      "provider": "openai-compatible",
      "baseUrl": "http://127.0.0.1:9000/v1",
      "apiKey": "not-needed",
      "model": "owl-commander",
      "name": "OWL Commander"
    },
    {
      "provider": "openai-compatible",
      "baseUrl": "http://127.0.0.1:9000/v1",
      "apiKey": "not-needed",
      "model": "qwen-reviewer",
      "name": "Qwen Reviewer"
    }
  ]
}
```

### Как это работает

```
Roo Code → /v1/chat/completions → A2A Hub → Агент (owl-coder, owl-researcher, ...)
                ↑                                         ↓
           OpenAI-формат                           Ответ в OpenAI-формате
```

1. **Ты выбираешь модель** (агента) в Roo Code
2. **Hub маршрутизирует** запрос нужному агенту по имени модели
3. **Агент может делегировать** задачи другим агентам через Hub
4. **Результат возвращается** в формате OpenAI chat completion

### Сценарии использования

**Прямой выбор агента:**
- Выбираешь "OWL Coder" → пишешь код
- Выбираешь "OWL Researcher" → исследуешь
- Выбираешь "OWL Commander" → оркестрируешь

**Оркестрация через командира:**
- Выбираешь "OWL Commander" → пишешь сложную задачу
- Commander автоматически декомпозирует и делегирует:
  - Код → OWL Coder
  - Исследование → OWL Researcher
  - Ревью → Qwen Reviewer
- Результат объединяется и возвращается тебе

### API Endpoints

| Endpoint | Описание |
|----------|----------|
| `GET /v1/models` | Список доступных моделей (агентов) |
| `POST /v1/chat/completions` | Chat completions (streaming + non-streaming) |
| `GET /health` | Health check |

### Проверка работы

```bash
# Список моделей
curl http://127.0.0.1:9000/v1/models

# Тестовый запрос
curl -X POST http://127.0.0.1:9000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"owl-coder","messages":[{"role":"user","content":"Hello"}]}'
```

## MCP Server

MCP Server предоставляет 7 инструментов для интеграции с Roo/VS Code:

- `list_agents` — список всех агентов
- `delegate_task` — делегировать задачу агенту
- `get_agent_card` — получить карточку агента
- `get_shared_context` — получить общий контекст
- `remember` — сохранить факт
- `recall` — получить факт
- `get_task_history` — история задач

**Запуск:**
```bash
python -m a2a_hub.mcp_server --transport stdio
```

## Логи

- Hub: `journalctl -u a2a-hub@$USER -f`
- Агенты: `journalctl -u a2a-agents@$USER -f`
- Ручной запуск: `/tmp/owl-coder.log`, `/tmp/owl-researcher.log`, `/tmp/owl-commander.log`, `/tmp/qwen-reviewer.log`
