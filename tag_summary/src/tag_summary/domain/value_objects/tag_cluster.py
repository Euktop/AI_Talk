"""Value object TagCluster — группа синонимов с каноническим тегом.

Self-canonical кластер (canonical с пустым списком aliases) допустим:
это случай, когда тег не вошёл ни в одну группу и не был покрыт LLM.
Он остаётся как отдельный канонический — пользователь на approve сам
решит, оставить его или удалить.
"""

from __future__ import annotations

from dataclasses import dataclass

from tag_summary.domain.exceptions import ValidationError
from tag_summary.domain.value_objects.tag import Tag


@dataclass(frozen=True, slots=True)
class TagCluster:
    """Кластер синонимов.

    canonical — итоговый тег, который пойдёт в файлы vault.
    aliases — исходные теги, которые сворачиваются в canonical.
              Может быть пустым (self-canonical кластер).
    total_frequency — сумма частот canonical и всех aliases.
    """

    canonical: Tag
    aliases: tuple[str, ...]
    total_frequency: int

    def __post_init__(self) -> None:
        if self.canonical.value in self.aliases:
            raise ValidationError(
                f"Canonical tag cannot be in its own aliases: {self.canonical.value}"
            )
        if self.total_frequency < 0:
            raise ValidationError("total_frequency cannot be negative")
