"""Конфигурация AI_Talk.

AITalkConfig живёт здесь (а не в ai_talk/config.py), потому что
ai_talk/config/ — уже пакет, и одновременно модуль config.py
существовать не может.

Все дефолты совпадают со старым поведением: AITalk() работает как раньше.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from ai_talk.config.models import ModelRole


@dataclass
class AITalkConfig:
    """Конфигурация AITalk.

    Дефолты = старое поведение v2.1. Изменение любого поля опционально.
    """

    model_role: Union[str, ModelRole] = ModelRole.BASE
    ollama_host: str = "http://localhost:11434"
    custom_dir: Path = field(default_factory=lambda: Path("запросы_к_ии"))
    archive_dir: Optional[Path] = None  # None -> custom_dir / "архив"
    timeout_seconds: float = 3600.0
    poll_interval_seconds: float = 5.0
    temperature: float = 0.7
    verbose: bool = False
    move_completed_files: bool = True
    # CUSTOM UI (см. docs/CUSTOM_UI.md)
    custom_ui_host: str = "127.0.0.1"
    custom_ui_port: int = 8765
    custom_ui_db: Optional[Path] = None  # None -> ~/.ai_talk/custom_ui.db
    custom_ui_open_browser: bool = True


__all__ = ["AITalkConfig"]
