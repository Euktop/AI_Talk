"""Базовый пример: задать вопрос локальной модели.

Запуск:
    python examples/01_basic_ask.py

Требует запущенной Ollama и модели qwen2.5:3b.
"""
from ai_talk import AITalk, ModelRole


def main():
    ai = AITalk(model=ModelRole.FAST)
    answer = ai.ask("В одном предложении: что такое RAG?")
    print(answer)

    # health_check не блокирует и не падает, если Ollama недоступна.
    status = ai.health_check()
    print("---")
    print("Ollama доступна:", status.ollama_available)
    print("Модели:", status.installed_models[:5])


if __name__ == "__main__":
    main()
