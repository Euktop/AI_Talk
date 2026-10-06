# 🧠 AI_Talk v2.2

**AI_Talk** — это легковесная Python-библиотека для безопасного и структурированного взаимодействия с локальными LLM через [Ollama](https://ollama.com/). 
Библиотека построена на принципах **Clean Architecture**, **SOLID** и **DRY**, что обеспечивает высокую тестируемость, расширяемость и независимость от внешних фреймворков.

## 🏗 Архитектура (Clean Architecture)

Код строго разделен на слои с инверсией зависимостей (DIP):

1. **Domain Layer (Ядро)**: 
   - `interfaces.py`: Абстракции (`ILLMClient`, `IFileReader`).
   - `exceptions.py`: Доменные исключения.
   - *Не зависит ни от каких внешних библиотек.*
2. **Application Layer (Прикладной уровень)**:
   - `use_cases.py`: Бизнес-логика (`AskAIUseCase`, `GetTextUseCase`).
   - `prompts.py`: Хранилище промптов.
3. **Infrastructure Layer (Инфраструктура)**:
   - `ollama_client.py`: Реализация `ILLMClient` для Ollama.
   - `custom_client.py`: Реализация `ILLMClient` для ручного режима через файлы.
   - `file_reader.py`: Реализация `IFileReader` для локальной ФС.
4. **Adapters Layer (Адаптеры)**:
   - `facade.py`: Класс `AITalk`, который связывает всё воедино и предоставляет публичный API.

## 🚀 Возможности

1. **Умный парсинг ввода**: Автоматически отличает путь к `.md` / `.txt` файлу от обычной строки.
2. **Абстракция моделей (`ModelRole`)**: Используйте роли (`FAST`, `SMART`, `BASE`, `CUSTOM`), а не хардкод названий.
3. **CUSTOM-режим**: Ручная имитация ИИ через файлы. Идеально для отладки и сценариев, где ответ пишет человек.
4. **Структурированный вывод**: Поддержка `ask_ai_structured` для получения валидного JSON.
5. **Fail-Safe**: Автоматическая проверка подключения к Ollama при старте.

## 📦 Установка

1. Убедитесь, что у вас установлена и запущена [Ollama](https://ollama.com/) (не нужно для CUSTOM-режима).
2. Установите библиотеку:
```bash
pip install -e .
```

## 🆕 Что нового в 2.2

- **Конфигурация**: `AITalkConfig` с дефолтами, совпадающими с 2.1.
- **Новый API**: `ask`, `ask_file`, `ask_json`, `run_template`, `health_check`.
- **Шаблоны**: `spellcheck`, `obsidian_tagger` + регистрация своих.
- **`actantai` — опциональная зависимость**: `pip install ai_talk` тянет только `ollama`.

### Новый API (рекомендуется)

```python
from ai_talk import AITalk, ModelRole, AITalkConfig

ai = AITalk(config=AITalkConfig(model_role=ModelRole.SMART))

print(ai.ask("Объясни RAG"))
print(ai.ask_file("note.md"))
print(ai.run_template("spellcheck", source="article.md"))
print(ai.health_check())
```

### Свой шаблон

```python
from ai_talk import AITalk, TemplateSpec

ai = AITalk()
ai.register_template(TemplateSpec(
    name="summarize_ru",
    system_prompt="Сделай краткий пересказ на русском. Верни JSON.",
    output_format="json",
    temperature=0.2,
))
result = ai.run_template("summarize_ru", source="note.md")
```

## 💻 Примеры использования (совместимый API)

Всё, что работало в 2.1, работает и в 2.2 без изменений.

### 1. Базовый запрос к ИИ
```python
from ai_talk import AITalk, ModelRole

ai = AITalk(model=ModelRole.FAST)
response = ai.ask_ai("Привет! Как оптимизировать SQL-запрос?")
print(response)
```

### 2. Анализ файла
```python
from ai_talk import AITalk, ModelRole, Prompts

ai = AITalk(model=ModelRole.SMART)
response = ai.ask_ai_structured(
    source="D:\\My_notes\\мысли.md",
    system_prompt=Prompts.OBSIDIAN_TAGGER
)
print(response["tags"])
```

### 3. CUSTOM-режим (Ручная имитация ИИ)
```python
from ai_talk import AITalk, ModelRole

ai = AITalk(ModelRole.CUSTOM, custom_dir="запросы_к_ии")
response = ai.ask_ai(
    source="Исправь ошибки: привт мир",
    system_prompt="Ты редактор."
)
```

## 🛠 Обработка ошибок
```python
from ai_talk import AITalk, AITalkConnectionError, AITalkGenerationError

try:
    ai = AITalk()
except AITalkConnectionError:
    print("Ollama не запущена!")
```
