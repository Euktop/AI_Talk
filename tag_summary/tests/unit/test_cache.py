"""Юнит-тесты для FileCacheStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from tag_summary.domain.exceptions import CacheError
from tag_summary.infrastructure.cache.jsonl_cache import FileCacheStore


class TestFileCacheStore:
    def test_json_roundtrip(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        store.write_json("data", {"a": 1, "b": [2, 3]})
        assert store.read_json("data") == {"a": 1, "b": [2, 3]}

    def test_jsonl_roundtrip(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        rows = [{"x": 1}, {"x": 2}, {"x": 3}]
        store.write_jsonl("rows", rows)
        assert store.read_jsonl("rows") == rows

    def test_exists(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        assert not store.exists("nope")
        store.write_json("present", {})
        assert store.exists("present")

    def test_read_missing_raises(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        with pytest.raises(CacheError):
            store.read_json("missing")

    def test_empty_jsonl(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        store.write_jsonl("empty", [])
        assert store.read_jsonl("empty") == []

    def test_invalid_jsonl_line_skipped_with_warning(
        self, tmp_path: Path, caplog
    ) -> None:
        """Битая строка пропускается с warning, валидные строки возвращаются.

        Намеренное поведение (см. docstring read_jsonl): толерантность
        к обрезанным строкам после краша критична для resume. Тест
        ожидал CacheError, что противоречило дизайну.
        """
        import logging

        store = FileCacheStore(tmp_path)
        (tmp_path / "broken.jsonl").write_text(
            '{"valid": 1}\nnot json\n{"valid": 2}\n',
            encoding="utf-8",
        )
        with caplog.at_level(logging.WARNING):
            rows = store.read_jsonl("broken")
        assert rows == [{"valid": 1}, {"valid": 2}]
        assert any(
            "Skipping unparsable line" in r.message for r in caplog.records
        )
