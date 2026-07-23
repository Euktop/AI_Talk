# 🧠 AI_Talk

**AI_Talk** — это легковесная Python-библиотека для безопасного и структурированного взаимодействия с локальными LLM через Ollama.

## 🚀 Возможности
- **Auto-Connect:** Автоматическая проверка доступности Ollama.
- **Structured Output:** Встроенная поддержка строгого JSON-формата.
- **Error Handling:** Кастомные исключения.

## 📦 Установка
`pip install -e .`

## 💻 Быстрый старт
`from ai_talk import AITalk, Prompts`
`ai = AITalk()`
`result = ai.structured_chat('Текст', Prompts.SPELL_CHECKER)`
`print(result)`