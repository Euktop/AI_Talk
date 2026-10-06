"""Юнит-тесты для TagNormalizer."""

from __future__ import annotations

from tag_summary.domain.services.tag_normalizer import TagNormalizer


class TestTagNormalizer:
    def setup_method(self) -> None:
        self.n = TagNormalizer()

    def test_lowercases(self) -> None:
        assert self.n.normalize("ANDROID").value == "android"

    def test_strips_hash(self) -> None:
        assert self.n.normalize("#android").value == "android"

    def test_replaces_spaces_with_dashes(self) -> None:
        assert self.n.normalize("clean architecture").value == "clean-architecture"

    def test_replaces_underscores(self) -> None:
        assert self.n.normalize("clean_architecture").value == "clean-architecture"

    def test_collapses_multiple_dashes(self) -> None:
        assert self.n.normalize("a---b").value == "a-b"

    def test_collapses_multiple_slashes(self) -> None:
        assert self.n.normalize("tech//android").value == "tech/android"

    def test_strips_edges(self) -> None:
        assert self.n.normalize("  -android-  ").value == "android"

    def test_yo_to_ye(self) -> None:
        assert self.n.normalize("ё-тег") is None  # кириллица всё равно отсеется

    def test_empty_returns_none(self) -> None:
        assert self.n.normalize("") is None

    def test_only_hash_returns_none(self) -> None:
        assert self.n.normalize("###") is None

    def test_cyrillic_returns_none(self) -> None:
        assert self.n.normalize("андроид") is None
