# Навык: memory-consolidation

**Версия:** 1.0.0  
**Приоритет:** 🔹 P3 — Утилитарный  
**Автор:** 🧩 Skill Engineer  
**Теги:** `memory`, `session`, `consolidation`, `all-modes`

---

## Когда использовать

Запускать **в конце каждой рабочей сессии** перед завершением работы.  
Конкретные триггеры:
- Перед `attempt_completion` — финальная консолидация
- После серии `ctx_session(finding|decision)` — много накопленных решений
- После `mem_save` нескольких наблюдений — нужно собрать воедино
- При переключении между задачами — сохранить контекст текущей
- По расписанию: каждые 2 часа активной работы

---

## Контракт ввода/вывода

### Входные параметры

| Параметр | Тип | Обязательный | Описание |
|----------|-----|:------------:|----------|
| `session_id` | `string` | нет | ID сессии (по умолч.: текущая/последняя) |
| `project` | `string` | нет | Проект (по умолч.: текущий) |
| `include_files` | `boolean` | нет | Включить список изменённых файлов (по умолч.: true) |
| `auto_summarize` | `boolean` | нет | Авто-суммирование через ctx_session (по умолч.: true) |

### Выходные данные

```json
{
  "skill": "memory-consolidation",
  "version": "1.0.0",
  "session_id": "session-abc-123",
  "project": "linux-arch-kde-plasma-side-panel",
  "consolidated": {
    "decisions": 3,
    "findings": 5,
    "tasks_completed": 2,
    "tasks_pending": 1
  },
  "summary": {
    "goal": "Рефакторинг custom_modes.yaml и создание навыков",
    "accomplished": [
      "✅ Аудит MCP конфига — 4 сервера, 46 инструментов",
      "✅ Обновление custom_modes.yaml — 13 модов с MCP TOOL MAP",
      "✅ Создание MCP_AUDIT_REPORT.md"
    ],
    "discoveries": [
      "coding-teacher не имел группы mcp — критический пробел",
      "searxng не использовался ни одним модом"
    ],
    "next_steps": [
      "Создать навык mcp-tool-audit"
    ]
  },
  "files_changed": [
    ".config/VSCodium/.../custom_modes.yaml",
    "MCP_AUDIT_REPORT.md"
  ],
  "memory_saved": true
}
```

---

## MCP Usage Pattern

### Последовательность вызовов

```
ФАЗА 1 — СБОР ВСЕХ ДАННЫХ СЕССИИ:
1. ctx_session(action:"load", session_id:"{session_id}")
   → Загрузить все task/finding/decision
2. ctx_session(action:"status")
   → Получить статус текущей сессии
3. mem_search(project:"{project}", type:"decision|architecture|bugfix|pattern")
   → Найти все наблюдения текущей сессии
4. ctx_knowledge(action:"recall", query:"session:{session_id}")
   → Найти факты из lean-ctx

ФАЗА 2 — АНАЛИЗ И ГРУППИРОВКА:
5. Сгруппировать по типам:
   - decisions → архитектурные решения
   - findings → открытия и инсайты
   - tasks → выполненные и оставшиеся задачи
6. Извлечь changed files из контекста

ФАЗА 3 — СОЗДАНИЕ СВОДКИ:
7. mem_session_summary(
     session_id:"{session_id}",
     content:"{structured_summary}"
   )
   → Сохранить структурированную сводку

ФАЗА 4 — ОЧИСТКА:
8. Если были конфликты → mem_judge для каждого
9. ctx_session(action:"save")
   → Сохранить состояние сессии
```

### Пример вызова

```bash
# Шаг 1: Загрузить сессию
ctx_session(action:"load", session_id:"latest")

# Шаг 2: Найти все решения
mem_search(project:"linux-arch-kde-plasma-side-panel", type:"decision")

# Шаг 3: Создать сводку
mem_session_summary(
  session_id:"latest",
  content:"## Goal\n...\n## Accomplished\n...\n## Discoveries\n..."
)
```

---

## Обработка ошибок и fallback

| Ситуация | Действие |
|----------|----------|
| Сессия не найдена | Создать новую через `ctx_session(action:"save")` |
| Нет данных для консолидации | Сохранить минимальную сводку: "Сессия без значимых изменений" |
| Engram недоступен | Сохранить сводку в локальный файл `session-summary.md` |
| lean-ctx недоступен | Использовать только engram + локальные данные |
| Конфликт при сохранении | Использовать `mem_judge` для разрешения |

---

## Пример тестового вызова

```bash
# Тест: консолидация текущей сессии
ctx_session(action:"status")
# → Ожидается: информация о текущей сессии

mem_search(project:"linux-arch-kde-plasma-side-panel", limit:5)
# → Ожидается: последние наблюдения

# Тест: создание сводки
mem_session_summary(
  session_id:"test-consolidation",
  content:"## Goal\nТест консолидации\n## Accomplished\n- ✅ Тест пройден"
)
# → Ожидается: Session summary saved
```

---

## Интеграция с режимами

- **Запуск из:** Все режимы (универсальный навык)
- **Рекомендуется вызывать:** Перед `attempt_completion` в любом режиме
- **Память:** Сохраняет через `mem_session_summary` + опционально `mem_save`

---

## Быстрая команда для конца сессии

```bash
# Минимальный вызов для консолидации
ctx_session(action:"load", session_id:"latest") && \
mem_search(project:"{project}", type:"decision|bugfix|pattern", limit:10) && \
mem_session_summary(session_id:"latest", content:"{auto-generated}")
```
