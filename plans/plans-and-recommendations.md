# Plans & Recommendations

**Version**: 1.0.0
**Date**: 2026-05-26
**Project**: KDE AI Agent Panel

---

## Current Status

Phase 3 (Plasma Integration & Hardening) полностью завершён. Проект в стабильном beta-состоянии:

| Метрика | Значение |
|---------|----------|
| Инструментов | 12 |
| Тестов | 86 passed, 0 failed |
| C++ Native | ✅ GCC 16.1.1, pybind11, LTO, PGO |
| codebase-memory | 1499 nodes, 2569 edges |
| Git коммитов | 10+ за сессию |

---

## Priority 1 — Production Readiness

### 1.1 Установить whisper.cpp и протестировать voice_input

**Почему**: `voice_input` сейчас работает в graceful fallback режиме. Нужен собранный `whisper-cli`.

```bash
# Через наш CMake
cmake -B build -DBUILD_WHISPER=ON
cmake --build build -j$(nproc)

# Или через пакетный менеджер
pip install whisper-cpp
```

**Файлы**: [`cmake/BuildWhisper.cmake.in`](cmake/BuildWhisper.cmake.in)

### 1.2 Добавить uvicorn + starlette в зависимости

**Почему**: MCP SSE транспорт и Web UI требуют этих пакетов, но их нет в `requirements.txt`.

```bash
# Добавить в agent/requirements.txt:
uvicorn>=0.30.0
starlette>=0.40.0
jinja2>=3.1.0
httpx>=0.27.0
```

### 1.3 Настроить GitHub Secrets для CI

**Почему**: `.github/workflows/ci.yml` готов, но не запустится без репозитория на GitHub.

**Действия**:
1. Создать репозиторий на GitHub
2. `git remote add origin <url>`
3. `git push -u origin master`
4. CI запустится автоматически

### 1.4 Интеграционные тесты ChromaDB

**Почему**: 6 тестов требуют `RAG_INTEGRATION_TESTS=1`. Нужно добавить их в CI.

```yaml
# В .github/workflows/ci.yml добавить шаг:
- name: Integration tests
  run: RAG_INTEGRATION_TESTS=1 python -m pytest tests/test_rag.py -v -k "integration"
```

---

## Priority 2 — Feature Enhancements

### 2.1 C++ Native → Python интеграция

**Почему**: `rag_native` модуль собран, но не подключён к Python RAG engine.

**План**:
1. В `agent/rag.py` добавить опциональный импорт `rag_native`
2. Заменить Python-реализации `chunk_text` и `cosine_similarity` на C++ при наличии модуля
3. Добавить бенчмарк: сравнить скорость Python vs C++

```python
# В agent/rag.py
try:
    import rag_native
    HAS_NATIVE = True
except ImportError:
    HAS_NATIVE = False

def chunk_text(text, chunk_size=512, overlap=64):
    if HAS_NATIVE:
        return rag_native.chunk_text(text, chunk_size, overlap)
    # fallback Python implementation
```

### 2.2 TurboQuant+ интеграция

**Почему**: У тебя есть форк TheTom/turboquant_plus (6.9k⭐) с экстремальным сжатием KV cache.

**План**:
1. Собрать с `-DBUILD_LLAMA=ON`
2. Написать Python-обёртку для llama.cpp через pybind11
3. Добавить инструмент `local_inference` для запуска GGUF моделей локально

### 2.3 Multi-agent режим

**Почему**: Несколько AgentLoop воркеров могут работать параллельно над разными задачами.

**План**:
1. Создать `AgentPool` — менеджер воркеров
2. Общая RAG память (ChromaDB уже поддерживает)
3. Очередь задач через Redis или SQLite

### 2.4 VSCode Extension

**Почему**: Агент уже работает как MCP сервер (`--mcp-stdio`). VSCode расширение даст UI.

**План**:
1. Создать VSCode extension на TypeScript
2. Подключиться к MCP серверу агента
3. Отображать чат в WebView панели

---

## Priority 3 — Ecosystem & Community

### 3.1 GitHub Pages документация

**Почему**: README.md хорош, но документация с API reference и примерами нужна для сообщества.

**Инструменты**: MkDocs + Material theme

### 3.2 AUR пакет

**Почему**: Упростит установку для Arch Linux пользователей.

```bash
# PKGBUILD уже есть в packaging/arch/
cd packaging/arch && makepkg -si
```

### 3.3 OpenObserve Dashboard

**Почему**: Агент уже шлёт события в OpenObserve. Нужен готовый дашборд.

**План**:
1. Создать `dashboards/agent-overview.json`
2. Импортировать в OpenObserve
3. Метрики: tool calls/min, tokens/sec, error rate, latency

---

## Technical Debt

### Нужно починить

| Issue | Файл | Описание |
|-------|------|----------|
| `get_config()` warning | [`agent/rag.py`](agent/rag.py) | ChromaDB требует `get_config()` в будущей версии |
| `-Wc11-c23-compat` warning | [`cmake/CompilerFlags.cmake`](cmake/CompilerFlags.cmake) | Флаг только для C/ObjC, не для C++ |
| SSE transport без uvicorn | [`agent/mcp_server.py`](agent/mcp_server.py) | MCPSSETransport не работает без uvicorn |
| install.sh не копирует web/ | [`install.sh`](install.sh) | Web UI не устанавливается автоматически |

### Оптимизации

| Что | Где | Эффект |
|-----|-----|--------|
| Подключить `rag_native` | [`agent/rag.py`](agent/rag.py) | 10-100x ускорение chunking/embeddings |
| PGO сборка | `scripts/pgo-*.sh` | 5-15% ускорение C++ кода |
| Кэшировать repo_map | [`agent/tools.py`](agent/tools.py) | Уменьшить latency при повторных вызовах |
| Async MCP client | [`agent/mcp_client.py`](agent/mcp_client.py) | Не блокировать ReAct loop при MCP вызовах |

---

## Architecture Decisions

### Почему Python, а не C++ для агента?

1. **Быстрая итерация** — Python позволяет менять логику без перекомпиляции
2. **Экосистема LLM** — все LLM SDK (anthropic, openai) — Python-first
3. **pybind11 для горячих путей** — RAG операции вынесены в C++

### Почему ChromaDB, а не FAISS?

1. **Встроенные embedding функции** — не нужно писать обёртки
2. **PersistentClient** — данные сохраняются между запусками
3. **Метаданные** — фильтрация по тегам, источникам

### Почему MCP, а не собственный протокол?

1. **Стандарт** — MCP используется в IDE (VSCode, Cursor, JetBrains)
2. **Готовая экосистема** — lean-ctx, engram, codebase-memory уже работают через MCP
3. **Расширяемость** — любой MCP-совместимый сервер подключается без изменений кода

---

## Roadmap

```
Q2 2026 (current)     Q3 2026              Q4 2026
─────────────────     ──────────            ──────────
Phase 3 ✅            Phase 4               Phase 5
├── M1 Plasma Polish  ├── Multi-agent       ├── Fine-tuning
├── M2 Test Coverage  ├── VSCode Extension  ├── Mobile app
├── M3 Cross-repo     ├── TurboQuant+       ├── Plugin system
├── M4 Extended       ├── Web UI v2         └── Marketplace
└── C++ Native ✅     └── AUR package
```

---

*Generated by KDE AI Agent · 2026-05-26*
