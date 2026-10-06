"""Пример: CUSTOM UI — ручной ответ на запросы.

Запуск:
    python examples/04_custom_ui.py

Что произойдёт:
1. Поднимется локальный сервер на 127.0.0.1:8765.
2. Откроется браузер с очередью запросов.
3. Скрипт создаст 3 запроса и будет ждать ответов.
4. В браузере скопируй запрос, ответь в ChatGPT/DeepSeek,
   вставь ответ через [📥] или Ctrl+Shift+V.
5. Скрипт получит ответ, напечатает его и перейдёт к следующему.
6. После всех ответов сервер сам закроется через 5 секунд.

Требует установленного flask:
    pip install -e ".[ui]"
"""
from ai_talk import AITalk, ModelRole


PROMPTS = [
    "Придумай одно слово-приветствие.",
    "Назови один цвет.",
    "Скажи одно число от 1 до 10.",
]


def main():
    ai = AITalk(model=ModelRole.CUSTOM)

    for i, prompt in enumerate(PROMPTS, start=1):
        print("--- Запрос {0}/{1}: {2}".format(i, len(PROMPTS), prompt))
        answer = ai.ask_ai(prompt)
        print("Ответ: {0}".format(answer))

    print("Все ответы получены.")


if __name__ == "__main__":
    main()
