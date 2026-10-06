"""Юнит-тесты для Value Object Tag."""

from __future__ import annotations

import pytest

from tag_summary.domain.exceptions import ValidationError
from tag_summary.domain.value_objects.tag import Tag, TagSet


class TestTag:
    def test_valid_flat_tag(self) -> None:
        t = Tag("resource")
        assert t.value == "resource"
        assert t.namespace is None

    def test_valid_namespaced_tag(self) -> None:
        t = Tag("tech/android")
        assert t.namespace == "tech"

    def test_valid_multi_level_namespace(self) -> None:
        t = Tag("tech/mobile/android")
        assert t.namespace == "tech"

    def test_uppercase_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("Android")

    def test_cyrillic_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("андроид")

    def test_space_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("mobile dev")

    def test_leading_dash_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("-android")

    def test_trailing_dash_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("android-")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("")

    def test_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("a" * 65)

    def test_hash_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Tag("#android")


class TestTagSet:
    def test_accepts_up_to_max(self) -> None:
        ts = TagSet(tags=(Tag("a"), Tag("b"), Tag("c")), max_size=5)
        assert len(ts) == 3

    def test_rejects_above_max(self) -> None:
        with pytest.raises(ValidationError):
            TagSet(tags=tuple(Tag(f"t{i}") for i in range(6)), max_size=5)

    def test_rejects_duplicates(self) -> None:
        with pytest.raises(ValidationError):
            TagSet(tags=(Tag("a"), Tag("a")), max_size=5)
