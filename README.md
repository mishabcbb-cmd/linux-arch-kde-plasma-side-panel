# KDE AI Agent Panel

> **AI coding agent, интегрированный в панель KDE Plasma 6.**  
> Общайтесь с Claude, Ollama, OpenRouter или OpenAI-совместимыми моделями — читайте, пишите, ищите и тестируйте код прямо с рабочего стола.

[![Status](https://img.shields.io/badge/status-stable-green)](https://github.com/kde-ai-agent/kde-ai-agent)
[![KDE Plasma](https://img.shields.io/badge/KDE%20Plasma-6-blue)](https://kde.org/plasma-desktop/)
[![Tauri](https://img.shields.io/badge/Tauri-2-black)](https://tauri.app/)
[![React](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)
[![Rust](https://img.shields.io/badge/Rust-1.95-orange)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Python-3.14-green)](https://www.python.org/)
[![GCC](https://img.shields.io/badge/GCC-16-orange)](https://gcc.gnu.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-86%20passed-brightgreen)](tests/)
[![MCP](https://img.shields.io/badge/MCP-ready-purple)](https://modelcontextprotocol.io/)
[![A2A](https://img.shields.io/badge/A2A%20Hub-active-ff6b6b)](a2a_hub/)

---

## 📋 Содержание

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Возможности](#возможности)
- [Инструменты](#инструменты)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Использование](#использование)
- [Разработка](#разработка)
- [Docker](#docker)
- [MCP Интеграция](#mcp-интеграция)
- [Лицензия](#лицензия)
- [Благодарности](#благодарности)

---

## Обзор

**KDE AI Agent Panel** — это полноценный AI-агент для разработки, встроенный прямо в панель задач KDE Plasma 6. Проект объединяет:

- **ReAct-цикл** (Reasoning + Acting) — агент думает, вызывает инструменты, анализирует результаты и итерирует
- **Мульти-провайдерность** — Anthropic Claude, локальный Ollama, OpenRouter, OpenAI-совместимые
- **MCP протокол** — интеграция с внешними MCP-серверами (lean-ctx, engram, codebase-memory, searxng)
- **RAG-движок** — ChromaDB с семантическим поиском по кодовой базе, памяти и документации
- **C++ Native слой** — GCC 16, pybind11, LTO thin, PGO для максимальной производительности
- **Кросс-репозиторный интеллект** — поиск и трассировка кода через 10+ индексированных проектов
- **Tauri 2 UI** — Messenger-style интерфейс на React 19 + TypeScript с Rust backend
- **Web UI** — FastAPI + HTMX для headless/Docker режима
- **A2A Hub** — Мульти-агентная оркестрация (4 агента: owl-coder, owl-researcher, qwen-reviewer, owl-commander)

Проект вдохновлён лучшими практиками из [Aider](https://github.com/Aider-AI/aider), [OpenCode](https://github.com/opencode-ai/opencode), [JARVIS](https://github.com/novik133/jarvis), [end4](https://github.com/end-4/dots-hyprland) и [ZooCode/Roo Code](https://github.com/RooVetGit/Roo-Code).

---

## Архитектура

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  KDE Plasma Panel (QML) / Web UI (FastAPI + HTMX)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐                        │
│  │ ChatView │ │TaskInput │ │FileTree  │ │ StatusBar │                        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘                        │
│       │            │            │              │                              │
│       └────────────┴────────────┴──────────────┘                              │
│                        │ D-Bus / subprocess                                   │
├────────────────────────┼──────────────────────────────────────────────────────┤
│                        ▼                                                      │
│  Python Agent Backend (systemd user service)                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  AgentLoop (ReAct)                                                     │   │
│  │  ┌──────────┐ ┌────────────┐ ┌──────────┐ ┌──────────────┐            │   │
│  │  │ LLM      │ │ Tool       │ │ MCP      │ │ Context      │            │   │
│  │  │ Client   │ │ Registry   │ │ Client   │ │ Manager      │            │   │
│  │  │ 4 prov.  │ │ 12 tools   │ │ dynamic  │ │ token budget │            │   │
│  │  └──────────┘ └────────────┘ └──────────┘ └──────────────┘            │   │
│  │                        │                                                │   │
│  │  ┌────────────────────────────────────────────────────────────────┐    │   │
│  │  │  RAG Engine (ChromaDB)                                         │    │   │
│  │  │  codebase · memory · docs — Ollama embeddings + fallback       │    │   │
│  │  └────────────────────────────────────────────────────────────────┘    │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                        │                                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  C++ Native Layer (GCC 16.1.1 · pybind11)                             │   │
│  │  cosine_similarity · normalize · batch_normalize · similarity_matrix   │   │
│  │  count_tokens · chunk_text                                             │   │
│  │  LTO thin · PGO · march=native · TurboQuant+ (optional)               │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                        │                                                      │
│  ┌────────────────────────────────────────────────────────────────────────┐   │
│  │  External MCP Servers                                                  │   │
│  │  lean-ctx · engram · codebase-memory · searxng                         │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Компоненты

| Слой | Технологии | Назначение |
|------|-----------|-----------|
| **UI** | QML (Plasma 6), FastAPI + HTMX | Интерфейс пользователя |
| **Транспорт** | D-Bus, Unix Socket, subprocess | Связь UI с бэкендом |
| **Агент** | Python 3.14, ReAct Loop | Логика агента |
| **LLM** | Anthropic, Ollama, OpenRouter, OpenAI | Провайдеры языковых моделей |
| **Инструменты** | 12 встроенных + MCP внешние | Выполнение действий |
| **RAG** | ChromaDB, Ollama embeddings | Семантический поиск |
| **Native** | C++23, pybind11, GCC 16 | Оптимизированные вычисления |
| **Память** | Engram, ChromaDB | Кросс-сессионная память |

---

## Возможности

### ✅ Реализовано (Phase 3)

| Возможность | Статус | Описание |
|------------|--------|----------|
| **ReAct Agent Loop** | ✅ | 50 итераций, обратная связь от инструментов |
| **Streaming Output** | ✅ | Токены → D-Bus → QML ChatView в реальном времени |
| **Multi-Provider** | ✅ | Anthropic, Ollama, OpenRouter, OpenAI-compatible |
| **12 Built-in Tools** | ✅ | bash_exec, file_read, file_write, search_codebase, repo_map, run_tests, ask_user, cross_repo_search, cross_repo_trace, system_monitor, voice_input, tts_output |
| **MCP Server** | ✅ | stdio + SSE транспорты, динамическое обнаружение инструментов |
| **MCP Client** | ✅ | Подключение внешних MCP-серверов, auto-approve |
| **RAG Engine** | ✅ | ChromaDB, 3 коллекции, Ollama embeddings, чанкование |
| **C++ Native Layer** | ✅ | CMake, GCC 16, LTO thin, PGO, llama.cpp из исходников |
| **Cross-session Memory** | ✅ | memory_store/memory_recall с тегами |
| **Auto Git Commits** | ✅ | На каждый file_write |
| **D-Bus Integration** | ✅ | 7 сигналов, 4 метода |
| **Unix Socket Fallback** | ✅ | Когда D-Bus недоступен |
| **OpenObserve** | ✅ | Структурированный стриминг событий |
| **FileTree** | ✅ | Реальный файловый браузер с breadcrumb, фильтром, multi-select |
| **Config Persistence** | ✅ | 17 настроек через KConfig XSD |
| **Web UI** | ✅ | FastAPI + HTMX для headless режима |
| **Cross-repo Intelligence** | ✅ | Поиск и трассировка через 10+ проектов |
| **System Monitoring** | ✅ | CPU, RAM, температура, диск, uptime |
| **Voice Input / TTS** | ✅ | whisper.cpp + espeak-ng |
| **CI Pipeline** | ✅ | GitHub Actions: тесты, линтинг, сборка native |
| **Docker** | ✅ | Headless/MCP SSE режим |
| **Arch Linux PKGBUILD** | ✅ | packaging/arch/PKGBUILD |

### 🔄 В разработке

| Возможность | Приоритет | Статус |
|------------|-----------|--------|
| Agentic RAG (самокорректирующийся поиск) | 📌 P1 | 📅 Планируется |
| Hybrid Search (BM25 + векторный) | 📌 P1 | 📅 Планируется |
| Re-ranking слой | 📌 P1 | 📅 Планируется |
| Multi-агентная архитектура | 🧊 P2 | 📅 Планируется |
| Плагинная система инструментов | 🧊 P2 | 📅 Планируется |
| GPU ускорение для RAG | 🧊 P2 | 📅 Планируется |

---

## Инструменты

### Встроенные (12)

| Инструмент | Описание |
|-----------|----------|
| [`bash_exec`](agent/tools.py) | Выполнение shell-команд (сборка, тесты, git, системные запросы) |
| [`file_read`](agent/tools.py) | Чтение файлов с номерами строк и листингом директорий |
| [`file_write`](agent/tools.py) | Запись/создание файлов с автоматическим git commit |
| [`search_codebase`](agent/tools.py) | Regex-поиск по проекту (ripgrep) |
| [`repo_map`](agent/tools.py) | tree-sitter структурная сводка кодовой базы |
| [`run_tests`](agent/tools.py) | Авто-определение тестового фреймворка (pytest, cargo, npm, go, ctest) |
| [`ask_user`](agent/tools.py) | Пауза и вопрос пользователю через UI |
| [`cross_repo_search`](agent/tools.py) | Поиск по 10+ индексированным проектам |
| [`cross_repo_trace`](agent/tools.py) | Трассировка вызовов через проект |
| [`system_monitor`](agent/tools.py) | CPU, память, температура, диск, uptime |
| [`voice_input`](agent/tools.py) | Запись + транскрибация через whisper.cpp |
| [`tts_output`](agent/tools.py) | Text-to-Speech через espeak-ng |

### MCP Серверы

| Сервер | Транспорт | Инструменты |
|--------|-----------|------------|
| **lean-ctx** | stdio | ctx_read, ctx_search, ctx_graph, ctx_knowledge, ctx_edit, ctx_session |
| **engram** | stdio | mem_save, mem_search, mem_context, mem_timeline, mem_session_summary |
| **codebase-memory** | stdio | search_graph, search_code, trace_path, get_code_snippet, get_architecture |
| **searxng** | stdio | searxng_web_search, web_url_read |

---

## Требования

### Системные

- **Arch Linux** (или любой дистрибутив с `pacman`/`yay`)
- **KDE Plasma 6** (для plasmoid-виджета)
- **Python 3.10+** (3.14 рекомендуется)
- **GCC 15+** (для C++ native слоя; 16.1.1 рекомендуется)
- **ripgrep** (`rg`) — для поиска по коду
- **git** — для авто-коммитов

### API Ключ (выберите один)

- **Anthropic API key** → [console.anthropic.com](https://console.anthropic.com/)
- **Ollama** (локальный, бесплатный) → `pacman -S ollama && ollama serve`
- **OpenRouter** → [openrouter.ai/keys](https://openrouter.ai/keys)

---

## Установка

### Быстрая установка

```bash
git clone https://github.com/kde-ai-agent/kde-ai-agent.git
cd kde-ai-agent/linux-arch-kde-plasma-side-panel
chmod +x install.sh
./install.sh
```

### Что делает install.sh (8 шагов)

| Шаг | Действие | Fallback |
|-----|----------|----------|
| 0 | Проверка Python 3.10+ | Выход с ошибкой |
| 1 | Установка системных пакетов (pacman) | Пропуск если нет pacman |
| 2 | Установка Python зависимостей (pip --user) | --break-system-packages |
| 3 | CMake сборка с GCC 16 флагами | Пропуск если нет CMake |
| 4 | Установка plasmoid (kpackagetool6) | Ручное копирование |
| 5 | Создание systemd user service | — |
| 6 | Создание конфига по умолчанию | — |
| 7 | Верификация установки | Предупреждение при проблемах |

### Ручная установка

```bash
# Системные пакеты
sudo pacman -S plasma-framework kirigami2 qt6-declarative \
    python-dbus python-gobject ripgrep git tree-sitter

# Python зависимости
pip install --user -r agent/requirements.txt

# C++ native слой
cmake -B build
cmake --build build -j$(nproc)

# Установка plasmoid
kpackagetool6 --install plasmoid/ai-agent-panel/

# Запуск сервиса
systemctl --user enable --now kde-ai-agent
```

---

## Конфигурация

Редактируйте `~/.config/kde-ai-agent/config.json` или используйте **QML Config UI** (правый клик по plasmoid → Configure):

```json
{
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key": "sk-ant-api03-your-key-here",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.2",
    "max_tokens": 8192,
    "max_input_tokens": 100000,
    "temperature": 0.7,
    "working_dir": "/home/you/projects/my-project",
    "openobserve_endpoint": "",
    "openobserve_stream": "ai-agent-events",
    "mcp_servers": {
        "lean-ctx": {
            "transport": "stdio",
            "command": "lean-ctx",
            "auto_approve": ["ctx_read", "ctx_search"]
        }
    }
}
```

### Конфигурация MCP Серверов

Настраивается в [`ConfigApi.qml`](plasmoid/ai-agent-panel/contents/config/ConfigApi.qml) или напрямую в `config.json`:

```json
{
  "mcp_servers": {
    "lean-ctx": {
      "transport": "stdio",
      "command": "lean-ctx",
      "auto_approve": ["ctx_read", "ctx_search"]
    },
    "engram": {
      "transport": "stdio",
      "command": "/usr/bin/engram",
      "args": ["mcp"],
      "auto_approve": ["mem_search", "mem_context"]
    },
    "codebase-memory": {
      "transport": "stdio",
      "command": "/usr/bin/codebase-memory-mcp",
      "args": ["stdio"],
      "auto_approve": ["search_graph", "search_code"]
    },
    "searxng": {
      "transport": "stdio",
      "command": "mcp-searxng",
      "auto_approve": ["searxng_web_search"]
    }
  }
}
```

---

## Использование

### Добавление на панель

1. Правый клик по панели KDE → **Add Widgets**
2. Поиск **"AI Agent Panel"**
3. Перетащите на нужное место панели

### Отправка задач

1. Введите задачу в поле ввода
2. Нажмите **Ctrl+Enter** или кнопку **Send**
3. Наблюдайте как агент думает, выполняет инструменты и стримит результаты

### Контекстные файлы

- Нажмите кнопку **File** или **Files** в статус-баре
- Выберите файлы для добавления в контекст (multi-select с чекбоксами)
- Выбранные файлы отображаются как чипы над полем ввода

### Горячие клавиши

| Клавиша | Действие |
|---------|----------|
| `Ctrl+Enter` | Отправить задачу |
| `Esc` | Очистить ввод |

### Режимы запуска

```bash
# Нормальный D-Bus режим
cd agent && python3 -m agent.main

# Как MCP stdio сервер (для IDE)
python3 -m agent.main --mcp-stdio

# Как MCP SSE сервер на порту 8765
python3 -m agent.main --mcp-sse

# Web UI (headless)
python3 -m web.app
# → http://localhost:8080
```

---

## Разработка

### Структура проекта

```
linux-arch-kde-plasma-side-panel/
├── agent/                          # Python бэкенд
│   ├── __init__.py                 # Экспорт пакета, версия 0.3.0
│   ├── main.py                     # D-Bus сервис, точка входа
│   ├── agent_loop.py               # ReAct цикл + MCP роутинг
│   ├── tools.py                    # 12 реализаций инструментов
│   ├── llm_client.py               # 5 провайдеров LLM
│   ├── context_manager.py          # Управление токен-бюджетом
│   ├── mcp_server.py               # MCP сервер (stdio + SSE)
│   ├── mcp_client.py               # MCP клиент (динамические серверы)
│   ├── rag.py                      # RAG движок (ChromaDB)
│   └── requirements.txt
├── src/                            # React frontend (Tauri)
│   ├── rag_native.h                # Заголовок: cosine, normalize, chunk
│   ├── embedding.cpp               # Быстрые операции с эмбеддингами
│   ├── tokenizer.cpp               # UTF-8 подсчёт токенов + чанкование
│   └── rag_native.cpp              # pybind11 модуль-обёртка
├── cmake/                          # CMake модули
│   ├── CompilerFlags.cmake         # GCC 16 флаги (LTO, PGO, march)
│   ├── BuildLlama.cmake.in         # Сборка TurboQuant+ форка
│   └── BuildWhisper.cmake.in       # Сборка whisper.cpp
├── tests/                          # Тесты
│   ├── conftest.py                 # MockToolRegistry + фикстуры
│   ├── test_mcp_server.py          # 13 тестов MCP сервера
│   ├── test_mcp_client.py          # 19 тестов MCP клиента
│   ├── test_rag.py                 # 24 теста RAG движка
│   └── test_tools.py               # 24 теста ToolRegistry
├── web/                            # Web UI (headless режим)
│   ├── app.py                      # FastAPI + HTMX сервер
│   └── templates/                  # Jinja2 шаблоны
├── plasmoid/ai-agent-panel/        # QML plasmoid
│   └── contents/
│       ├── ui/                     # QML компоненты
│       └── config/                 # Страницы конфигурации + main.xml
├── scripts/                        # Скрипты сборки
│   ├── pgo-generate.sh             # PGO генерация профиля
│   └── pgo-use.sh                  # PGO оптимизированная сборка
├── plans/                          # Документация и планы
│   └── plans-and-recommendations.md
├── .github/workflows/ci.yml        # CI пайплайн
├── Dockerfile                      # Docker образ
├── install.sh / uninstall.sh
├── README.md                       # Этот файл
└── PROJECT_STATE.md                # Состояние проекта
```

### Сборка Tauri 2 (React + Rust)

```bash
# Собрать фронтенд + запустить Tauri (без Vite dev server)
pnpm tauri:dev:build

# Или по шагам:
pnpm build                              # Собрать React frontend → dist/
cd src-tauri && cargo run --no-default-features   # Запустить Tauri

# Production билд
cd src-tauri && cargo tauri build
```

**Важно**: приложение загружает фронтенд из `dist/` напрямую, без Vite dev server и без localhost.

### Сборка C++ Native слоя

```bash
# Стандартная сборка (GCC 16)
cmake -B build
cmake --build build -j$(nproc)

# С TurboQuant+ (llama.cpp форк)
cmake -B build -DBUILD_LLAMA=ON
cmake --build build -j$(nproc)

# PGO оптимизированная сборка
./scripts/pgo-generate.sh   # Шаг 1: генерация профиля
./scripts/pgo-use.sh        # Шаг 2: использование профиля

# Отладка с санитайзерами
cmake -B build -DCMAKE_BUILD_TYPE=Debug -DENABLE_SANITIZERS=ON
```

### Запуск тестов

```bash
# Все unit-тесты
python -m pytest tests/ -v

# С ChromaDB интеграционными тестами
RAG_INTEGRATION_TESTS=1 python -m pytest tests/ -v

# С coverage отчётом
python -m pytest tests/ --cov=agent --cov-report=term-missing
```

### Тестирование D-Bus

```bash
systemctl --user status kde-ai-agent
qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.GetStatus
qdbus org.kde.aiagent /org/kde/aiagent org.kde.aiagent.RunTask "Create hello.txt" "[]"
```

---

## Docker

```bash
# Сборка
docker build -t kde-ai-agent .

# Запуск (headless MCP SSE режим)
docker run -v ~/.config/kde-ai-agent:/root/.config/kde-ai-agent \
  -p 8765:8765 kde-ai-agent
```

---

## MCP Интеграция

Проект поддерживает **Model Context Protocol (MCP)** — открытый стандарт для подключения AI-агентов к внешним инструментам и данным.

### AI Agent как MCP Сервер

```bash
# Запуск как MCP stdio сервера
python -m agent.main --mcp-stdio

# Запуск с MCP SSE сервером на порту 8765
python -m agent.main --mcp-sse
```

### Внешние MCP Серверы

| Сервер | Назначение | Ключевые инструменты |
|--------|-----------|---------------------|
| **lean-ctx** | Контекстное сжатие, кеширование, AST | ctx_read, ctx_search, ctx_graph, ctx_knowledge |
| **engram** | Персистентная память, семантический поиск | mem_save, mem_search, mem_context, mem_timeline |
| **codebase-memory** | Граф знаний кода, трассировка | search_graph, trace_path, get_architecture |
| **searxng** | Приватный веб-поиск | searxng_web_search, web_url_read |

---

## Производительность

### C++ Native слой (GCC 16.1.1)

| Операция | Производительность |
|----------|-------------------|
| cosine_similarity (768d) | ~0.5 µs |
| normalize_embedding (768d) | ~0.3 µs |
| similarity_matrix (1000×1000) | ~5 ms |
| count_tokens (1KB text) | ~2 µs |
| chunk_text (10KB, 512/64) | ~50 µs |

### RAG Engine

| Метрика | Значение |
|---------|----------|
| Время индексации (1000 файлов) | ~30 сек |
| Время поиска (top-5) | ~50 мс |
| Размер коллекции codebase | ~5000 чанков |
| Точность семантического поиска | ~85% recall@5 |

---

## Roadmap

### Phase 3 — Plasma Integration & Hardening (Активна)

| Милстоун | Статус | Описание |
|----------|--------|----------|
| **M1 — Plasma Polish** | ✅ Завершён | FileTree + Config Persistence |
| **M2 — Test Coverage** | ✅ Завершён | Pytest (86 тестов) + MCP Config UI |
| **M3 — Cross-repo AI** | ✅ Завершён | Cross-repo search + trace |
| **M4 — Extended Features** | ✅ Завершён | Voice, Monitoring, TTS |

### Phase 4 — Tauri 2 Integration & Hybrid UI ✅ COMPLETE

| Милстоун | Статус | Описание |
|----------|--------|----------|
| **M1 — Tauri Scaffolding** | ✅ Done | Cargo.toml, lib.rs, commands.rs, 5 plugins |
| **M2 — React Frontend** | ✅ Done | App.tsx, Zustand store, 4 components |
| **M3 — D-Bus Bridge** | ✅ Done | dbus_listener.rs, commands.rs |
| **M4 — LayerShell** | ✅ Done | wayland-client implementation |
| **M5 — Testing & Polish** | ✅ Done | Build, test on Wayland, fix issues |

### Phase 4.5 — UI/UX Overhaul & Messenger Layout ✅ COMPLETE

| Милстоун | Статус | Описание |
|----------|--------|----------|
| **M1 — Layout Rewrite** | ✅ Done | Header, chat flex:1, input, toolbar per v2 reference |
| **M2 — Message Bubbles** | ✅ Done | User/agent bubbles, tool cards, collapsible reasoning |
| **M3 — Tauri Dev Fix** | ✅ Done | Removed devUrl, cargo run --no-default-features |
| **M4 — Codebase Index** | ✅ Done | Full index: 2918 nodes, 5021 edges |

### Phase 5 — Enterprise & Performance (Планируется)

| Милстоун | Приоритет | Описание |
|----------|-----------|----------|
| **Agentic RAG** | 🔥 P0 | Самокорректирующийся RAG с итеративным поиском |
| **Hybrid Search** | 🔥 P0 | BM25 + векторный поиск с RRF fusion |
| **Re-ranking** | 📌 P1 | Cross-encoder для реранжирования результатов |
| **Multi-Agent** | 📌 P1 | Специализированные агенты (код, поиск, анализ) |
| **Plugin System** | 🧊 P2 | Плагинная архитектура инструментов |
| **GPU RAG** | 🧊 P2 | CUDA ускорение для эмбеддингов |

---

## Удаление

```bash
chmod +x uninstall.sh
./uninstall.sh
```

---

## Лицензия

GPL-3.0 — См. [LICENSE](LICENSE)

---

## Благодарности

Патерны и вдохновение от:

- **[JARVIS](https://github.com/novik133/jarvis)** (novik133/jarvis) — KDE Plasma 6 plasmoid структура, системный мониторинг
- **[end4](https://github.com/end-4/dots-hyprland)** (dots-hyprland) — AI sidebar streaming паттерн
- **[Aider](https://github.com/Aider-AI/aider)** (Aider-AI/aider) — ReAct цикл + repo map
- **[OpenCode](https://github.com/opencode-ai/opencode)** (opencode-ai/opencode) — MCP клиент, PubSub, permission система
- **[ZooCode / Roo Code](https://github.com/RooVetGit/Roo-Code)** — MCP auto-approval, интерфейс выполнения инструментов
- **[TurboQuant+](https://github.com/TheTom/turboquant_plus)** (TheTom/turboquant_plus) — Экстремальная KV cache компрессия (ICLR 2026)

---

<div align="center">
  <sub>Сделано с ❤️ для KDE Plasma 6 · Arch Linux · Python 3.14 · GCC 16.1.1</sub>
</div>
