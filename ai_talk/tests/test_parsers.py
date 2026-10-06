"""TDD-тесты для будущего ai_talk/parsers.py.

Модуль ещё не реализован (Фаза 2, см. docs/MIGRATION.md). Пока все тесты
помечены xfail(strict=True), чтобы они не валили сборку. Когда parsers.py
появится, тесты пройдут и станут XPASS (strict=True пометит это как fail),
что напомнит снять маркер.
"""
import pytest

pytestmark = pytest.mark.xfail(
    reason="ai_talk.parsers будет добавлен в Фазе 2 (см. docs/MIGRATION.md)",
    strict=True,
)


def test_extract_json_plain():
    from ai_talk.parsers import extract_json

    assert extract_json('{"a": 1}') == '{"a": 1}'


def test_extract_json_from_markdown_fence():
    from ai_talk.parsers import extract_json

    text = 'Вот результат:\n```json\n{"a": 1}\n```\nГотово.'
    assert extract_json(text) == '{"a": 1}'


def test_extract_json_uppercase_fence():
    from ai_talk.parsers import extract_json

    text = '```JSON\n{"a": 1}\n```'
    assert extract_json(text) == '{"a": 1}'


def test_parse_json_object_with_surrounding_text():
    from ai_talk.parsers import parse_json_object

    assert parse_json_object('Ответ: {"a": 1} Пояснение.') == {"a": 1}


def test_parse_json_object_invalid_raises_generation_error():
    from ai_talk.domain.exceptions import AITalkGenerationError
    from ai_talk.parsers import parse_json_object

    with pytest.raises(AITalkGenerationError):
        parse_json_object("not a json")


def test_parse_json_array():
    from ai_talk.parsers import parse_json_array

    assert parse_json_array('Результат: [1, 2, 3]') == [1, 2, 3]
