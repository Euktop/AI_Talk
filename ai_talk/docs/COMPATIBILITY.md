# Совместимость AI_Talk

Документ фиксирует публичный контракт пакета `ai_talk`. Всё, что перечислено
в разделе «Нельзя ломать», используется внешними скриптами и не может быть
изменено без мажорной версии (3.0.0) и периода deprecation.

## Публичный API (ai_talk/__init__.py)

- `AITalk` — фасад.
- `ModelRole` — enum ролей моделей.
- `Prompts` — системные промпты (`SPELL_CHECKER`, `OBSIDIAN_TAGGER`).
- `AITalkError` — базовое исключение.
- `AITalkConnectionError` — ошибка подключения.
- `AITalkGenerationError` — ошибка генерации.

## Методы AITalk, которые нельзя менять

| Метод | Сигнатура | Возврат |
|---|---|---|
| `ask_ai` | `(source: str, system_prompt: str = "", temperature: float = 0.7)` | `str` |
| `ask_ai_structured` | `(source: str, system_prompt: str, response_format: str = "json")` | `dict` |
| `get_text` | `(source: str)` | `str` |
| `close` | `()` | `None` |
| `__enter__` / `__exit__` | — | — |

## Конструктор AITalk

```python
AITalk(
    model: Union[str, ModelRole] = ModelRole.BASE,
    host: str = "http://localhost:11434",
    custom_dir: str = "запросы_к_ии",
    browser_instance_id: int = 0,
)
```

Порядок позиционных параметров, значения по умолчанию и имена — фиксированы.

## Атрибуты AITalk

- `llm_client: ILLMClient` — используется в отладочных скриптах
  (`type(ai.llm_client).__name__`).
- `file_reader: IFileReader`.

## Значения ModelRole

- `FAST` = `"fast"`
- `SMART` = `"smart"`
- `BASE` = `"base"`
- `CUSTOM` = `"custom"`
- `WEB_DEEPSEEK` = `"web_deepseek"`
- `WEB_CHATGPT` = `"web_chatgpt"`

`MODEL_REGISTRY` (в `ai_talk.config.models`) — маппинг роль → имя модели Ollama.

## Промпты

`Prompts.SPELL_CHECKER` и `Prompts.OBSIDIAN_TAGGER` — публичные атрибуты.
Тексты можно дополнять, но нельзя удалять или переименовывать.

## Исключения

```
AITalkError
├── AITalkConnectionError
└── AITalkGenerationError
```

`AITalkGenerationError` — базовый для новых типов ошибок парсинга/таймаута,
чтобы старые `except AITalkGenerationError` продолжали работать.

## CUSTOM-режим

В 2.2 и раньше — файловая очередь (`запросы_к_ии/*.md`, папка `архив/`,
маркер `## 🟢 ВАШ ОТВЕТ`). **Удалена в 2.3.0.**

В 2.3.0 — локальный web-UI (`ai_talk.custom_ui`), сервер на
`127.0.0.1:8765`, SQLite в `~/.ai_talk/custom_ui.db`.

Сохраняется:
- `ModelRole.CUSTOM` как значение enum.
- Сигнатуры `AITalk.ask_ai`, `ask_ai_structured`, `get_text`.
- Параметр `custom_dir` в конструкторе (игнорируется, для совместимости).

Не сохраняется (breaking change в 2.3.0):
- Файловый формат очереди, маркер ответа, папка `архив/`.
- Прямое чтение `запросы_к_ии/*.md` сторонними процессами.

Скриптам, полагавшимся на файловую очередь, нужно либо перейти на
`CustomWebClient` (автоматически), либо зафиксировать версию `ai_talk<2.3`.

## Файлы через LocalFileReader

Расширения, трактуемые как путь: `.md`, `.txt`, `.json`, `.csv`. Если файла
с таким расширением нет — `FileNotFoundError`. Иначе строка возвращается как есть.

## Что можно менять без предупреждения

- Внутреннюю реализацию клиентов (`OllamaClient`, `CustomWebClient`,
  `ActantAIClient`) при сохранении сигнатур `chat` / `structured_chat`.
  `CustomFileClient` удалён в 2.3.0 (заменён на `CustomWebClient`).
- Модули `application.use_cases`, `domain.interfaces` — при условии, что
  публичные классы (`AskAIUseCase`, `GetTextUseCase`, `Message`, `ILLMClient`,
  `IFileReader`) остаются импортируемыми.
- Сообщения об ошибках — при сохранении типа исключения.

## Deprecated-план

| Версия | Действие |
|---|---|
| 2.2 | Добавить `AITalkConfig`, `ask_json`, `parsers`, `templates`. Старое не трогать. |
| 2.3 | Пометить `DeprecationWarning` те методы, что будут удалены в 3.0. |
| 3.0 | Удалить deprecated-методы. Мажорный бамп. |
