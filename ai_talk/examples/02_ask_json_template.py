"""Пример: структурированный JSON через встроенный шаблон.

Запуск:
    python examples/02_ask_json_template.py path/to/note.md

Если путь не указан, используется встроенный текст с ошибкой.
"""
import sys
from pathlib import Path

from ai_talk import AITalk, ModelRole

DEFAULT_TEXT = "Это тестовый текс с ашипкой."


def main():
    ai = AITalk(model=ModelRole.SMART)

    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
        result = ai.run_template("spellcheck", source=str(source))
    else:
        result = ai.run_template("spellcheck", prompt=DEFAULT_TEXT)

    print("Исправления:")
    for c in result.get("corrections", []):
        print("  {0!r} -> {1!r}".format(c.get("original"), c.get("fixed")))


if __name__ == "__main__":
    main()
