"""Пример: CUSTOM UI — все запросы сразу списком.

Запуск:
    python examples/04_custom_ui.py

Что произойдёт:
1. Поднимется локальный сервер на 127.0.0.1:8765.
2. Откроется браузер.
3. ВСЕ три запроса появятся в списке сразу (ask_many).
4. Отвечай в любом порядке: скопируй промпт ([📋] или Ctrl+Shift+C),
   вставь в ChatGPT/DeepSeek, скопируй ответ, вставь обратно
   ([📥] или Ctrl+Shift+V). Строка исчезнет.
5. Скрипт получит все ответы и напечатает их в исходном порядке.
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

    print("Отправляю {0} запроса...".format(len(PROMPTS)))
    print("Все они уже в браузере. Отвечай в любом порядке.")
    answers = ai.ask_many(PROMPTS)

    print()
    for i, (prompt, answer) in enumerate(zip(PROMPTS, answers), start=1):
        print("--- {0}. {1}".format(i, prompt))
        print("    {0}".format(answer))

    print()
    print("Все ответы получены.")


if __name__ == "__main__":
    main()
