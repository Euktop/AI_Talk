"""Адаптер IPromptProvider над Command Engine.

Читает три инструкции из Obsidian по их id. НЕ передаёт данные
в переменных — только чистые шаблоны.
"""

from __future__ import annotations

import logging

from command_engine import CommandEngine

from tag_summary.domain.exceptions import ConfigError

logger = logging.getLogger(__name__)

_ID_COLLECT = "prompt.tag-summary-collect"
_ID_CLUSTER = "prompt.tag-summary-cluster"
_ID_APPLY = "prompt.tag-summary-apply"


class CommandEnginePromptProvider:
    """Реализация IPromptProvider через Command Engine."""

    def __init__(
        self,
        *,
        vault_path: str,
        engine: CommandEngine | None = None,
    ) -> None:
        self._vault_path = vault_path
        if engine is not None:
            self._engine = engine
        else:
            self._engine = CommandEngine(vault_path=vault_path)
            self._engine.reindex(force_full=False)
        logger.info("CommandEnginePromptProvider initialised for vault=%s", vault_path)

    def get_collect_prompt(self) -> str:
        return self._resolve(_ID_COLLECT)

    def get_cluster_prompt(self) -> str:
        return self._resolve(_ID_CLUSTER)

    def get_apply_prompt(self) -> str:
        return self._resolve(_ID_APPLY)

    def _resolve(self, instruction_id: str) -> str:
        try:
            text = self._engine.get_instruction(instruction_id)
        except Exception as exc:  # noqa: BLE001
            raise ConfigError(
                f"Failed to resolve prompt {instruction_id!r} from vault "
                f"{self._vault_path!r}: {exc}"
            ) from exc
        if not text or not text.strip():
            raise ConfigError(
                f"Prompt {instruction_id!r} resolved to empty text."
            )
        if "\u27e6E0" in text:
            raise ConfigError(
                f"Prompt {instruction_id!r} contains Command Engine error marker: "
                f"{text[:200]!r}"
            )
        return text
