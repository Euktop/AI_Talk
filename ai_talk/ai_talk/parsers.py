"""Устойчивый разбор JSON из ответов LLM.

Модели часто:
- заворачивают JSON в markdown-блоки (```json ... ```, ```JSON ... ```);
- добавляют пояснения до/после JSON;
- меняют регистр языкового тега.

Эти функции извлекают первую JSON-структуру и парсят её. При неудаче
бросают AITalkParsingError (наследник AITalkGenerationError).
"""
import json
import re
from typing import Any, Dict, List

from ai_talk.errors import AITalkParsingError


_FENCE_RE = re.compile(r"```[a-zA-Z]*\s*\n(.*?)```", re.DOTALL)


def extract_json(text: str) -> str:
    """Возвращает первую JSON-структуру (объект или массив) из текста.

    Обрабатывает:
    - голый JSON: '{"a": 1}' -> '{"a": 1}'
    - markdown-блоки: ```json ... ``` и ```JSON ... ```
    - произвольный текст до/после JSON

    Бросает AITalkParsingError, если JSON не найден.
    """
    if not isinstance(text, str):
        raise AITalkParsingError(
            "Ожидалась строка, получено {0}".format(type(text).__name__)
        )

    s = text.strip()
    if not s:
        raise AITalkParsingError("Пустой ответ: JSON не найден")

    # 1. Разворачиваем markdown-fence
    m = _FENCE_RE.search(s)
    if m:
        s = m.group(1).strip()
        if not s:
            raise AITalkParsingError("Пустой markdown-блок: JSON не найден")

    # 2. Если начинается с { или [ — ищем парный закрывающий
    if s.startswith("{") or s.startswith("["):
        close_ch = "}" if s[0] == "{" else "]"
        end = s.rfind(close_ch)
        if end <= 0:
            raise AITalkParsingError(
                "Не найден закрывающий {0!r} в ответе: {1!r}".format(
                    close_ch, s[:200]
                )
            )
        return s[: end + 1]

    # 3. Иначе — ищем первую { или [ и берём до последней парной
    candidates = []
    obj_start = s.find("{")
    if obj_start != -1:
        candidates.append((obj_start, "}"))
    arr_start = s.find("[")
    if arr_start != -1:
        candidates.append((arr_start, "]"))

    if not candidates:
        raise AITalkParsingError(
            "JSON не найден в ответе: {0!r}".format(s[:200])
        )

    start, close_ch = min(candidates, key=lambda x: x[0])
    end = s.rfind(close_ch)
    if end <= start:
        raise AITalkParsingError(
            "Не найден закрывающий {0!r} в ответе: {1!r}".format(
                close_ch, s[:200]
            )
        )
    return s[start : end + 1]


def parse_json_object(text: str) -> Dict[str, Any]:
    """Парсит JSON-объект из текста. Возвращает dict.

    Бросает AITalkParsingError при любой проблеме (JSON не найден,
    невалиден или не является объектом).
    """
    raw = extract_json(text)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AITalkParsingError(
            "Невалидный JSON: {0}. Первые 200 символов: {1!r}".format(
                e, raw[:200]
            )
        ) from e
    if not isinstance(result, dict):
        raise AITalkParsingError(
            "Ожидался JSON-объект, получен {0}".format(type(result).__name__)
        )
    return result


def parse_json_array(text: str) -> List[Any]:
    """Парсит JSON-массив из текста. Возвращает list."""
    raw = extract_json(text)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise AITalkParsingError(
            "Невалидный JSON: {0}. Первые 200 символов: {1!r}".format(
                e, raw[:200]
            )
        ) from e
    if not isinstance(result, list):
        raise AITalkParsingError(
            "Ожидался JSON-массив, получен {0}".format(type(result).__name__)
        )
    return result


__all__ = ["extract_json", "parse_json_object", "parse_json_array"]
