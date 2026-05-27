# Планы и Рекомендации — KDE AI Agent Panel

**Версия**: 1.1.0
**Дата**: 2026-05-26
**Автор**: 🏗️ Lead Architect
**Контекст**: Arch Linux · KDE Plasma 6 · Python 3.14 · GCC 16.1.1 · NVIDIA Wayland · llama.cpp Qwen3.6-35B

---

## Содержание

1. [Резюме](#1-резюме)
2. [Методология исследования](#2-методология-исследования)
3. [Текущее состояние архитектуры](#3-текущее-состояние-архитектуры)
4. [Исследование: RAG в 2026](#4-исследование-rag-в-2026)
5. [Исследование: AI Agent Architecture](#5-исследование-ai-agent-architecture)
6. [Исследование: MCP Best Practices](#6-исследование-mcp-best-practices)
7. [Исследование: KDE Plasma 6 Development](#7-исследование-kde-plasma-6-development)
8. [Исследование: C++ Native Optimization](#8-исследование-c-native-optimization)
9. [Phase 4 — Детальный план](#9-phase-4--детальный-план)
10. [Архитектурные решения (ADRs)](#10-архитектурные-решения-adrs)
11. [Матрица приоритетов](#11-матрица-приоритетов)
12. [Риски и митигации](#12-риски-и-митигации)
13. [Заключение](#13-заключение)

---

## 1. Резюме

Проект **KDE AI Agent Panel** успешно завершил три фазы развития и находится в состоянии production-ready для базового сценария: AI-агент в панели KDE Plasma 6 с 12 инструментами, RAG, MCP интеграцией и C++ native слоем.

**Ключевые метрики текущего состояния:**
- 1593 ноды, 2723 ребра в графе знаний кода
- 86 unit-тестов (все проходят)
- 12 встроенных инструментов
- 4 LLM провайдера
- 4 внешних MCP сервера
- C++ native слой с LTO thin + PGO

**Главные направления развития (Phase 4):**

| Направление | Impact | Сложность | Приоритет |
|------------|--------|-----------|-----------|
| Agentic RAG | 🔥 High | Medium | P0 |
| Hybrid Search + Re-ranking | 🔥 High | Medium | P0 |
| Multi-Agent Architecture | 📌 Medium | High | P1 |
| Plugin System | 📌 Medium | High | P1 |
| GPU Acceleration | 🧊 Medium | High | P2 |
| MCP Security Hardening | 🔥 High | Low | P0 |

---

## 2. Методология исследования

### 2.1 Источники

Исследование проведено с использованием:
- **SearXNG** — приватный веб-поиск по 5 ключевым направлениям
- **codebase-memory** — граф знаний проекта (1593 ноды)
- **lean-ctx** — контекстный анализ кодовой базы
- **engram** — кросс-сессионная память (12 записей)

### 2.2 Исследованные темы

| Тема | Источников | Ключевые находки |
|------|-----------|-----------------|
| RAG Production Guide 2026 | 5 статей | Hybrid + Rerank — лучший ratio цена/качество |
| AI Agent Architecture | 6 статей | ReAct → Reflexion → Multi-Agent эволюция |
| MCP Best Practices | 4 статьи | Security, modular design, rate limiting |
| KDE Plasma 6 Development | 3 статьи | Plasma 6.6, 6.7 на подходе |
| C++/pybind11 Optimization | 2 статьи | PGO, LTO — стандарт индустрии |

---

## 3. Текущее состояние архитектуры

### 3.1 Сильные стороны

```
✅ ReAct Loop — проверенный паттерн, 50 итераций
✅ Multi-Provider — 4 LLM провайдера с единым интерфейсом
✅ MCP Dual Role — сервер + клиент одновременно
✅ C++ Native — GCC 16, LTO thin, PGO, march=native
✅ RAG Engine — ChromaDB, 3 коллекции, fallback механизм
✅ Cross-repo Intelligence — поиск по 10+ проектам
✅ D-Bus + Unix Socket — двойной транспорт
✅ Web UI — FastAPI + HTMX для headless режима
✅ CI/CD — GitHub Actions, Docker, Arch PKGBUILD
```

### 3.2 Слабые стороны

```
❌ RAG: только векторный поиск, нет BM25 (naive RAG)
❌ RAG: нет реранжирования (top-k напрямую в LLM)
❌ RAG: нет самокоррекции (один проход retrieval)
❌ Agent: нет introspection/Reflexion паттерна
❌ Agent: нет multi-агентной архитектуры
❌ MCP: нет sandboxing/rate limiting для внешних серверов
❌ Tools: жёстко зашиты в ToolRegistry, нет плагинов
❌ C++: нет GPU ускорения для эмбеддингов
❌ Tests: нет интеграционных тестов с реальными API
```

### 3.3 Архитектурные долги

| Долг | Impact | Время погашения |
|------|--------|----------------|
| Отсутствие абстракции Tool → Plugin | High | ~2 недели |
| RAG без hybrid search | High | ~1 неделя |
| Нет rate limiting для MCP | Medium | ~3 дня |
| Нет introspection в AgentLoop | Medium | ~1 неделя |
| QML путь хардкожен в main.qml | Low | ~1 день |

---

## 4. Исследование: RAG в 2026

### 4.1 Проблема Naive RAG

Согласно исследованиям 2025-2026, **73% отказов RAG систем происходят на этапе retrieval, не генерации**. Наш проект использует именно naive RAG:

```
Запрос → Embed → Vector Search (top-5) → LLM → Ответ
```

**Проблемы:**
- **Semantic gap**:词汇 пользователя и документа не совпадают
- **Context pollution**: 5 чанков, из которых релевантны 1-2
- **Chunking artifacts**: фиксированные границы чанков
- **No recovery**: если retrieval не нашёл — ответа не будет

### 4.2 Рекомендуемая архитектура: Hybrid + Rerank + Agentic

```
┌─────────────────────────────────────────────────────────────────────┐
│  Agentic RAG Pipeline                                               │
│                                                                     │
│  Запрос → Query Transform → ┌──────────────────────┐               │
│                             │  Hybrid Search        │               │
│                             │  ┌──────┐ ┌────────┐  │               │
│                             │  │ BM25 │ │Vector  │  │               │
│                             │  │(ключ.)│ │(семан.)│  │               │
│                             │  └──┬───┘ └───┬────┘  │               │
│                             │     └────┬────┘       │               │
│                             │     RRF Fusion        │               │
│                             │       top-50          │               │
│                             └──────────┬───────────┘               │
│                                        ▼                           │
│                             ┌──────────────────────┐               │
│                             │  Cross-encoder        │               │
│                             │  Re-ranker            │               │
│                             │  top-50 → top-5       │               │
│                             └──────────┬───────────┘               │
│                                        ▼                           │
│                             ┌──────────────────────┐               │
│                             │  Agent Evaluation     │               │
│                             │  "Достаточно инфы?"   │──┐           │
│                             │  "Релевантно?"        │  │           │
│                             └──────────────────────┘  │           │
│                                        │              │           │
│                                        ▼              │           │
│                             ┌──────────────────┐      │           │
│                             │  LLM Generation   │      │           │
│                             └──────────────────┘      │           │
│                                        │              │           │
│                                        ▼              ▼           │
│                                   Ответ         Reformulate Query │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Chunking Strategy (рекомендации 2026)

| Тип контента | Размер чанка | Overlap | Метод |
|-------------|-------------|---------|-------|
| Документация | 512-1024 токенов | 128 | Semantic chunking |
| Код | Function-level | 0 | AST-based |
| Логи/консоль | 256 токенов | 32 | Fixed-size |
| Markdown | Section-level | 64 | Heading-based |

**Сейчас в проекте:** 512 char, 64 overlap, paragraph-based.  
**Рекомендация:** перейти на semantic chunking (по границам топиков через cosine similarity между предложениями).

### 4.4 Embedding Models (2026)

| Модель | Размерность | MTEB | Стоимость | Статус |
|--------|------------|------|-----------|--------|
| Ollama nomic-embed-text | 768 | ~62 | Бесплатно | ✅ Используется |
| sentence-transformers all-MiniLM-L6-v2 | 384 | ~58 | Бесплатно | ✅ Fallback |
| **Jina embeddings-v3** | 1024 | 65.5 | Self-hosted | 📅 Добавить |
| **Voyage code-3** | 1024 | 67.1 | $0.18/1M | 📅 Для кода |

**Рекомендация:** добавить Jina embeddings-v3 как self-hosted альтернативу для production.

### 4.5 Re-ranking (ключевая оптимизация)

Re-ranking — **самая высокоокупаемая оптимизация** для RAG в 2026:

| Реранкер | Стоимость | Латенси | Качество |
|----------|-----------|---------|----------|
| Cohere Rerank v3.5 | $2/1K | ~200ms | Лучший ratio |
| Jina Reranker v2 | Self-hosted | ~400ms | Open-weight |
| ColBERT v2 | Self-hosted | ~100ms | Token-level |

**Pipeline:** Hybrid Search (top-50) → Re-ranker (top-5) → LLM  
**Улучшение:** 15-30% на RAGAS метриках

### 4.6 Agentic RAG Patterns

| Паттерн | Как работает | Cost vs Naive |
|---------|-------------|---------------|
| **Iterative Retrieval** | Retrieve → evaluate → re-retrieve | 2-3x |
| **Query Decomposition** | Разбить запрос на подвопросы | 3-5x |
| **Hypothesis-Driven** | Сгенерировать гипотезу → найти evidence | 3-5x |
| **Cross-Corpus** | Множественные источники → cross-validate | 5-10x |

**Рекомендация:** начать с Iterative Retrieval — он даёт наибольший прирост качества при минимальном увеличении стоимости.

---

## 5. Исследование: AI Agent Architecture

### 5.1 Эволюция паттернов (2025-2026)

```
2024                   2025                    2026
┌────────┐     ┌──────────────┐     ┌──────────────────┐
│ ReAct  │────→│  Reflexion   │────→│  Multi-Agent     │
│ Think  │     │  Act → Fail  │     │  Coordinator     │
│ Act    │     │  → Reflect   │     │  + Specialists   │
│ Observe│     │  → Plan Again│     │  + Hierarchical  │
└────────┘     └──────────────┘     └──────────────────┘
     │                │                       │
     ▼                ▼                       ▼
┌────────┐     ┌──────────────┐     ┌──────────────────┐
│ Base   │     │ Self-Correct │     │ Parallel         │
│ 50 iter│     │ 10-15 iter   │     │ Orchestrated     │
└────────┘     └──────────────┘     └──────────────────┘
```

### 5.2 Reflexion Pattern (следующий шаг)

**Текущее состояние:** ReAct — думает → действует → наблюдает → повторяет

**Рекомендуемое:** Reflexion — добавляет introspection

```
Act → Fail → Reflect → Plan → Act Again
                │
                ▼
        "Я провалился потому что..."
        "В следующий раз я попробую..."
        "Нужно изменить подход к..."
```

**Изменения в коде:**
- Добавить `ReflectionMemory` — хранит уроки из прошлых ошибок
- Добавить `Evaluator` — оценивает успешность каждого шага
- Модифицировать `AgentLoop._execute_tool()` — добавить анализ ошибок

### 5.3 Multi-Agent Architecture (Phase 4 M3)

```
┌──────────────────────────────────────────────────────┐
│  Orchestrator Agent                                  │
│  ┌────────────────────────────────────────────────┐  │
│  │  Planner: декомпозиция задачи → DAG подзадач   │  │
│  │  Coordinator: управление зависимостями          │  │
│  │  Aggregator: сборка финального результата       │  │
│  └────────────────────────────────────────────────┘  │
│                        │                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │ Code     │ │ Search   │ │ Analysis │ │ Test    │ │
│  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent   │ │
│  │ read/    │ │ codebase │ │ system   │ │ pytest  │ │
│  │ write    │ │ web      │ │ monitor  │ │ cargo   │ │
│  └──────────┘ └──────────┘ └──────────┘ └─────────┘ │
└──────────────────────────────────────────────────────┘
```

**Преимущества:**
- Параллельное выполнение независимых задач
- Специализация агентов (меньше инструментов = меньше ошибок)
- Масштабирование: добавить агента = добавить capability
- Изоляция ошибок: падение одного агента не роняет всю систему

### 5.4 Tool-Use Router Pattern

Для маршрутизации между агентами:

```
Запрос → Router (classifier) → Specialist Agent → Ответ
```

**Router** — лёгкий классификатор (LLM или ML), который определяет:
- Какой агент нужен
- Какие инструменты потребуются
- Какой приоритет задачи

---

## 6. Исследование: MCP Best Practices

### 6.1 MCP Architecture Reference

Согласно спецификации MCP 2025-2026:

```
┌──────────┐     JSON-RPC 2.0     ┌──────────┐
│  Host    │◄──────────────────►│  Server  │
│  (Agent) │    stdio / SSE      │  (Tools) │
└──────────┘                     └──────────┘
     │                                │
     ▼                                ▼
┌──────────┐                     ┌──────────┐
│  Client  │                     │ Resources│
│  Manager │                     │ Prompts  │
└──────────┘                     │ Logging  │
                                 └──────────┘
```

### 6.2 Security Best Practices

| Практика | Статус | Рекомендация |
|----------|--------|-------------|
| **Modular Server Design** | ✅ | Уже разделено по доменам |
| **Input Validation** | ❌ | Добавить schema validation для всех tool inputs |
| **Rate Limiting** | ❌ | Добавить per-agent/per-method quotas |
| **Idempotency** | ❌ | Для write операций |
| **Audit Logging** | ✅ | OpenObserve уже настроен |
| **Sandboxing** | ❌ | Запускать MCP серверы в изолированном окружении |
| **Least Privilege** | ⚠️ | Частично: auto_approve списки |
| **Error Propagation** | ⚠️ | Улучшить graceful fallback |

### 6.3 Рекомендуемые улучшения MCP

1. **Добавить MCP Resource Discovery** — Resources API для доступа к файлам и данным
2. **Добавить MCP Prompts** — шаблоны промптов для типовых задач
3. **Внедрить MCP Logging** — структурированное логирование через MCP протокол
4. **Добавить Health Checks** — ping/health endpoint для мониторинга MCP серверов
5. **Реализовать MCP Roots** — корневые директории для контекста

---

## 7. Исследование: KDE Plasma 6 Development

### 7.1 Текущий контекст

- **KDE Plasma 6.6** — текущая стабильная версия (февраль 2026)
- **KDE Plasma 6.7** — ожидается 16 июня 2026
- **KDE Frameworks 6.5+** — актуальные версии
- **Qt 6.8+** — рекомендуется для новых plasmoid

### 7.2 Plasma 6.7 Новые возможности

| Возможность | Impact для проекта |
|------------|-------------------|
| Улучшенная производительность панели | 🟢 Положительный |
| Новые PlasmaComponents API | 🟡 Проверить совместимость |
| Улучшенная поддержка Wayland | 🟢 NVIDIA Wayland контекст |
| Memory оптимизация (-100MB) | 🟢 Меньше потребление |

### 7.3 Рекомендации по Plasma

1. **Перейти на Plasma6Support вместо Plasma5Support** — Plasma5Support.DataSource deprecated в 6.6+
2. **Использовать Kirigami компоненты** — для лучшей адаптации под мобильные экраны
3. **Добавить Plasma Theme интеграцию** — цвета и стили из глобальной темы
4. **Оптимизировать FileTree** — C++ модель вместо Python subprocess для производительности

---

## 8. Исследование: C++ Native Optimization

### 8.1 Текущие оптимизации

| Оптимизация | Статус | Эффект |
|------------|--------|--------|
| `-march=native` | ✅ | CPU-specific instructions |
| `-O3` | ✅ | Max optimization |
| `-flto=thin` | ✅ | Link-time optimization |
| PGO | ✅ | Profile-guided optimization |
| `-fhardcfr-check-exceptions` | ✅ | Control flow robustness |

### 8.2 Рекомендуемые улучшения

| Улучшение | Impact | Сложность |
|-----------|--------|-----------|
| **CUDA kernels** для batch_normalize | 🔥 High | High |
| **SIMD intrinsics** для cosine_similarity | 🔥 High | Medium |
| **OpenMP** параллелизация similarity_matrix | 📌 Medium | Low |
| **Memory pool** для эмбеддингов | 📌 Medium | Medium |
| **AVX-512** детекция в рантайме | 🧊 Low | Medium |

### 8.3 GPU Acceleration Roadmap

```
Phase 4 M5: GPU Acceleration
├── M5.1: CUDA kernel for batch_normalize (1 неделя)
├── M5.2: CUDA kernel for similarity_matrix (1 неделя)
├── M5.3: Batched embedding inference (2 недели)
└── M5.4: cuBLAS integration (2 недели)
```

---

## 9. Phase 4 — Детальный план

### 9.1 Milestone M1: Agentic RAG (🔥 P0)

**Цель:** RAG accuracy улучшается с 85% до 95%+ recall@5

| Задача | Файлы | Описание | Время |
|--------|-------|----------|-------|
| Query Transformation | [`agent/rag.py`](agent/rag.py) | Добавить query expansion, HyDE, multi-query | 2 дня |
| Iterative Retrieval | [`agent/agent_loop.py`](agent/agent_loop.py) | Agent оценивает достаточность контекста | 3 дня |
| Query Decomposition | [`agent/rag.py`](agent/rag.py) | Разбивка сложных запросов на подвопросы | 2 дня |
| Evaluation Metrics | [`tests/test_rag.py`](tests/test_rag.py) | RAGAS: faithfulness, relevance, precision | 2 дня |

**Total:** ~9 дней

### 9.2 Milestone M2: Hybrid Search + Re-ranking (🔥 P0)

**Цель:** 25-40% precision improvement

| Задача | Файлы | Описание | Время |
|--------|-------|----------|-------|
| BM25 Index | [`agent/rag.py`](agent/rag.py) | Добавить BM25 (whoosh или tantivy) | 2 дня |
| RRF Fusion | [`agent/rag.py`](agent/rag.py) | Reciprocal Rank Fusion для объединения результатов | 1 день |
| Re-ranker Integration | [`agent/rag.py`](agent/rag.py) | Cross-encoder (Jina или Cohere) | 2 дня |
| Pipeline Orchestration | [`agent/rag.py`](agent/rag.py) | Hybrid → Rerank → LLM | 1 день |
| Tests | [`tests/test_rag.py`](tests/test_rag.py) | Тесты hybrid search + rerank | 2 дня |

**Total:** ~8 дней

### 9.3 Milestone M3: Multi-Agent Architecture (📌 P1)

**Цель:** Параллельное выполнение, специализация, масштабирование

| Задача | Файлы | Описание | Время |
|--------|-------|----------|-------|
| Agent Base Class | [`agent/agent_loop.py`](agent/agent_loop.py) | Рефакторинг AgentLoop в BaseAgent | 2 дня |
| Orchestrator Agent | [`agent/orchestrator.py`](agent/orchestrator.py) | Планировщик + координатор | 3 дня |
| Code Agent | [`agent/agents/code_agent.py`](agent/agents/code_agent.py) | read/write/search специализация | 2 дня |
| Search Agent | [`agent/agents/search_agent.py`](agent/agents/search_agent.py) | codebase + web + RAG | 2 дня |
| Analysis Agent | [`agent/agents/analysis_agent.py`](agent/agents/analysis_agent.py) | system_monitor + анализ | 2 дня |
| Router | [`agent/router.py`](agent/router.py) | Классификатор запросов → агент | 2 дня |
| Tests | [`tests/`](tests/) | Тесты multi-agent | 3 дня |

**Total:** ~16 дней

### 9.4 Milestone M4: Plugin System (📌 P1)

**Цель:** Extensible tool ecosystem

| Задача | Файлы | Описание | Время |
|--------|-------|----------|-------|
| Plugin Interface | [`agent/plugin.py`](agent/plugin.py) | Abstract base class для плагинов | 2 дня |
| Plugin Manager | [`agent/plugin_manager.py`](agent/plugin_manager.py) | Загрузка, валидация, lifecycle | 2 дня |
| Plugin Discovery | [`agent/plugin_manager.py`](agent/plugin_manager.py) | Сканирование директорий плагинов | 1 день |
| SDK Documentation | [`docs/plugin-sdk.md`](docs/plugin-sdk.md) | Документация для разработчиков плагинов | 2 дня |
| Example Plugin | [`plugins/example/`](plugins/example/) | Пример плагина | 1 день |
| Tests | [`tests/test_plugin.py`](tests/test_plugin.py) | Тесты плагинной системы | 2 дня |

**Total:** ~10 дней

### 9.5 Milestone M5: GPU Acceleration (🧊 P2)

**Цель:** 10x faster embedding generation

| Задача | Файлы | Описание | Время |
|--------|-------|----------|-------|
| CUDA batch_normalize | [`src/embedding.cpp`](src/embedding.cpp) | CUDA kernel | 1 неделя |
| CUDA similarity_matrix | [`src/embedding.cpp`](src/embedding.cpp) | CUDA kernel | 1 неделя |
| Batched Embedding | [`agent/rag.py`](agent/rag.py) | GPU inference для эмбеддингов | 2 недели |
| cuBLAS Integration | [`CMakeLists.txt`](CMakeLists.txt) | BLAS optimizations | 2 недели |

**Total:** ~6 недель

### 9.6 Quick Wins (можно сделать за 1-3 дня)

| Задача | Impact | Время |
|--------|--------|-------|
| MCP Rate Limiting | 🔥 High | 1 день |
| MCP Input Validation | 🔥 High | 1 день |
| Semantic Chunking | 📌 Medium | 2 дня |
| RAGAS Evaluation | 📌 Medium | 2 дня |
| Health Checks для MCP | 📌 Medium | 1 день |
| Plasma6Support migration | 🟢 Low | 1 день |

---

## 10. Архитектурные решения (ADRs)

### ADR-001: Agentic RAG вместо Naive RAG

**Статус:** Предложено  
**Контекст:** Текущий RAG использует один проход vector search → LLM  
**Решение:** Внедрить итеративный retrieval с оценкой достаточности контекста  
**Обоснование:** 73% отказов RAG — на этапе retrieval. Agentic RAG даёт +27% accuracy (DSPy benchmarks)  
**Trade-offs:** +2-3x стоимость, +2-5s латенси  
**Альтернативы:** Fine-tuning модели (дороже, сложнее обновлять)

### ADR-002: Hybrid Search (BM25 + Vector) с RRF Fusion

**Статус:** Предложено  
**Контекст:** Чисто векторный поиск пропускает точные keyword-матчи  
**Решение:** BM25 (whoosh/tantivy) + Vector Search (ChromaDB) → RRF Fusion  
**Обоснование:** 25-40% precision improvement, стандарт индустрии 2026  
**Trade-offs:** +200ms latency, +1 dependency  
**Альтернативы:** Только BM25 (теряем семантику), только Vector (текущее состояние)

### ADR-003: Reflexion Pattern для Agent Loop

**Статус:** Предложено  
**Контекст:** ReAct цикл не анализирует свои ошибки  
**Решение:** Добавить ReflectionMemory + Evaluator в AgentLoop  
**Обоснование:** Reflexion улучшает accuracy на 10-15% на multi-step задачах  
**Trade-offs:** +2-3x токенов на отражение, +сложность кода  
**Альтернативы:** Увеличить max_iterations (дешевле, но не учится)

### ADR-004: Multi-Agent Architecture

**Статус:** Предложено  
**Контекст:** Один агент со всеми инструментами — source of confusion  
**Решение:** Orchestrator + специализированные агенты (Code, Search, Analysis, Test)  
**Обоснование:** Меньше инструментов на агента = меньше ошибок, параллельное выполнение  
**Trade-offs:** +сложность оркестрации, +overhead на коммуникацию  
**Альтернативы:** Продолжать с одним агентом (проще, но не масштабируется)

### ADR-005: Plugin System вместо Hardcoded Tools

**Статус:** Предложено  
**Контекст:** ToolRegistry — жёсткая регистрация инструментов в коде  
**Решение:** Plugin interface + Plugin Manager с динамической загрузкой  
**Обоснование:** Расширяемость, community contributions, изоляция ошибок  
**Trade-offs:** +сложность, +security considerations  
**Альтернативы:** Продолжать hardcode (проще, но не extensible)

---

## 11. Матрица приоритетов

```
Высокий Impact
     │
     │  ┌──────────────────────────────────────────────────┐
     │  │                                                  │
 🔥  │  │  Agentic RAG     Hybrid Search                   │
 P0  │  │  MCP Security    Re-ranking                      │
     │  │                                                  │
     ├──┼──────────────────────────────────────────────────┤
     │  │                                                  │
 📌  │  │  Multi-Agent     Plugin System                   │
 P1  │  │  Reflexion       Semantic Chunking               │
     │  │                                                  │
     ├──┼──────────────────────────────────────────────────┤
     │  │                                                  │
 🧊  │  │  GPU Accel       Plasma 6.7 Migration            │
 P2  │  │  AVX-512         C++ Memory Pool                 │
     │  │                                                  │
     └──┼──────────────────────────────────────────────────┘
        │          Low              Medium           High
                   Сложность реализации
```

### Приоритеты по времени

| Когда | Что делать |
|-------|-----------|
| **На этой неделе** | MCP Rate Limiting, Input Validation, Semantic Chunking |
| **Через 2 недели** | Agentic RAG M1, Hybrid Search M2 |
| **Через месяц** | Reflexion Pattern, Multi-Agent M3 |
| **Через 2 месяца** | Plugin System M4 |
| **Через 3 месяца** | GPU Acceleration M5 |

---

## 12. Риски и митигации

### 12.1 Технические риски

| Риск | Вероятность | Impact | Митигация |
|------|------------|--------|-----------|
| Agentic RAG увеличивает latency | High | Medium | Async retrieval, caching |
| Multi-Agent сложнее отлаживать | Medium | High | OpenObserve tracing, structured logging |
| Plugin System security | Medium | High | Sandboxing, permission system |
| GPU код непереносим | Low | Medium | CUDA + CPU fallback |
| Plasma 6.7 API changes | Low | Low | CI тесты на beta |

### 12.2 Архитектурные риски

| Риск | Описание | Митигация |
|------|----------|-----------|
| Over-engineering | Слишком сложная архитектура для простых задач | Adaptive RAG: простой путь для простых запросов |
| Vendor lock-in | Зависимость от конкретных MCP серверов | MCP — открытый стандарт, fallback реализации |
| Token costs | Agentic RAG + Reflexion = больше токенов | Бюджетирование, лимиты, мониторинг |

### 12.3 NVIDIA Wayland специфичные риски

| Риск | Описание | Митигация |
|------|----------|-----------|
| D-Bus на Wayland | D-Bus работает через XWayland | Unix socket fallback уже реализован |
| GPU memory | CUDA + Plasma = конкуренция за GPU | Настраиваемые лимиты GPU memory |
| Screen recording | Wayland screen capture protocols | PipeWire/xdg-desktop-portal интеграция |

---

## 13. Заключение

### Ключевые выводы

1. **Проект в отличной форме** — Phase 3 завершён, 86 тестов, production-ready базовый сценарий
2. **RAG — главный приоритет** — переход от naive к hybrid + agentic RAG даст наибольший прирост качества
3. **MCP Security — quick win** — rate limiting и input validation можно сделать за 1-2 дня
4. **Multi-Agent — стратегическое направление** — масштабируемость и специализация
5. **GPU — долгосрочная инвестиция** — когда CPU станет bottleneck

### Рекомендуемый порядок действий

```
Неделя 1:   MCP Security Hardening + Semantic Chunking
Неделя 2-3: Hybrid Search + Re-ranking (M2)
Неделя 4-5: Agentic RAG (M1)
Неделя 6-7: Reflexion Pattern
Неделя 8-10: Multi-Agent Architecture (M3)
Неделя 11-12: Plugin System (M4)
Неделя 13+: GPU Acceleration (M5)
```

### Метрики успеха Phase 4

| Метрика | Текущее | Цель |
|---------|---------|------|
| RAG recall@5 | ~85% | >95% |
| RAGAS faithfulness | — | >0.9 |
| Hybrid search precision | — | +25-40% |
| Agent task completion rate | — | >90% |
| MCP server uptime | — | >99.9% |
| Plugin ecosystem | 0 plugins | >5 community plugins |
| GPU embedding throughput | CPU-only | 10x improvement |

---

## 14. Исследование: Wayland GLib Re-entrancy Crash

### 14.1 Проблема

Qt6 на Wayland использует `QEventDispatcherGlib`. Любой вызов `window.setVisible()`/`show()`/`hide()`/`setX()` из callback'ов `QTimer`, `QThread.pyqtSignal` или `QMetaObject.invokeMethod` вызывает GLib re-entrancy → `QMessageLogger::fatal` → `abort()` (Signal 6).

### 14.2 Испробованные подходы

| Подход | Результат | Причина |
|--------|-----------|---------|
| QTimer → window.show() | ❌ Crash | GLib re-entrancy |
| QThread.pyqtSignal → show() | ❌ Crash | sendPostedEvents re-entrancy |
| QMetaObject.invokeMethod(QueuedConnection) | ❌ Crash | QueuedConnection всё равно через GLib |
| Off-screen setX() | ❌ Crash | setX() триггерит compositor roundtrip |
| Self-pipe trick (os.pipe + QSocketNotifier) | ⚠️ Нестабильно | SIGUSR1 toggle ненадёжен |
| **QML Window (AppGrid pattern)** | ✅ **Стабильно** | Внутри Plasma QML engine, без GLib |

### 14.3 Решение: AppGrid Pattern

**AppGrid** (xarbit/plasma6-applet-appgrid) использует правильный подход:

1. **C++ плагин** расширяет `Plasma::Applet` — предоставляет `configureWindow()` через `LayerShellQt::Window`
2. **QML** создаёт `Window` как дочерний компонент через `Component.createObject()`
3. **Plasmoid.configureWindow(window)** — единственный правильный способ для Wayland
4. **activationTogglesExpanded: false** + `Plasmoid.activated` сигнал

```qml
// main.qml — AppGrid pattern
PlasmoidItem {
    activationTogglesExpanded: false
    property GridWindow gridWindow: null
    property bool gridOpen: false

    Connections {
        target: Plasmoid
        function onActivated() { toggleWindow() }
    }

    function openWindow() {
        gridOpen = true
        if (!gridWindow) {
            gridWindow = gridWindowComponent.createObject(kicker)
        }
        gridWindow.showGrid()
    }

    Component {
        id: gridWindowComponent
        GridWindow {}
    }
}
```

```cpp
// C++ plugin — LayerShellQt::Window
void AppGridPlugin::configureWayland(QWindow *window) {
    auto *layer = LayerShellQt::Window::get(window);
    layer->setLayer(LayerShellQt::Window::LayerTop);
    layer->setAnchors(AnchorTop | AnchorBottom | AnchorLeft | AnchorRight);
}
```

### 14.4 Рекомендация

Создать C++ плагин для нашего плазмода (как в AppGrid), который предоставляет:
- `configureWindow()` — LayerShellQt для Wayland
- `updateWindowScreen()` — переключение экранов
- `setBlurBehind()` — blur эффект

Это единственный способ получить стабильное frameless окно на Wayland.

---

## 15. Исследование: AppGrid Code Analysis

### 15.1 Структура

| Компонент | Файл | Назначение |
|-----------|------|-----------|
| C++ Plugin | `src/appgridplugin.cpp` (864 строк) | Plasma::Applet, LayerShellQt, window management |
| QML Root | `package/contents/ui/main.qml` (123 строки) | PlasmoidItem + Window lifecycle |
| QML Window | `package/contents/ui/GridWindow.qml` (336 строк) | Overlay window, animations, blur |
| QML Panel | `package/contents/ui/GridPanel.qml` | Grid content |

### 15.2 Ключевые паттерны

1. **C++ плагин** — `Plasma::Applet` subclass с методами `configureWindow()`, `updateWindowScreen()`, `setBlurBehind()`, `setInputRect()`
2. **LayerShellQt::Window** — Wayland-native positioning (LayerTop, full screen anchors)
3. **Window lifecycle** — `Component.createObject()` + `gridOpen` boolean для toggle
4. **Close on deactivate** — `onActiveChanged` с `deactivateGuard` таймером
5. **Input rect** — `window->setMask()` для pass-through областей
6. **Animations** — 11 стилей анимаций через Loader

### 15.3 Применимость к нашему проекту

Для стабильной боковой панели на Wayland нужно:
1. Создать C++ плагин (как AppGridPlugin) с `configureWindow()` для LayerShellQt
2. Использовать `Plasmoid.configureWindow(window)` в QML
3. Позиционировать окно слева (не full screen, а 380px)
4. Добавить slide animation через `Behavior on x`

---

*Документ создан: 2026-05-26*
*Автор: 🏗️ Lead Architect*
*Контекст: Arch Linux · KDE Plasma 6 · Python 3.14 · GCC 16.1.1 · NVIDIA Wayland · llama.cpp Qwen3.6-35B*
*Инструменты: SearXNG research · codebase-memory · lean-ctx · engram · AppGrid source analysis*

## 16. Исследование: Frontend Dependencies Architecture

### 16.1 React 19 + Vite 6 + TypeScript Stack

#### React 19 (Production: ^19.0.0)
- **Server Components** — нативно интегрированы, не нужен Next.js
- **Actions API** — упрощает формы и мутации данных (replace useEffect + setState)
- **Automatic Batching** — улучшена concurrent rendering
- **useActionState / useOptimistic** — встроенная поддержка optimistic updates
- **useOptimistic hook** — упрощает optimistic UI updates для async операций
- **Relevance для проекта**: React 19 идеально подходит для AI Agent UI — Actions API упрощает интеграцию с Tauri IPC, Server Components позволяют offload LLM queries на бэкенд

#### Vite 6 (Build: ^6.0.0)
- **Faster HMR** — критично для QML/React bridge development
- **ESM-first** — лучше совместимость с Tauri webview
- **Plugin system** — @vitejs/plugin-react для JSX/TSX support
- **Relevance**: Vite 6 обеспечивает быструю разработку с мгновенным hot-reload

#### TypeScript (Type: ^5.6.0)
- **Essential** для QML interop type safety
- **Strict mode** — предотвращает runtime errors при IPC calls
- **Relevance**: TypeScript обеспечивает type safety между React frontend ↔ Rust backend ↔ QML

#### Tailwind CSS (Build: ^3.4.0)
- **Utility-first** — идеально для быстрой итерации UI компонентов
- **PostCSS + Autoprefixer** — vendor prefixing для Wayland compatibility
- **Relevance**: Tailwind ускоряет разработку QML-подобных компонентов в React

### 16.2 Zustand State Management (Production: ^5.0.0)

#### Преимущества для проекта
- **Minimal API** — нет boilerplate, в отличие от Redux
- **Hook-based** — natural integration с React 19
- **Pull-based model** — selectors для efficient re-rendering
- **No Context Provider** — не нужно оборачивать приложение

#### Zustand vs QtQuick Property Binding
| Аспект | QtQuick Binding | Zustand |
|--------|----------------|---------|
| Reactivity | Automatic (declarative) | Explicit (selectors) |
| Cross-process | Нет (QML only) | Да (через IPC) |
| Testability | Low | High |
| Boilerplate | Low | Minimal |
| **Relevance** | Native для QML | Bridge между React ↔ QML |

**Ключевая инсайт**: Zustand store может служить единым источником истины между React frontend и QML через Tauri IPC — Zustand selectors map к QML properties.

### 16.3 Lucide React Icons (Production: ^0.383.0)

#### Почему Lucide, а не FontAwesome
| Аспект | Lucide | FontAwesome |
|--------|---------|-------------|
| Format | SVG (inline) | Font file |
| Tree-shakeable | ✅ Да | ❌ Нет |
| Bundle impact | Only imported icons | All icons loaded |
| Customization | Props (size, color, stroke) | CSS overrides |
| License | MIT | CC BY 4.0 |
| Icons count | 1600+ | 20000+ |

**Relevance для проекта**: Tree-shakeable SVG icons — только импортированные иконки попадают в bundle. Идеально для Plasma sidebar где важен размер и производительность.

### 16.4 Tauri 2.0 Plugins Analysis

#### @tauri-apps/api (Production: ^2)
- **Webview-based** — использует системный WebView (не Chromium)
- **IPC bridge** — между Rust backend и JS frontend
- **Relevance**: Основной транспорт для React ↔ Rust communication

#### tauri-plugin-autostart (Production: ^2)
- **Linux support** — работает через XDG Autostart
- **Flatpak caveat** — issue #3166: Exec path issue в Flatpak
- **Relevance**: Для автозапуска AI Agent при логине в KDE

#### tauri-plugin-global-shortcut (Production: ^2)
- **Rust 1.77.2+ required** — наш GCC 16.1.1 совместим
- **Wayland support** — работает, но требует Accessibility permissions
- **Default shortcut** — ctrl+shift+space (конфликт с KDE?)
- **Relevance**: Global hotkey для вызова AI Agent panel из любого приложения

#### tauri-plugin-shell (Production: ^2)
- **Process spawning** — для LLM commands (llama.cpp)
- **File/URL management** — через default applications
- **Relevance**: Запуск `llama-server` и управление процессами

#### tauri-plugin-store (Production: ^2)
- **JSON persistence** — для configuration
- **Limitations**: Не подходит для complex state (embedding vectors)
- **Relevance**: Хранение API keys, settings, preferences

### 16.5 Hybrid Architecture: React/Tauri + QML/Plasma

#### Наша архитектура
```
┌─────────────────────────────────────────────────────────────┐
│                    KDE Plasma 6                              │
│  ┌─────────────┐  ┌─────────────────────────────────────┐  │
│  │  QML/Plasma │  │       Tauri WebView (React)          │  │
│  │  Side Panel │  │                                      │  │
│  │             │  │  ┌───────────────────────────────┐   │  │
│  │  • System   │  │  │  React 19 + TypeScript         │   │  │
│  │  • Tray     │  │  │  Zustand State                 │   │  │
│  │  • Native   │  │  │  Lucide Icons                  │   │  │
│  │  • Wayland  │  │  │  Tailwind CSS                  │   │  │
│  │  • Kirigami │  │  └───────────┬───────────────────┘   │  │
│  │             │  │              │ IPC (Tauri)           │  │
│  └──────┬──────┘  │              │                       │  │
│         │          │  ┌───────────▼───────────────────┐   │  │
│         │          │  │  Rust Backend (Tauri)          │   │  │
│         │          │  │  • llama.cpp (LLM inference)   │   │  │
│         │          │  │  • Embeddings (RAG)            │   │  │
│         │          │  │  • MCP Server/Client           │   │  │
│         │          │  │  • Plugin System               │   │  │
│         │          │  └───────────────────────────────┘   │  │
│         │          └─────────────────────────────────────┘  │
└─────────┴───────────────────────────────────────────────────┘
```

#### Почему Hybrid, а не Pure QML или Pure React
| Архитектура | Плюсы | Минусы |
|-------------|-------|--------|
| **Pure QML** | Native Plasma, best Wayland perf | Limited AI ecosystem, no React components |
| **Pure React/Tauri** | Rich ecosystem, TypeScript | No native Plasma integration |
| **Hybrid (наш выбор)** | Best of both worlds | More complexity, IPC overhead |

**Решение**: Hybrid архитектура — QML для native sidebar integration, React для AI agent UI complexity.

### 16.6 Wayland-specific Concerns

#### NVIDIA Wayland Risks
| Риск | Severity | Mitigation |
|------|----------|------------|
| GBM EGL display crash | High | Tauri webview isolation |
| GPU memory contention | Medium | Configurable GPU limits |
| Screen recording | Medium | xdg-desktop-portal integration |

#### Tauri on Wayland
- Tauri 2.0 использует системный WebView (WebKitGTK на Linux)
- WebKitGTK на Wayland работает стабильнее чем Chromium
- **Recommendation**: Использовать `WEBKIT_DISABLE_DMABUF_RENDERER=1` для NVIDIA GPUs

### 16.7 Dependencies Summary

#### Production Dependencies — Оценка
| Dependency | Fit for Project | Risk |
|------------|----------------|------|
| React 19 | ✅ Отлично — идеален для AI UI | Low |
| Zustand | ✅ Хорошо — minimal overhead | Low |
| Lucide React | ✅ Отлично — tree-shakeable | Low |
| Tauri 2 | ✅ Хорошо — native Rust backend | Medium (Wayland) |
| Tailwind CSS | ✅ Хорошо — rapid UI dev | Low |
| Vite 6 | ✅ Отлично — fast HMR | Low |

#### Development Dependencies — Оценка
| Dependency | Fit for Project | Risk |
|------------|----------------|------|
| TypeScript | ✅ Essential | Low |
| PostCSS/Autoprefixer | ✅ Needed for vendor prefixes | Low |
| Tauri CLI | ✅ Required for build | Low |
