"""Логирование каждого LLM-запроса и ответа в JSONL.

Зачем: без сырых данных диагностика LLM-пайплайна превращается
в гадание. Каждый вызов сохраняется в runs/<id>/logs/llm.jsonl.

Если ответ не парсится как JSON — та же запись дублируется в
llm_failed.jsonl. Это позволяет потом быстро найти все проблемные
ответы без чтения всего лога.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LLMLogger:
    """Пишет запросы и ответы LLM в JSONL."""

    def __init__(self, base_dir: Path) -> None:
        self._base = Path(base_dir)
        try:
            self._base.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("LLMLogger cannot create %s: %s", self._base, exc)

    @property
    def base_dir(self) -> Path:
        return self._base

    def log_exchange(
        self,
        *,
        model: str,
        attempt: int,
        system_prompt: str,
        user_prompt: str,
        raw_response: str,
        duration_sec: float,
        parse_ok: bool,
        parse_error: str | None = None,
    ) -> None:
        row: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "model": model,
            "attempt": attempt,
            "duration_sec": round(duration_sec, 3),
            "system_prompt_len": len(system_prompt),
            "user_prompt_len": len(user_prompt),
            "raw_response_len": len(raw_response),
            "parse_ok": parse_ok,
            "parse_error": parse_error,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "raw_response": raw_response,
        }
        self._append("llm.jsonl", row)
        if not parse_ok:
            self._append("llm_failed.jsonl", row)

    def _append(self, name: str, row: dict[str, Any]) -> None:
        path = self._base / name
        try:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False))
                fh.write("\n")
        except OSError as exc:
            logger.warning("LLMLogger cannot append to %s: %s", path, exc)
