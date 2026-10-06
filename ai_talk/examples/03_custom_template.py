"""Пример: собственный шаблон поверх AITalk.

Запуск:
    python examples/03_custom_template.py

Требует запущенной Ollama.
"""
from ai_talk import AITalk, ModelRole, TemplateSpec


TEMPLATE = TemplateSpec(
    name="summarize_ru",
    system_prompt=(
        "Сделай краткий пересказ текста на русском. "
        "Верни JSON: {\"summary\": \"...\", \"keywords\": [\"...\"]}"
    ),
    output_format="json",
    temperature=0.2,
)

TEXT = (
    "Ollama — это инструмент для запуска больших языковых моделей локально. "
    "Он поддерживает GGUF-модели, умеет работать по HTTP API и совместим "
    "с клиентами, написанными под OpenAI API. Модели можно переключать "
    "на лету, а веса хранятся на диске пользователя."
)


def main():
    ai = AITalk(model=ModelRole.SMART)
    ai.register_template(TEMPLATE)

    result = ai.run_template("summarize_ru", prompt=TEXT)
    print("summary:", result.get("summary"))
    print("keywords:", result.get("keywords"))


if __name__ == "__main__":
    main()
