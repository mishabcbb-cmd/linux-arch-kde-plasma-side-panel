# Навык: plasma-debug-workflow

**Версия:** 1.0.0  
**Приоритет:** 🔸 P2 — Важный  
**Автор:** 🧩 Skill Engineer  
**Теги:** `plasma`, `debug`, `wayland`, `qml`, `nvidia`

---

## Когда использовать

Запускать при диагностике проблем с Plasma виджетами, QML компонентами или Wayland рендерингом.  
Конкретные триггеры:
- Виджет не отображается или отображается некорректно
- Ошибки рендеринга (артефакты, мерцание, чёрный экран)
- Проблемы с GPU ускорением на NVIDIA
- Ошибки в логах Qt Quick / Plasma
- Сигналы не обрабатываются
- Проблемы с темой оформления (светлая/тёмная)
- Некорректное позиционирование элементов

---

## Контракт ввода/вывода

### Входные параметры

| Параметр | Тип | Обязательный | Описание |
|----------|-----|:------------:|----------|
| `widget_path` | `string` | да | Путь к главному QML файлу виджета |
| `error_log` | `string` | нет | Текст ошибки из лога (если есть) |
| `symptom` | `string` | да | Описание симптома: `not_rendering`, `gpu_error`, `positioning`, `theme`, `signal`, `crash` |
| `plasma_version` | `string` | нет | Версия Plasma (по умолч.: 6.x) |
| `gpu_info` | `string` | нет | Информация о GPU (по умолч.: NVIDIA Wayland) |

### Выходные данные

```json
{
  "skill": "plasma-debug-workflow",
  "version": "1.0.0",
  "symptom": "not_rendering",
  "widget": "plasmoid/ai-agent-panel/contents/ui/main.qml",
  "checks_performed": [
    "wayland_environment",
    "qt_logging_rules",
    "gpu_acceleration",
    "qml_imports",
    "signal_connections",
    "theme_compatibility"
  ],
  "issues_found": [
    {
      "severity": "HIGH",
      "description": "Отсутствует QT_QPA_PLATFORM=wayland",
      "fix": "export QT_QPA_PLATFORM=wayland",
      "file": null
    },
    {
      "severity": "MEDIUM",
      "description": "Используется raw Qt Controls вместо PlasmaComponents3",
      "fix": "Заменить import QtQuick.Controls на import org.kde.plasma.components3",
      "file": "plasmoid/ai-agent-panel/contents/ui/main.qml:12"
    }
  ],
  "fixes_applied": 2,
  "verification": "Виджет отображается корректно после применения фиксов"
}
```

---

## MCP Usage Pattern

### Последовательность вызовов

```
ФАЗА 1 — ДИАГНОСТИКА ОКРУЖЕНИЯ:
1. ctx_shell(command:"echo $QT_QPA_PLATFORM")       # Проверить Wayland
2. ctx_shell(command:"echo $QT_QUICK_BACKEND")       # Проверить Qt Quick backend
3. ctx_shell(command:"echo $GBM_BACKEND")            # Проверить GBM
4. ctx_shell(command:"eglinfo 2>&1 | grep -i wayland") # Проверить EGL Wayland
5. ctx_shell(command:"dmesg | grep -i nvidia | tail -5") # Проверить NVIDIA драйвер

ФАЗА 2 — ДИАГНОСТИКА ВИДЖЕТА:
6. ctx_read(mode:full, path:"{widget_path}")         # Прочитать QML код
7. ctx_search(pattern:"import ", path:"{widget_dir}") # Найти все импорты
8. ctx_search(pattern:"PlasmaCore|PlasmaComponents|Kirigami", path:"{widget_dir}")

ФАЗА 3 — ПОИСК РЕШЕНИЯ:
9. searxng_web_search(query:"{error_log} Plasma 6 NVIDIA Wayland")
10. web_url_read(url:"...")                          # Читать документацию

ФАЗА 4 — ПРИМЕНЕНИЕ ФИКСА:
11. ctx_edit → исправить проблему
12. ctx_shell(command:"plasmoidviewer -a {widget_path}") # Проверить

ФАЗА 5 — СОХРАНЕНИЕ:
13. mem_save(type:bugfix, title:"Plasma debug: {symptom}")
```

### Пример вызова

```bash
# Фаза 1: Проверка окружения
echo "QT_QPA_PLATFORM=$QT_QPA_PLATFORM"
echo "QT_QUICK_BACKEND=$QT_QUICK_BACKEND"
echo "GBM_BACKEND=$GBM_BACKEND"
eglinfo 2>&1 | grep -i wayland

# Фаза 2: Чтение виджета
cat plasmoid/ai-agent-panel/contents/ui/main.qml

# Фаза 3: Поиск решения
searxng_web_search(query:"Plasma 6 QML widget not rendering NVIDIA Wayland fix")
```

---

## Обработка ошибок и fallback

| Ситуация | Действие |
|----------|----------|
| `eglinfo` не установлен | Использовать `glxinfo` или `nvidia-smi` |
| Wayland не активен | Проверить X11 fallback, установить `QT_QPA_PLATFORM=wayland` |
| QML импорты не найдены | Установить пакеты через `sudo pacman -S qt6-declarative plasma-framework` |
| Виджет не загружается | Запустить `QT_LOGGING_RULES="*.debug=true" plasmoidviewer -a .` |
| NVIDIA драйвер не загружен | Проверить `nvidia-open` или `nvidia-dkms`, перезагрузить |
| Ошибка синхронизации | Включить explicit sync в KWin |

---

## Пример тестового вызова

```bash
# Тест: диагностика проблем с рендерингом
export QT_QPA_PLATFORM=wayland
export QT_LOGGING_RULES="qt.qml.debug=true"
plasmoidviewer -a /home/neo/ecosystem/linux-arch-kde-plasma-side-panel/plasmoid/ai-agent-panel 2>&1 | head -50
```

Ожидаемый результат: виджет открывается в отдельном окне, в логе нет CRITICAL ошибок.

---

## NVIDIA Wayland Checklist

```bash
# Минимальный набор проверок
[ -n "$QT_QPA_PLATFORM" ] && echo "✅ QT_QPA_PLATFORM" || echo "❌ QT_QPA_PLATFORM"
[ -n "$QT_QUICK_BACKEND" ] && echo "✅ QT_QUICK_BACKEND" || echo "❌ QT_QUICK_BACKEND"
[ -n "$GBM_BACKEND" ] && echo "✅ GBM_BACKEND" || echo "❌ GBM_BACKEND"
eglinfo 2>&1 | grep -q "Wayland" && echo "✅ EGL Wayland" || echo "❌ EGL Wayland"
nvidia-smi &>/dev/null && echo "✅ NVIDIA driver" || echo "❌ NVIDIA driver"
```

---

## Интеграция с режимами

- **Запуск из:** `🎨 KDE Plasma Specialist` (plasma-specialist), `🪲 Debug` (debug)
- **Делегация в:** `💻 Code` (code) для применения фиксов, `🚀 DevOps` (devops) для окружения
- **Память:** Результаты сохраняются в Engram через `mem_save(type:bugfix)`
