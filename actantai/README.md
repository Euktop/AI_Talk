# ActantAI

Библиотека для работы с веб-версиями ИИ (DeepSeek, ChatGPT, Claude и др.) через браузер.

## 🎯 Возможности

- **Единый интерфейс** для работы с разными ИИ-провайдерами
- **Автоматизация браузера** через библиотеку ActantWeb
- **Чистая архитектура** (Clean Architecture) для легкого расширения
- **Поддержка множественных провайдеров** в одном запросе

## 🏗 Архитектура

```
ActantAI/
├── domain/                 # Ядро (порты, value objects, исключения)
├── application/            # Движок и оркестрация
├── infrastructure/         # Адаптеры и провайдеры
│   ├── actantweb_adapter.py
│   ├── manifests/          # Селекторы для сайтов
│   └── providers/          # Реализации провайдеров
└── examples/               # Примеры использования
```

## 🚀 Установка

1. Установите ActantWeb (если еще не установлена):
```bash
cd D:\repos\ActantWeb
pip install -e .
```

2. Установите ActantAI:
```bash
cd D:\repos\ActantAI
pip install -e .
```

## 📖 Быстрый старт

```python
from actantweb import create_actant
from actantai.application.engine import ActantAIEngine
from actantai.infrastructure.actantweb_adapter import ActantWebAdapter
from actantai.infrastructure.providers.deepseek_provider import DeepSeekProvider

# Создаем браузер
actant_web = create_actant()
browser = ActantWebAdapter(actant_web)

# Создаем движок
engine = ActantAIEngine()
engine.register_provider(DeepSeekProvider(browser))

# Отправляем запрос
response = engine.ask("DeepSeek", "Привет!")
print(response.text)

# Закрываем браузер
browser.stop()
```

## 🛠 Добавление нового провайдера

1. Создайте манифест в `infrastructure/manifests/`:
```python
@dataclass(frozen=True)
class ChatGPTSelectors:
    url: str = "https://chat.openai.com/"
    input_field: str = "//textarea[@id='prompt-textarea']"
    send_button: str = "//button[@data-testid='send-button']"
    response_container: str = "//div[contains(@class, 'markdown')]"
```

2. Создайте провайдер в `infrastructure/providers/`:
```python
class ChatGPTProvider(ILLMProvider):
    def get_name(self) -> str:
        return "ChatGPT"
    
    def send_prompt(self, prompt: Prompt) -> AIResponse:
        # Реализация...
        pass
```

3. Зарегистрируйте провайдер:
```python
engine.register_provider(ChatGPTProvider(browser))
```

## 📋 Зависимости

- **ActantWeb** — библиотека для автоматизации браузера
- **undetected-chromedriver** — обход антибот-защиты
- **selenium** — управление браузером

## 🤝 Расширение

Проект построен на принципах Clean Architecture, что позволяет:
- Легко добавлять новые ИИ-провайдеры
- Заменять браузерный движок (например, на Playwright)
- Тестировать бизнес-логику без браузера

## 📝 Лицензия

MIT
