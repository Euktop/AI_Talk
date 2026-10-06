"""Тесты для ai_talk.parsers (Фаза 2)."""
from ai_talk.domain.exceptions import AITalkGenerationError
from ai_talk.parsers import extract_json, parse_json_array, parse_json_object


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == '{"a": 1}'


def test_extract_json_from_markdown_fence():
    text = 'Вот результат:\n```json\n{"a": 1}\n```\nГотово.'
    assert extract_json(text) == '{"a": 1}'


def test_extract_json_uppercase_fence():
    text = '```JSON\n{"a": 1}\n```'
    assert extract_json(text) == '{"a": 1}'


def test_parse_json_object_with_surrounding_text():
    assert parse_json_object('Ответ: {"a": 1} Пояснение.') == {"a": 1}


def test_parse_json_object_invalid_raises_generation_error():
    try:
        parse_json_object("not a json")
    except AITalkGenerationError:
        return
    raise AssertionError("AITalkGenerationError не был брошен")


def test_parse_json_array():
    assert parse_json_array('Результат: [1, 2, 3]') == [1, 2, 3]
