# Навык: adr-from-session

**Версия:** 1.0.0  
**Приоритет:** 🔸 P2 — Важный  
**Автор:** 🧩 Skill Engineer  
**Теги:** `adr`, `architecture`, `documentation`, `ctx_session`

---

## Когда использовать

Запускать **в конце сессии** или **после принятия архитектурного решения**.  
Конкретные триггеры:
- После `ctx_session(finding:...)` — зафиксировано новое открытие
- После `ctx_session(decision:...)` — принято решение
- После `mem_save(type:architecture)` — сохранено архитектурное наблюдение
- В конце рабочей сессии перед `mem_session_summary`
- При код-ревью, когда нужно зафиксировать архитектурное обоснование

---

## Контракт ввода/вывода

### Входные параметры

| Параметр | Тип | Обязательный | Описание |
|----------|-----|:------------:|----------|
| `session_id` | `string` | нет | ID сессии для анализа (по умолч.: текущая) |
| `project` | `string` | нет | Проект (по умолч.: текущий из ctx_overview) |
| `auto_extract` | `boolean` | нет | Автоматически извлекать решения из контекста (по умолч.: true) |
| `dry_run` | `boolean` | нет | Только показать, что будет создано, без записи (по умолч.: false) |

### Выходные данные

```json
{
  "skill": "adr-from-session",
  "version": "1.0.0",
  "session_id": "session-abc-123",
  "decisions_found": 3,
  "adrs_created": [
    {
      "id": "ADR-001",
      "title": "Выбор MCP-first подхода для всех агентов",
      "status": "accepted",
      "context": "Агенты теряли контекст между сессиями",
      "decision": "Все моды обязаны вызывать ctx_overview при старте",
      "consequences": "Единообразный паттерн, но увеличение времени старта на ~2с",
      "files": ["custom_modes.yaml"],
      "created_from": "ctx_session(decision)"
    }
  ],
  "findings_promoted": [
    {
      "title": "lean-ctx снижает токены на 89-99%",
      "type": "finding",
      "promoted_to": "knowledge"
    }
  ]
}
```

---

## MCP Usage Pattern

### Последовательность вызовов

```
ФАЗА 1 — СБОР КОНТЕКСТА:
1. ctx_session(action:"load", session_id:"{session_id}")
   → Загрузить все task/finding/decision текущей сессии
2. mem_search(type:"architecture|decision", project:"{project}")
   → Найти архитектурные решения, сохранённые в Engram
3. ctx_knowledge(action:"recall", query:"architecture decisions")
   → Найти решения в lean-ctx knowledge

ФАЗА 2 — АНАЛИЗ И ИЗВЛЕЧЕНИЕ:
4. Для каждого решения:
   a. Извлечь: title, context, decision, consequences
   b. Сопоставить с affected files
   c. Определить статус (accepted/proposed/deprecated)
5. Для каждого finding:
   a. Оценить важность
   b. Если значимое → предложить promotion до ADR

ФАЗА 3 — СОЗДАНИЕ ADR:
6. manage_adr(mode:"update", content:"{adr_content}")
   → Создать или обновить ADR
7. mem_save(type:architecture, title:"ADR: {title}")
   → Сохранить в Engram

ФАЗА 4 — ВЕРИФИКАЦИЯ:
8. manage_adr(mode:"get")
   → Проверить, что ADR создан
```

### Пример вызова

```bash
# Шаг 1: Загрузить решения сессии
ctx_session(action:"load", session_id:"latest")

# Шаг 2: Извлечь архитектурные решения
# (парсинг finding и decision из сессии)

# Шаг 3: Создать ADR
manage_adr(
  mode:"update",
  content:"# ADR-001: MCP-first подход\n\n## Context\n...\n## Decision\n...\n## Consequences\n..."
)
```

---

## Обработка ошибок и fallback

| Ситуация | Действие |
|----------|----------|
| Сессия не найдена | Использовать `ctx_session(action:"list")` для поиска |
| Нет решений в сессии | Проверить `mem_search(type:decision)` за последние 24ч |
| `manage_adr` не поддерживается проектом | Сохранить ADR как markdown в `docs/adr/` |
| Дубликат ADR | Использовать `manage_adr(mode:"get")` для проверки существующих |
| Сухой прогон (dry_run=true) | Вывести предполагаемые ADR без записи |

---

## Пример тестового вызова

```bash
# Тест: извлечение решений из последней сессии
ctx_session(action:"load", session_id:"latest")
# → Ожидается: список task/finding/decision

# Тест: создание ADR в dry-run режиме
manage_adr(mode:"get")
# → Ожидается: список существующих ADR (или пусто)
```

Ожидаемый результат: все архитектурные решения сессии зафиксированы как ADR.

---

## Структура ADR

Каждый ADR должен содержать:

```markdown
# ADR-NNN: Название решения

## Статус
[accepted | proposed | deprecated | superseded]

## Контекст
Почему это решение было необходимо?

## Решение
Что именно было решено?

## Последствия
Какие последствия (положительные и отрицательные)?

## Затронутые файлы
- path/to/file.ts — причина

## Связанные ADR
- ADR-XXX: Связанное решение
```

---

## Интеграция с режимами

- **Запуск из:** `🏗️ Architect` (architect), `🧠 Yeah Boi` (yeah-boi)
- **Делегация в:** `💻 Code` (code) для создания ADR файлов вручную
- **Память:** ADR сохраняются через `manage_adr` + `mem_save(type:architecture)`
