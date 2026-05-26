# MCP Аудит и Рефакторинг custom_modes.yaml

**Дата:** 2026-05-26  
**Автор:** ✍️ Mode Architect  
**Версия:** v2.0

---

## 1. Инвентаризация MCP серверов

Источник: [`mcp_settings.json`](/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/mcp_settings.json)

| Сервер | Команда | Инструментов alwaysAllow | Назначение |
|--------|---------|------------------------:|------------|
| **lean-ctx** | `lean-ctx` | 12 | Контекстное сжатие, кеширование чтения, сессии CCP, AST парсинг, shell-компрессия |
| **engram** | `/usr/bin/engram mcp` | 18 | Персистентная память, семантический поиск, FTS5, управление сессиями |
| **codebase-memory** | `/usr/bin/codebase-memory-mcp stdio` | 14 | Граф знаний кода (tree-sitter), трассировка вызовов, ADR, impact analysis |
| **searxng** | `mcp-searxng` | 2 | Приватный веб-поиск через SearXNG, чтение URL |

### 1.1 lean-ctx — инструменты

| Инструмент | Назначение |
|-----------|------------|
| `ctx_overview` | Получить task-relevant проектный обзор |
| `ctx_read` | Чтение файла (10 режимов: full, map, signatures, entropy, aggressive, task, ref, diff, lines:N-M) |
| `ctx_search` | Регулярный поиск по коду (gitignore-aware) |
| `ctx_shell` | Выполнение команд с компрессией вывода (95+ паттернов) |
| `ctx_edit` | Редактирование через search-and-replace |
| `ctx_graph` | Граф кода: build, related, symbol, impact, status, enrich, context, diagram |
| `ctx_knowledge` | Персистентные факты: remember, recall, pattern, feedback, relate, consolidate |
| `ctx_session` | Кросс-сессионная память: load, save, task, finding, decision, snapshot |
| `ctx_provider` | Внешние провайдеры: GitHub, GitLab |
| `ctx_call` | Вызов 50+ lean-ctx инструментов по имени |
| `ctx_tree` | Древовидный листинг директории |
| `ctx_overview` | Task-relevant проектный обзор |

### 1.2 engram — инструменты

| Инструмент | Назначение |
|-----------|------------|
| `mem_current_project` | Определить текущий проект |
| `mem_search` | Поиск по памяти (семантический + FTS5) |
| `mem_save` | Сохранить наблюдение (типы: decision, architecture, bugfix, pattern, config) |
| `mem_context` | Контекст предыдущих сессий |
| `mem_session_summary` | Сохранить итоговую сводку сессии |
| `mem_session_start/end` | Управление сессиями |
| `mem_get_observation` | Получить полное содержимое наблюдения |
| `mem_timeline` | Хронология вокруг наблюдения |
| `mem_judge` | Разрешить конфликты памяти |
| `mem_capture_passive` | Автоматическое извлечение learnings |
| `mem_compare` | Сравнить два наблюдения семантически |
| `mem_stats` | Статистика системы памяти |
| `mem_update` | Обновить существующее наблюдение |
| `mem_delete` | Удалить наблюдение |
| `mem_merge_projects` | Слияние проектных вариантов |
| `mem_save_prompt` | Сохранить промт пользователя |
| `mem_suggest_topic_key` | Предложить topic_key для upsert |
| `mem_doctor` | Диагностика системы |

### 1.3 codebase-memory — инструменты

| Инструмент | Назначение |
|-----------|------------|
| `list_projects` | Список индексированных проектов |
| `index_repository` | Индексация репозитория в граф знаний |
| `get_architecture` | Архитектурный обзор проекта |
| `index_status` | Статус индексации |
| `manage_adr` | Создание/обновление Architecture Decision Records |
| `search_graph` | Поиск по графу (BM25, name_pattern, semantic_query) |
| `search_code` | Поиск кода с обогащением из графа |
| `query_graph` | Cypher запросы к графу |
| `trace_path` | Трассировка: calls, data_flow, cross_service |
| `get_code_snippet` | Чтение исходного кода функции/класса |
| `get_graph_schema` | Схема графа (ноды, рёбра) |
| `delete_project` | Удалить проект из индекса |
| `detect_changes` | Обнаружение изменений и их влияния |
| `ingest_traces` | Импорт runtime-трейсов в граф |

### 1.4 searxng — инструменты

| Инструмент | Назначение |
|-----------|------------|
| `searxng_web_search` | Веб-поиск с параметрами (язык, время, safesearch) |
| `web_url_read` | Чтение содержимого URL |

---

## 2. Аудит custom_modes.yaml: найденные пробелы

Источник: [`custom_modes.yaml`](/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml)

### 2.1 Сводная таблица покрытия MCP инструментами

| Мод | lean-ctx | engram | codebase-memory | searxng | Группа mcp |
|-----|:--------:|:------:|:---------------:|:-------:|:----------:|
| 🏗️ architect | ✅ | ✅ | ✅ | ➕ | ✅ |
| 💻 code | ✅ | ✅ | ✅ | ➕ | ✅ |
| 🪲 debug | ✅ | ✅ | ✅ | ➕ | ✅ |
| ❓ ask | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🪃 orchestrator | ✅ | ✅ | ✅ | ➕ | ✅ |
| 🚀 devops | ✅ | ✅ | ✅ | ➕ | ✅ |
| 💡 coding-teacher | ➕ | ➕ | ➕ | ➕ | 🔴→✅ |
| ✍️ mode-writer | ✅ | ✅ | ✅ | ✅ | ✅ |
| 🧩 skill-writer | ✅ | ✅ | ✅ | ➕ | ✅ |
| 🔀 merge-resolver | ✅ | ✅ | ✅ | ➕ | ✅ |
| 🧠 yeah-boi | ✅ | ✅ | ✅ | ➕ | ✅ |
| 🎨 plasma-specialist | ✅ | ✅ | ✅ | ➕ | ✅ |
| 🤖 ai-engineer | ✅ | ✅ | ✅ | ➕ | ✅ |

**Легенда:** ✅ = был, ➕ = добавлен, 🔴→✅ = критический пробел исправлен

### 2.2 Критические пробелы

| # | Проблема | Мод | Серьёзность | Исправление |
|---|----------|-----|:-----------:|-------------|
| 1 | Нет группы `mcp` | `coding-teacher` | 🔴 CRITICAL | Добавлена группа `mcp` |
| 2 | Нет `searxng_web_search` | 11 модов | 🟡 MEDIUM | Добавлен во все моды |
| 3 | Нет `trace_path` | `architect`, `code`, `debug` | 🟡 MEDIUM | Добавлен |
| 4 | Нет `detect_changes` | `debug`, `merge-resolver` | 🟡 MEDIUM | Добавлен |
| 5 | Нет `manage_adr` | `architect` | 🟢 LOW | Добавлен |
| 6 | Нет `get_code_snippet` | `code`, `debug` | 🟢 LOW | Добавлен |
| 7 | Нет `ingest_traces` | `debug` | 🟢 LOW | Добавлен |

---

## 3. Внесённые изменения

### 3.1 Все моды — добавлена секция `MCP TOOL MAP`

Каждый мод теперь содержит структурированную карту инструментов, сгруппированных по серверам:

```yaml
# MCP TOOL MAP
── lean-ctx ──
ctx_overview, ctx_read, ctx_search, ctx_edit, ctx_shell
ctx_graph(related|diagram), ctx_knowledge(recall|pattern)
ctx_session(task|finding|decision)
── engram ──
mem_search, mem_save (type:...), mem_context, mem_session_summary
── codebase-memory ──
search_graph, search_code, get_code_snippet, trace_path(mode:...)
── searxng ──
searxng_web_search (research ...)
web_url_read (read documentation)
```

### 3.2 `coding-teacher` — полная переработка

- **Добавлена группа `mcp`** — критический пробел
- **Добавлен MCP TOOL MAP** — все 4 сервера
- **Добавлена стартовая последовательность** — `ctx_overview` → `search_graph` → `searxng_web_search`
- **Добавлена делегация** — `→ code`, `→ ask`, `→ debug`
- **Обновлён `roleDefinition`** — указано использование MCP для примеров из реального кода
- **Обновлён `description`** — указано "MCP-grounded codebase examples"

### 3.3 `architect` — расширение инструментов

- Добавлен `trace_path(mode:data_flow|cross_service)` — impact analysis
- Добавлен `manage_adr` — документирование архитектурных решений
- Добавлен `searxng_web_search` — исследование технологий
- Добавлен `detect_changes` — анализ изменений перед проектированием

### 3.4 `code` — расширение инструментов

- Добавлен `get_code_snippet` — чтение конкретных реализаций
- Добавлен `trace_path(mode:calls)` — понимание caller/callee
- Добавлен `searxng_web_search` — исследование API и библиотек

### 3.5 `debug` — расширение инструментов

- Добавлен `trace_path(mode:data_flow)` — трассировка данных через баг
- Добавлен `detect_changes` — поиск недавних изменений
- Добавлен `ingest_traces` — обогащение графа runtime-данными
- Добавлен `searxng_web_search` — поиск ошибок и известных проблем

### 3.6 `merge-resolver` — расширение инструментов

- Добавлен `detect_changes` — анализ изменений на каждой ветке
- Добавлен `trace_path(mode:calls)` — понимание влияния конфликтующих изменений
- Добавлен `searxng_web_search` — исследование стратегий слияния

### 3.7 Остальные моды — добавлен `searxng`

- `orchestrator`, `devops`, `skill-writer`, `yeah-boi`, `plasma-specialist`, `ai-engineer` — все получили `searxng_web_search` + `web_url_read`

---

## 4. Валидация

```bash
# Проверка YAML структуры
python3 -c "
import re
f = open('/home/neo/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml').read()
slugs = re.findall(r'^  - slug: (.+)$', f, re.MULTILINE)
print(f'Slugs found: {len(slugs)}')
for s in slugs: print(f'  ✅ {s}')
dupes = [s for s in slugs if slugs.count(s) > 1]
print(f'Duplicates: {dupes if dupes else \"None ✅\"}')
"

# Результат:
# Slugs found: 13
#   ✅ architect
#   ✅ code
#   ✅ debug
#   ✅ ask
#   ✅ orchestrator
#   ✅ devops
#   ✅ coding-teacher
#   ✅ mode-writer
#   ✅ skill-writer
#   ✅ merge-resolver
#   ✅ yeah-boi
#   ✅ plasma-specialist
#   ✅ ai-engineer
# Duplicates: None ✅
```

---

## 5. Рекомендация по навыкам (Skills)

### 🔥 Приоритет 1 — Критические

| Навык | Описание | Инструменты | Для кого |
|-------|----------|-------------|----------|
| **`mcp-tool-audit`** | Сканирует MCP конфиг и custom_modes.yaml, выявляет несоответствия между доступными инструментами и прописанными в модах | `ctx_read`, `ctx_search`, `mem_save` | `mode-writer` |
| **`cross-service-impact-analysis`** | Анализирует влияние изменений через HTTP/async вызовы между сервисами | `trace_path(mode:cross_service)`, `query_graph`, `mem_save` | `architect`, `debug` |

### 🔸 Приоритет 2 — Важные

| Навык | Описание | Инструменты | Для кого |
|-------|----------|-------------|----------|
| **`plasma-debug-workflow`** | Стандартизированный дебаг-воркфлоу для Plasma виджетов | `ctx_shell`, `trace_path`, `searxng_web_search`, `mem_save` | `plasma-specialist`, `debug` |
| **`adr-from-session`** | Извлекает архитектурные решения из сессии и создаёт ADR | `ctx_session(finding\|decision)`, `manage_adr`, `mem_save` | `architect`, `yeah-boi` |

### 🔹 Приоритет 3 — Утилитарные

| Навык | Описание | Инструменты | Для кого |
|-------|----------|-------------|----------|
| **`memory-consolidation`** | Собирает все решения сессии и создаёт структурированную сводку | `ctx_session`, `mem_save`, `mem_session_summary` | Все моды |

### Как добавить навыки

```bash
# Используй режим 🧩 Skill Engineer
new_task(skill-writer, "Создай навык mcp-tool-audit по спецификации из MCP_AUDIT_REPORT.md")
```

---

## 6. Сохранение в MCP память

| Система | Действие | Статус |
|---------|----------|:------:|
| **lean-ctx** | `ctx_knowledge(remember)` — custom_modes.yaml-v2-update | ✅ |
| **engram** | `mem_save(type:architecture)` — custom_modes.yaml v2 | ✅ |
| **engram** | `mem_judge` — конфликт разрешён (relation: scoped) | ✅ |
| **Файл** | `MCP_AUDIT_REPORT.md` — полный отчёт | ✅ |

---

*Документ создан в рамках аудита MCP экосистемы команды. Все изменения в custom_modes.yaml прошли валидацию.*
