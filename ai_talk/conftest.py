"""Корневой conftest: останавливает сбор тестов чужих проектов.

При запуске pytest из D:\repos\AI_Talk (монорепа) pytest подхватывает
тесты из tag_summary/ и actantai/. Эти тесты ожидают свои namespace-
пакеты и падают. Ставим testpaths в pyproject.toml проекта, но pytest
всё равно обходит родительские каталоги при поиске rootdir.

Этот conftest стоит на корне проекта и явно ограничивает область сбора.
"""


def pytest_ignore_collect(collection_path, config):
    """Игнорируем всё, что лежит вне D:\repos\AI_Talk\ai_talk."""
    try:
        collection_path.relative_to(config.rootpath)
    except ValueError:
        return True
    return False
