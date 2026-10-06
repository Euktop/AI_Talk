"""Контекст запуска пайплайна: идентификатор, манифест, этапы.

RunContext инкапсулирует:
- run_id и путь к директории запуска (runs/<timestamp>/);
- манифест (JSON), в котором фиксируется статус каждого этапа;
- методы проверки и обновления статуса этапа для resume.

Манифест — единственный источник правды о состоянии прогона.
Перезапуск после сбоя читает манифест и продолжает с первого
этапа, который не в статусе 'done'.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

from tag_summary.domain.exceptions import ConfigError
from tag_summary.domain.ports.i_cache_store import ICacheStore

logger = logging.getLogger(__name__)


class StageStatus(StrEnum):
    """Статус этапа пайплайна."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


STAGES: tuple[str, ...] = (
    "collect",
    "aggregate",
    "cluster",
    "approve",
    "apply",
    "validate",
)

_MANIFEST_NAME = "manifest"


@dataclass(slots=True)
class StageRecord:
    """Запись о состоянии одного этапа в манифесте."""

    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StageRecord:
        return cls(
            status=StageStatus(data.get("status", "pending")),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            meta=data.get("meta") or {},
        )


class RunContext:
    """Управление состоянием прогона.

    Создаётся из готового cache_store, привязанного к директории запуска.
    Читает или инициализирует manifest.json.
    """

    def __init__(
        self,
        *,
        cache_store: ICacheStore,
        vault_path: str,
        run_id: str | None = None,
    ) -> None:
        self._store = cache_store
        self._vault_path = vault_path
        self._stages: dict[str, StageRecord] = {}

        if cache_store.exists(_MANIFEST_NAME):
            data = cache_store.read_json(_MANIFEST_NAME)
            self._run_id = str(data.get("run_id") or "")
            if not self._run_id:
                raise ConfigError("Manifest exists but has no run_id")
            raw_stages = data.get("stages") or {}
            for name in STAGES:
                self._stages[name] = StageRecord.from_dict(raw_stages.get(name, {}))
            logger.info(
                "Loaded existing manifest run_id=%s from %s",
                self._run_id, cache_store.base_dir if hasattr(cache_store, "base_dir") else "?",
            )
        else:
            self._run_id = run_id or _make_run_id()
            for name in STAGES:
                self._stages[name] = StageRecord()
            self._persist()
            logger.info("Created new run_id=%s", self._run_id)

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def vault_path(self) -> str:
        return self._vault_path

    @property
    def cache_store(self) -> ICacheStore:
        return self._store

    def stage_status(self, name: str) -> StageStatus:
        self._ensure_stage(name)
        return self._stages[name].status

    def is_done(self, name: str) -> bool:
        return self.stage_status(name) == StageStatus.DONE

    def mark_started(self, name: str) -> None:
        self._ensure_stage(name)
        self._stages[name].status = StageStatus.IN_PROGRESS
        self._stages[name].started_at = _now_iso()
        self._stages[name].completed_at = None
        self._stages[name].error = None
        self._persist()

    def mark_done(self, name: str, **meta: Any) -> None:
        self._ensure_stage(name)
        self._stages[name].status = StageStatus.DONE
        self._stages[name].completed_at = _now_iso()
        self._stages[name].error = None
        if meta:
            self._stages[name].meta.update(meta)
        self._persist()

    def mark_failed(self, name: str, error: str) -> None:
        self._ensure_stage(name)
        self._stages[name].status = StageStatus.FAILED
        self._stages[name].error = error
        self._persist()

    def first_pending(self) -> str | None:
        for name in STAGES:
            if self._stages[name].status != StageStatus.DONE:
                return name
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "run_id": self._run_id,
            "vault_path": self._vault_path,
            "stages": {name: rec.to_dict() for name, rec in self._stages.items()},
        }

    def _ensure_stage(self, name: str) -> None:
        if name not in self._stages:
            raise ConfigError(f"Unknown stage: {name!r}. Known: {list(STAGES)}")

    def _persist(self) -> None:
        self._store.write_json(_MANIFEST_NAME, self.snapshot())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _make_run_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
