# Навык: cross-service-impact-analysis

**Версия:** 1.0.0  
**Приоритет:** 🔥 P1 — Критический  
**Автор:** 🧩 Skill Engineer  
**Теги:** `impact-analysis`, `trace_path`, `architecture`, `debug`

---

## Когда использовать

Запускать **перед внесением изменений** в код, который может затронуть несколько сервисов или компонентов.  
Конкретные триггеры:
- Изменение API контракта между сервисами
- Рефакторинг общего модуля/утилиты
- Добавление нового HTTP эндпоинта
- Изменение схемы данных, передаваемых между компонентами
- Перед merge request, затрагивающим несколько модулей
- При диагностике каскадных ошибок в production

---

## Контракт ввода/вывода

### Входные параметры

| Параметр | Тип | Обязательный | Описание |
|----------|-----|:------------:|----------|
| `target_function` | `string` | да | Имя функции/метода, с которого начинается анализ |
| `direction` | `string` | нет | `inbound` (кто вызывает), `outbound` (кого вызывает), `both` (по умолч.) |
| `depth` | `integer` | нет | Глубина трассировки (по умолчанию: 3, макс: 10) |
| `include_tests` | `boolean` | нет | Включить тестовые файлы в анализ (по умолч.: false) |
| `project` | `string` | нет | Проект для анализа (по умолч.: текущий) |
| `save_to_memory` | `boolean` | нет | Сохранить результат в Engram (по умолч.: true) |

### Выходные данные

```json
{
  "skill": "cross-service-impact-analysis",
  "version": "1.0.0",
  "target": "ProcessOrder",
  "timestamp": "2026-05-26T15:00:00Z",
  "call_chains": {
    "inbound": [
      {"from": "api/checkout.go:42", "type": "HTTP_CALL", "method": "POST /api/orders"},
      {"from": "worker/payment.go:88", "type": "ASYNC_CALL", "channel": "orders:created"}
    ],
    "outbound": [
      {"to": "internal/inventory.go:15", "type": "CALLS", "file": "internal/store.go:120"},
      {"to": "service/notification.go:7", "type": "ASYNC_CALL", "channel": "notifications:send"}
    ]
  },
  "risk_assessment": {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 3,
    "LOW": 5
  },
  "affected_files": [
    "api/checkout.go",
    "internal/store.go",
    "service/notification.go",
    "worker/payment.go"
  ],
  "recommendations": [
    "Изменение ProcessOrder затронет 4 файла — требуется тестирование всех путей",
    "Добавить обратную совместимость для /api/orders эндпоинта"
  ]
}
```

---

## MCP Usage Pattern

### Последовательность вызовов

```
1. ctx_overview(task:"impact-analysis for {target_function}")
2. search_graph(query:"{target_function}", project:"{project}")
   → Получить qualified_name функции
3. trace_path(
     function_name:"{qualified_name}",
     mode:"cross_service",
     direction:"both",
     depth:{depth},
     risk_labels:true,
     include_tests:{include_tests}
   )
   → Получить полную карту вызовов с HTTP/async связями
4. query_graph(
     project:"{project}",
     query:"MATCH ... RETURN ..."
   )
   → Дополнительные Cypher запросы для уточнения
5. Анализ результатов:
   a. Классифицировать пути по уровню риска
   b. Определить affected_files
   c. Сгенерировать рекомендации
6. Если save_to_memory:
   mem_save(type:architecture, title:"Impact analysis: {target_function}")
7. Вернуть структурированный результат
```

### Пример вызова

```bash
# Анализ влияния функции ProcessOrder
trace_path(
  function_name:"ProcessOrder",
  mode:"cross_service",
  direction:"both",
  depth:3,
  risk_labels:true
)
```

---

## Обработка ошибок и fallback

| Ситуация | Действие |
|----------|----------|
| Функция не найдена в графе | Использовать `search_code` для grep-поиска, затем `get_code_snippet` |
| Граф не проиндексирован | Вызвать `index_repository(mode:fast)` и повторить |
| Нет cross_service связей | Переключиться на `trace_path(mode:calls)` — только прямые вызовы |
| Слишком много результатов (>100) | Уменьшить depth до 2, отфильтровать по direction |
| Проект не указан | Использовать `mem_current_project` для автоопределения |

---

## Пример тестового вызова

```python
# Псевдокод тестового вызова
result = await trace_path(
    function_name="handleMessage",
    mode="cross_service",
    direction="both",
    depth=2,
    risk_labels=True,
    include_tests=False
)

# Ожидаемый результат:
# - Все inbound вызовы (кто вызывает handleMessage)
# - Все outbound вызовы (что вызывает handleMessage)
# - HTTP_CALLS через Route ноды
# - ASYNC_CALLS через каналы
# - Риск-классификация каждого пути
# - Список affected_files
```

---

## Интеграция с режимами

- **Запуск из:** `🏗️ Architect` (architect), `🪲 Debug` (debug)
- **Делегация в:** `🧠 Yeah Boi` (yeah-boi) при необходимости глубокого контекста
- **Память:** Результаты сохраняются в Engram через `mem_save(type:architecture)`
