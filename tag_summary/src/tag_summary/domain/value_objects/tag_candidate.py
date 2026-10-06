"""Value objects для промежуточных этапов пайплайна.

- TagCandidate — сырой тег от LLM (до нормализации).
- TagFrequency — нормализованный тег + частота.
"""

from __future__ import annotations

from dataclasses import dataclass

from tag_summary.domain.value_objects.tag import Tag


@dataclass(frozen=True, slots=True)
class TagCandidate:
    """Сырой тег, как его вернула LLM.

    Нормализация — отдельный шаг (TagNormalizer), потому что LLM может
    вернуть что угодно: '#Android', 'Mobile dev', 'android/'.
    """

    raw: str
    source_path: str


@dataclass(frozen=True, slots=True)
class TagFrequency:
    """Тег и его частота во всём vault (после нормализации и мёржа)."""

    tag: Tag
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ValueError(f"Frequency cannot be negative: {self.count}")
