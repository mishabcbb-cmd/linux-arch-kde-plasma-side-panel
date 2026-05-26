# Навык: mcp-tool-audit

**Версия:** 1.0.0  
**Приоритет:** 🔥 P1 — Критический  
**Автор:** 🧩 Skill Engineer  
**Теги:** `mcp`, `audit`, `mode-writer`, `validation`

---

## Когда использовать

Запускать **после каждого изменения** [`mcp_settings.json`](/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/mcp_settings.json) или [`custom_modes.yaml`](/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml).  
Также запускать при:
- Добавлении нового MCP сервера в конфиг
- Удалении MCP сервера
- Изменении списка `alwaysAllow` у существующего сервера
- Создании нового мода в `custom_modes.yaml`
- Периодической проверке целостности (рекомендуется раз в неделю)

---

## Контракт ввода/вывода

### Входные параметры

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|:------------:|-------------|----------|
| `mcp_config_path` | `string` | нет | `~/.config/VSCodium/.../mcp_settings.json` | Путь к MCP конфигу |
| `modes_config_path` | `string` | нет | `~/.config/VSCodium/.../custom_modes.yaml` | Путь к конфигу модов |
| `fix_mode` | `boolean` | нет | `false` | Автоматически добавлять недостающие инструменты в моды |
| `report_format` | `string` | нет | `markdown` | Формат отчёта: `markdown` или `json` |

### Выходные данные

```json
{
  "version": "1.0.0",
  "timestamp": "2026-05-26T15:00:00Z",
  "mcp_servers": {
    "total": 4,
    "servers": [
      {
        "name": "lean-ctx",
        "tools": ["ctx_overview", "ctx_read", ...],
        "tool_count": 12
      }
    ]
  },
  "modes": {
    "total": 13,
    "gaps": [
      {
        "mode": "coding-teacher",
        "missing_group": "mcp",
        "missing_tools": ["searxng_web_search"],
        "severity": "CRITICAL"
      }
    ],
    "coverage": {
      "full_coverage_modes": 12,
      "partial_coverage_modes": 1,
      "no_mcp_modes": 0
    }
  },
  "fixes_applied": 0,
  "summary": "Найдено 3 пробела: 1 CRITICAL, 2 MEDIUM"
}
```

---

## MCP Usage Pattern

### Последовательность вызовов

```
1. ctx_read(mode:full)  → mcp_settings.json     # Получить все MCP серверы и их инструменты
2. ctx_read(mode:full)  → custom_modes.yaml      # Получить все моды и их customInstructions
3. ctx_search(pattern:"groups:") → custom_modes.yaml  # Найти группы каждого мода
4. Для каждого мода:
   a. Проверить наличие группы "mcp" в groups
   b. Извлечь customInstructions
   c. Сопоставить упомянутые инструменты с доступными из MCP конфига
5. Сгенерировать отчёт о несоответствиях
6. Если fix_mode=true:
   a. ctx_edit → добавить недостающие инструменты в customInstructions
   b. ctx_edit → добавить группу mcp если отсутствует
7. mem_save(type:architecture) — сохранить результаты аудита
```

### Пример вызова

```bash
# Запуск аудита в режиме только отчёт
ctx_read(mode:full, path:"mcp_settings.json")
ctx_read(mode:full, path:"custom_modes.yaml")
# → анализ → отчёт

# Запуск аудита с авто-исправлением
ctx_read(mode:full, path:"mcp_settings.json")
ctx_read(mode:full, path:"custom_modes.yaml")
# → анализ → ctx_edit для каждого пробела
```

---

## Обработка ошибок и fallback

| Ситуация | Действие |
|----------|----------|
| Файл MCP конфига не найден | Использовать путь по умолчанию, сообщить об ошибке |
| Файл custom_modes.yaml не найден | Прервать с ошибкой, запросить путь у пользователя |
| YAML синтаксическая ошибка | Сообщить строку и тип ошибки, предложить `python3 -c "import yaml; yaml.safe_load(...)"` |
| Мод не имеет customInstructions | Пропустить мод, отметить в отчёте как `WARNING: no instructions` |
| Инструмент упомянут но не exists в MCP | Отметить как `WARNING: referenced but not available` |
| Нет доступа к записи | Работать в режиме read-only, отчёт без фиксов |

---

## Пример тестового вызова

```bash
# Шаг 1: Прочитать MCP конфиг
cat ~/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/mcp_settings.json

# Шаг 2: Прочитать custom_modes.yaml
cat ~/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml

# Шаг 3: Извлечь все slug'ы модов
grep "^  - slug:" ~/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml

# Шаг 4: Проверить наличие группы mcp в каждом моде
grep -A5 "^  - slug:" ~/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml | grep -E "(slug|groups)"

# Шаг 5: Проверить упоминание searxng в customInstructions
grep -l "searxng" ~/.config/VSCodium/User/globalStorage/zoocodeorganization.zoo-code/settings/custom_modes.yaml
```

Ожидаемый результат: все 13 модов имеют группу `mcp`, все упоминают `searxng_web_search` в MCP TOOL MAP.

---

## Интеграция с режимами

- **Запуск из:** `✍️ Mode Architect` (mode-writer)
- **Делегация в:** `🧩 Skill Engineer` (skill-writer) при необходимости создать новый навык по результатам
- **Память:** Результаты сохраняются в Engram через `mem_save(type:architecture)`
