# Публичный API AI_Talk (целевой, v2.2+)

Всё, что уже есть (см. `COMPATIBILITY.md`), продолжает работать без изменений.
Здесь — то, что добавляется.

## Основной вход

```python
from ai_talk import AITalk
ai = AITalk()
```

## Конфигурация

```python
from pathlib import Path
from ai_talk import AITalk, AITalkConfig

config = AITalkConfig(
    model_role="SMART",            # FAST | SMART | BASE | CUSTOM
    ollama_host="http://localhost:11434",
    custom_dir=Path("запросы_к_ии"),
    archive_dir=None,              # None -> custom_dir/"архив"
    timeout_seconds=3600,
    poll_interval_seconds=5,
    temperature=0.7,
    verbose=False,
    move_completed_files=True,
)
ai = AITalk(config=config)
```

Все поля имеют дефолты, совпадающие со старым поведением (`AITalk()` = как раньше).

## Методы

### ask

```python
def ask(
    self,
    prompt: str,
    *,
    source: str | Path | None = None,
    system_prompt: str | None = None,
    temperature: float | None = None,
) -> str
```

Если `source` — путь к файлу, читает его и добавляет к промпту. Возвращает `str`.

### ask_file

```python
def ask_file(self, path: str | Path, *, system_prompt: str | None = None) -> str
```

Синоним `ask("", source=path)`. Возвращает `str`.

### ask_json

```python
def ask_json(
    self,
    prompt: str,
    *,
    source: str | Path | None = None,
    schema: type | None = None,
    template: str | None = None,
) -> dict
```

Возвращает `dict`. Если `schema` передан — валидирует поля, но всё равно
возвращает `dict` (для совместимости с `ask_ai_structured`).

### run_template

```python
def run_template(self, name: str, *, source: str | Path | None = None, **kwargs) -> Any
```

Запускает именованный шаблон. Возвращает `str` или `dict` — по `TemplateSpec`.

### register_template

```python
def register_template(self, spec: TemplateSpec) -> None
```

Регистрирует пользовательский шаблон.

### get_text

```python
def get_text(self, source: str | Path) -> str
```

Читает файл или возвращает строку.

### health_check

```python
def health_check(self) -> HealthStatus
```

Возвращает `HealthStatus(ollama_available, installed_models, actantai_available)`.

## Совместимые методы (остаются)

- `ask_ai(source, system_prompt="", temperature=0.7) -> str`
- `ask_ai_structured(source, system_prompt, response_format="json") -> dict`
- `close()`
- `__enter__` / `__exit__`

## Встроенные шаблоны (v2.2)

| Имя | Возврат | Описание |
|---|---|---|
| `spellcheck` | dict | `{"corrections": [...]}` |
| `obsidian_tagger` | dict | `{"tags": [...], "links": [...]}` |
| `summarize` | str | Краткий пересказ |
| `extract_tasks` | dict | `{"tasks": [...]}` |
| `explain_code` | str | Объяснение кода |
| `json_repair` | dict | Починка JSON |

## Исключения

Расширение, обратно совместимое:

```
AITalkError
├── AITalkConnectionError
├── AITalkGenerationError
│   ├── AITalkParsingError
│   └── AITalkTimeoutError
└── AITalkFileError
```

Новые классы — наследники старых, чтобы `except AITalkGenerationError`
продолжал ловить ошибки парсинга и таймаута.
