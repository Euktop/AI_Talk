# План миграции AI_Talk 2.1 -> 2.2 -> 3.0

## Принципы

1. Сначала добавляем новое, потом удаляем старое.
2. Ни один публичный символ не меняет сигнатуру/тип возврата без мажорного бампа.
3. Каждый этап заканчивается зелёными тестами и работающими внешними скриптами.

## Фаза 0. Документы

- [x] `docs/COMPATIBILITY.md`
- [x] `docs/API.md`
- [x] `docs/MIGRATION.md`

Exit: документы приняты и зафиксированы в git.

## Фаза 1. Characterization tests

- [ ] `tests/test_compat_imports.py` — все импорты из `COMPATIBILITY.md` работают.
- [ ] `tests/test_compat_methods.py` — сигнатуры и типы возврата старых методов.
- [ ] `tests/conftest.py` — `FakeLLMClient` (без Ollama).
- [ ] `tests/test_parsers.py` — падающие тесты (TDD) для будущего `parsers.py`.

Exit: `pytest` зелёный (кроме намеренно падающих тестов парсера),
репозиторий без изменений в `ai_talk/`.

## Фаза 2. Новые модули (additive)

- [x] `ai_talk/parsers.py` — `extract_json`, `parse_json_object`, `parse_json_array`.
- [x] `ai_talk/errors.py` — расширенная иерархия (старые классы — там же).
- [x] `ai_talk/config/__init__.py` — `AITalkConfig` с дефолтами = старому поведению.
  (`ai_talk/config.py` создать нельзя — уже есть пакет `ai_talk/config/`.)

Exit: новые модули импортируются, старые не тронуты, тесты зелёные.

## Фаза 3. Подключение парсера

- [x] `OllamaClient.structured_chat` использует `parsers.parse_json_object`.
- [x] `ActantAIClient.structured_chat` использует тот же парсер.
- [x] `AITalkParsingError` наследует `AITalkGenerationError`.

Exit: старые тесты `ask_ai_structured` зелёные, ошибки парсинга ловятся как
`AITalkGenerationError`.

## Фаза 4. Расширение фасада AITalk

- [x] Принять `config: AITalkConfig | None = None` в конструкторе.
- [x] Добавить `ask`, `ask_file`, `ask_json`, `health_check`.
- [~] Старые `ask_ai`/`ask_ai_structured` делегируют в новые.
  (Оставлены как есть для 100% совместимости; унификация — опционально в 2.3.)

Exit: старые вызовы работают, новые тоже.

## Фаза 5. Шаблоны

- [x] `ai_talk/templates.py` — `TemplateSpec`, `TemplateRegistry`, `default_registry()`.
- [~] Встроенные: `spellcheck`, `obsidian_tagger`. `summarize`, `extract_tasks` — отложены до 2.2.
- [x] `AITalk.run_template`, `AITalk.register_template`.

Exit: `ai.run_template("spellcheck", source=...)` возвращает тот же `dict`,
что и старый `ask_ai_structured(..., Prompts.SPELL_CHECKER)`.

## Фаза 6. Внутренний перенос

- [ ] Логика из `application/use_cases.py` -> `core.py`.
- [ ] `application/use_cases.py` становится shim (`from ai_talk.core import ...`).
- [ ] Аналогично `infrastructure/*`.

Exit: все тесты зелёные, внешние импорты работают.

## Фаза 7. Deprecation warnings

- [ ] Пометить `ask_ai`, `ask_ai_structured`, `get_text` как deprecated.
- [ ] Обновить `README.md` с примерами нового API.

Exit: предупреждения появляются, но код работает.

## Фаза 8. Удаление (только 3.0)

- [ ] Удалить deprecated-методы.
- [ ] Бамп версии до `3.0.0`.

## Журнал

- 2026-10-06 — Фаза 0 + фикс `actantai` как optional (коммит `624771a`).
