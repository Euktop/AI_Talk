"""Юнит-тесты для внутренних функций кластеризации."""

from __future__ import annotations

from tag_summary.application.cluster_tags import (
    _build_tag_clusters,
    _chunk,
    _ensure_coverage,
    _merge_into,
    _resolve_conflicts,
)


class TestChunk:
    def test_empty(self) -> None:
        assert _chunk([], 3) == []

    def test_exact(self) -> None:
        assert _chunk([1, 2, 3], 3) == [[1, 2, 3]]

    def test_remainder(self) -> None:
        assert _chunk([1, 2, 3, 4], 3) == [[1, 2, 3], [4]]


class TestMergeInto:
    def test_adds_new_canonical(self) -> None:
        target: dict = {}
        _merge_into(target, {"a": ["b", "c"]})
        assert target == {"a": {"b", "c"}}

    def test_skips_self_alias(self) -> None:
        target: dict = {}
        _merge_into(target, {"a": ["a", "b"]})
        assert target == {"a": {"b"}}

    def test_unions_existing(self) -> None:
        target = {"a": {"b"}}
        _merge_into(target, {"a": ["c"]})
        assert target == {"a": {"b", "c"}}


class TestResolveConflicts:
    def test_no_conflict(self) -> None:
        m = {"a": {"b"}, "c": {"d"}}
        _resolve_conflicts(m)
        assert m == {"a": {"b"}, "c": {"d"}}

    def test_alias_collision_merges(self) -> None:
        m = {"a": {"shared"}, "b": {"shared"}}
        _resolve_conflicts(m)
        assert len(m) == 1
        merged = next(iter(m.values()))
        assert "shared" in merged

    def test_canonical_equals_alias_merges(self) -> None:
        m = {"a": {"b"}, "b": {"c"}}
        _resolve_conflicts(m)
        assert len(m) == 1


class TestEnsureCoverage:
    def test_all_covered(self) -> None:
        m = {"a": {"b"}}
        _ensure_coverage(m, {"a", "b"})
        assert m == {"a": {"b"}}

    def test_missing_added(self) -> None:
        m = {"a": {"b"}}
        _ensure_coverage(m, {"a", "b", "c"})
        assert "c" in m
        assert m["c"] == set()


class TestBuildTagClusters:
    def test_basic(self) -> None:
        m = {"tech/android": {"android", "mobile"}}
        freq = {"tech/android": 5, "android": 3, "mobile": 2}
        clusters = _build_tag_clusters(m, freq)
        assert len(clusters) == 1
        assert clusters[0].canonical.value == "tech/android"
        assert clusters[0].total_frequency == 10

    def test_invalid_canonical_dropped(self) -> None:
        m = {"#invalid": {"x"}}
        freq = {"#invalid": 1}
        assert _build_tag_clusters(m, freq) == []
