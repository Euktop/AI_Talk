# Changelog

Все заметные изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

## [2.3.0] — 2026-10-06

### Добавлено

- **CUSTOM UI** — локальный web-интерфейс для ручного ответа на запросы.
  Запускается автоматически при первом `ask_ai()` в режиме `ModelRole.CUSTOM`.
  Сервер на `127.0.0.1:8765`, SQLite в `~/.ai_talk/custom_ui.db`.
  - Список активных запросов с превью.
  - Клик по тексту или `[📋]` — копировать полный запрос в буфер.
  - `[?]` — модалка с полным текстом + «Скачать .txt».
  - `[📥]` — вставить ответ из буфера и удалить запрос.
  - Горячие клавиши `Ctrl+Shift+C` / `Ctrl+Shift+V` для копирования
    и вставки текущей строки, `↑`/`↓` для навигации.
  - Lifecycle: сервер поднимается lazily, выходит через 5 секунд
    простоя после завершения скрипта.
- `[project.optional-dependencies].ui = ["flask>=3"]`.
- `AITalkConfig.custom_ui_host`, `.custom_ui_port`, `.custom_ui_db`,
  `.custom_ui_open_browser`.

### Удалено

- `CustomFileClient` (файловая очередь `запросы_к_ии/*.md`,
  папка `архив/`, префикс `done_`, маркер `## 🟢 ВАШ ОТВЕТ`).
  Заменён на `CustomWebClient` + `ai_talk.custom_ui`.

### Изменено

- **Поведенческий breaking change:** `ModelRole.CUSTOM` теперь
  открывает браузер и требует установленного `flask`
  (`pip install ai_talk[ui]`). Старые скрипты, читавшие файлы
  очереди напрямую, должны перейти на новый режим.
- `AITalk.__init__(custom_dir=...)` принимается для совместимости,
  но игнорируется. Используйте `AITalkConfig.custom_ui_db`.
- `AITalk.health_check().installed_models` теперь читает оба поля
  `name` / `model` из ответа Ollama SDK.

### Не изменено

- Сигнатуры `ask_ai`, `ask_ai_structured`, `get_text`, `close`.
- Позиционные параметры `AITalk.__init__`.
- `ModelRole.CUSTOM` как значение — осталось, меняется реализация.
- `ask`, `ask_file`, `ask_json`, `run_template`, `register_template`.
- Ollama-режим и WEB-режим без изменений.

## [2.2.0] — 2026-10-06

### Добавлено

- `AITalkConfig` — конфигурация с дефолтами, совпадающими с 2.1.
- Новые методы `AITalk`: `ask`, `ask_file`, `ask_json`, `run_template`,
  `register_template`, `health_check`.
- Пакет `ai_talk.templates`: `TemplateSpec`, `TemplateRegistry`,
  `default_registry()`.
- Встроенные шаблоны: `spellcheck`, `obsidian_tagger`.
- `ai_talk.parsers`: устойчивый разбор JSON из ответов LLM
  (markdown-блоки, текст до/после, регистр тега).
- `ai_talk.errors`: канонический источник исключений.
- `AITalkParsingError`, `AITalkTimeoutError`, `AITalkFileError`,
  `AITalkConfigError`. Первые два — наследники `AITalkGenerationError`.
- `HealthStatus` — результат `AITalk.health_check()`.

### Изменено

- `actantai` переехал из обязательных зависимостей в `[project.optional-dependencies].web`.
  `import ai_talk` работает без установленного `actantai`.
- `OllamaClient.structured_chat` и `ActantAIClient.structured_chat` используют
  `parsers.parse_json_object` вместо ручного `json.loads` + вырезания fence.

### Исправлено

- `import ai_talk` падал с `ModuleNotFoundError: No module named 'actantweb'`,
  если `actantai` не установлен.
- `__version__` синхронизирован с `pyproject.toml`.

### Не изменено (совместимость 2.1 -> 2.2)

- Позиционные параметры `AITalk.__init__` и их дефолты.
- Сигнатуры `ask_ai`, `ask_ai_structured`, `get_text`, `close`.
- Значения `ModelRole` и содержимое `MODEL_REGISTRY`.
- Иерархия исключений: `AITalkError` -> `AITalkConnectionError` /
  `AITalkGenerationError`.
- CUSTOM-режим: папка `запросы_к_ии`, архив `архив/`, префикс `done_`,
  маркер `## 🟢 ВАШ ОТВЕТ`.

[2.2.0]: https://github.com/Euktop/AI_Talk/releases/tag/v2.2.0
[2.3.0]: https://github.com/Euktop/AI_Talk/releases/tag/v2.3.0
