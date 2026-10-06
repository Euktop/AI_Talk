"""Юнит-тесты для RunContext."""

from __future__ import annotations

from pathlib import Path

from tag_summary.application.context import RunContext, StageStatus
from tag_summary.infrastructure.cache.jsonl_cache import FileCacheStore


class TestRunContext:
    def test_new_manifest_created(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        ctx = RunContext(cache_store=store, vault_path="/fake")
        assert ctx.run_id
        assert (tmp_path / "manifest.json").exists()
        assert ctx.stage_status("collect") == StageStatus.PENDING

    def test_loaded_existing_manifest(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        ctx1 = RunContext(cache_store=store, vault_path="/fake")
        ctx1.mark_done("collect", files_processed=42)

        store2 = FileCacheStore(tmp_path)
        ctx2 = RunContext(cache_store=store2, vault_path="/fake")
        assert ctx2.run_id == ctx1.run_id
        assert ctx2.stage_status("collect") == StageStatus.DONE

    def test_stage_transitions(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        ctx = RunContext(cache_store=store, vault_path="/fake")
        ctx.mark_started("collect")
        assert ctx.stage_status("collect") == StageStatus.IN_PROGRESS
        ctx.mark_done("collect")
        assert ctx.stage_status("collect") == StageStatus.DONE

    def test_first_pending(self, tmp_path: Path) -> None:
        store = FileCacheStore(tmp_path)
        ctx = RunContext(cache_store=store, vault_path="/fake")
        assert ctx.first_pending() == "collect"
        ctx.mark_done("collect")
        assert ctx.first_pending() == "aggregate"
