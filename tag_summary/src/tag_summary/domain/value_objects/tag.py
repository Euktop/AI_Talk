"""Value object Tag — нормализованный тег vault.

Инварианты:
- только lowercase;
- разрешены a-z, 0-9, дефис, один или несколько слэшей (namespace);
- нет пробелов, '#' и кириллицы;
- длина от 1 до 64 символов (полный путь включая namespace);
- не начинается и не заканчивается на слэш или дефис.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tag_summary.domain.exceptions import ValidationError

_TAG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(/[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")


@dataclass(frozen=True, slots=True)
class Tag:
    """Нормализованный тег.

    Пример: Tag("tech/android"), Tag("resource").
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValidationError("Tag value is empty")
        if len(self.value) > 64:
            raise ValidationError(f"Tag too long: {self.value!r}")
        if not _TAG_RE.match(self.value):
            raise ValidationError(f"Invalid tag format: {self.value!r}")

    @property
    def namespace(self) -> str | None:
        """Префикс до первого слэша или None."""
        if "/" not in self.value:
            return None
        return self.value.split("/", 1)[0]

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TagSet:
    """Набор тегов для одного файла.

    Инварианты:
    - не более max_size элементов;
    - все теги уникальны;
    - структурные теги (без namespace) не выводятся этим VO — они
      добавляются отдельным слоем.
    """

    tags: tuple[Tag, ...]
    max_size: int = 5

    def __post_init__(self) -> None:
        if len(self.tags) > self.max_size:
            raise ValidationError(
                f"TagSet exceeds max_size={self.max_size}: {len(self.tags)}"
            )
        seen = set()
        for t in self.tags:
            if t.value in seen:
                raise ValidationError(f"Duplicate tag: {t.value}")
            seen.add(t.value)

    def __iter__(self):
        return iter(self.tags)

    def __len__(self) -> int:
        return len(self.tags)
