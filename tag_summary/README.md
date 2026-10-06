# 🏷 tag_summary

AI-driven пайплайн сбора, кластеризации и применения тегов для Obsidian-vault.

## Что это

Скрипт собирает все теги vault через LLM, кластеризует синонимы, формирует утверждённый словарь и применяет до 5 тегов к каждому файлу. Используется для приведения теговой системы к единому виду без ручной работы.

## Пайплайн

| Этап | Модель | Что делает |
|---|---|---|
| `collect` | fast | 12 тегов-кандидатов на каждый файл |
| `aggregate` | — | подсчёт частоты, отсев тегов с частотой ≤3 |
| `cluster` | smart | сведение синонимов к каноническим тегам, батчи по 300 |
| `approve` | — | подтверждение финального списка (ручное) |
| `apply` | smart | выбор до 5 тегов из утверждённого списка |
| `validate` | — | проверка результата, запуск внешнего валидатора |

## Установка

```
cd D:\repos\AI_Talk\tag_summary
pip install -e .
```

Требует Python 3.10+. Зависимости: `ai_talk`, `jasonutils`, `command_engine`.

## Конфигурация

1. Скопируй `config.toml` в свой проект (или оставь в корне репозитория).
2. Укажи `[vault] path` — путь к Obsidian-vault.
3. Опционально: `.env` по образцу `.env.example`.

## CLI

```
tag_summary run                      # весь пайплайн (с остановкой на approve)
tag_summary collect                  # только сбор кандидатов
tag_summary aggregate                # только подсчёт частот
tag_summary cluster                  # только кластеризация
tag_summary approve --tags-file X.json   # подтвердить финальный список
tag_summary apply                    # применить теги к файлам
tag_summary validate                 # валидация результата
tag_summary status                   # состояние последнего запуска
tag_summary list-runs                # список запусков
tag_summary test                     # pre-flight проверки
```

Если `tag_summary` не в PATH — используй `python -m tag_summary.adapters.cli <команда>`.

## Формат approve-файла

JSON-массив строк с утверждёнными каноническими тегами:

```json
[
  "tech/android",
  "topic/clean-architecture",
  "domain/career"
]
```

Перед approve посмотри `runs/<id>/03_clusters.json` — там кластеры с частотами. Отредактируй список вручную.

## Python API

```python
from tag_summary import TagSummary

with TagSummary(vault_path=r"D:\Work\My_notes") as ts:
    ts.collect()
    ts.aggregate()
    ts.cluster()
    # approve делается вручную
    ts.apply()
    ts.validate()
```

## Артефакты

Все промежуточные данные — в `runs/<timestamp>/`:

- `manifest.json` — статусы этапов
- `01_candidates.jsonl` — теги-кандидаты по файлам
- `02_frequency.json` — частоты
- `03_clusters.json` — кластеры
- `04_final_tags.json` — утверждённый список
- `05_applied.jsonl` — результаты применения
- `06_validation.json` — отчёт валидации

## Архитектура

Строгая Clean Architecture:

- `domain/` — VO, сервисы, порты. Никаких внешних зависимостей.
- `application/` — use cases. Зависят только от портов.
- `infrastructure/` — адаптеры: `AITalkLLMClient`, `JasonFileReader`, `JasonFileWriter`, `CommandEnginePromptProvider`, `FileCacheStore`.
- `adapters/` — CLI и фасад `TagSummary`.
- `config/` — настройки и загрузчик конфига.

## Безопасность

- Все изменения vault — только через `JasonUtils`.
- Перед каждым `set_frontmatter` — dry-run через `try`.
- Ошибка LLM после 3 ретраев — фатальна, скрипт останавливается.
- Кэш и логи — вне vault, в `runs/`.

## Промпты

Промпты живут в Obsidian как инструкции `CommandEngine`:

- `prompt.tag-summary-collect`
- `prompt.tag-summary-cluster`
- `prompt.tag-summary-apply`

Их можно править без пересборки скрипта.

## Тесты

```
pytest tests/unit -v
```

Integration-тесты (требуют реального vault и Ollama) помечены `@pytest.mark.integration`.
