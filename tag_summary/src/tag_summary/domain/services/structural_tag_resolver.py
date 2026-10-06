"""Определение структурных (обязательных) тегов по пути файла.

Соответствует правилам 00_RULES.md и локальным 00_RULES.md в папках.
Структурные теги ВСЕГДА добавляются к результату LLM, даже если LLM
их не предложила.
"""

from __future__ import annotations

from tag_summary.domain.value_objects.tag import Tag


class StructuralTagResolver:
    """Маппинг префикса пути → набор обязательных тегов."""

    RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("10 Панель управления/Отчёты", ("system", "analysis")),
        ("10 Панель управления", ("moc",)),
        ("20 Проекты", ("project",)),
        ("30 Зоны ответственности/Дневник", ("daily",)),
        ("30 Зоны ответственности/Карьера", ("career",)),
        ("30 Зоны ответственности/Учеба", ("study",)),
        ("30 Зоны ответственности/Личное/Люди", ("personal",)),
        ("30 Зоны ответственности/Личное/Финансы", ("personal", "finance")),
        ("30 Зоны ответственности/Личное", ("personal",)),
        ("40 Ресурсы/Валидаторы", ("system", "rules")),
        ("40 Ресурсы/Промпты", ("resource", "ai")),
        ("40 Ресурсы/Сниппеты", ("resource",)),
        ("40 Ресурсы/Шаблоны", ("template",)),
        ("40 Ресурсы/Инструменты", ("resource", "system")),
        ("40 Ресурсы/Архитектура ПО", ("resource", "study")),
        ("40 Ресурсы", ("resource",)),
        ("50 Архив/Ледник", ("archive",)),
        ("50 Архив", ("archive",)),
    )

    SPECIAL_CASES: dict[str, tuple[str, ...]] = {
        "00_RULES": ("system", "rules"),
        "AI_CONTEXT": ("system", "ai"),
        "README": ("system",),
    }

    def resolve(self, rel_path: str) -> tuple[Tag, ...]:
        """Возвращает кортеж структурных тегов для файла.

        rel_path — путь относительно корня vault, с прямыми слэшами,
        например '20 Проекты/AI_Talk.md'.
        """
        filename = rel_path.rsplit("/", 1)[-1].removesuffix(".md")
        if filename in self.SPECIAL_CASES:
            return tuple(Tag(t) for t in self.SPECIAL_CASES[filename])

        for prefix, tags in self.RULES:
            if rel_path.startswith(prefix + "/") or rel_path == prefix:
                return tuple(Tag(t) for t in tags)
        return ()
