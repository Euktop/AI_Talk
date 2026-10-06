# Changelog

Все заметные изменения проекта. Формат: [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/).

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
