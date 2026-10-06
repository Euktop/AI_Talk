"""Конфигурация tag_summary.

Источники (по приоритету):
1. Аргументы CLI (--vault, --runs-dir, --backend, --parallel).
2. Переменные окружения (TAG_SUMMARY_*).
3. Файл config.toml.
4. Значения по умолчанию.
"""

from __future__ import annotations

import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from tag_summary.domain.exceptions import ConfigError

logger = logging.getLogger(__name__)

DEFAULT_RUNS_DIR_NAME = "runs"
DEFAULT_THRESHOLD = 3
DEFAULT_CLUSTER_BATCH_SIZE = 300
DEFAULT_MAX_TAGS_PER_FILE = 5
DEFAULT_VALIDATOR_SCRIPT = r"D:\repos\Obsidian Tools\ObsidianValidator\main.py"

DEFAULT_LLM_BACKEND = "local"
DEFAULT_WEB_PROVIDER = "deepseek"
DEFAULT_MAX_PARALLEL = 1
DEFAULT_FILES_PER_BATCH = 4

VALID_BACKENDS = ("local", "web", "custom")
VALID_WEB_PROVIDERS = ("deepseek", "chatgpt")
DEFAULT_CUSTOM_DIR = "custom_queue"


@dataclass(frozen=True, slots=True)
class Settings:
    """Загруженные настройки прогона."""

    vault_path: str
    runs_dir: Path
    threshold: int
    cluster_batch_size: int
    max_tags_per_file: int
    validator_script: str | None
    llm_backend: str
    web_provider: str
    custom_dir: str
    max_parallel: int
    files_per_batch: int

    def __post_init__(self) -> None:
        if not self.vault_path:
            raise ConfigError("vault_path is empty")
        if self.threshold < 0:
            raise ConfigError(f"threshold must be >= 0, got {self.threshold}")
        if self.cluster_batch_size < 10 or self.cluster_batch_size > 800:
            raise ConfigError(
                f"cluster_batch_size must be in [10, 800], got {self.cluster_batch_size}"
            )
        if self.max_tags_per_file < 1 or self.max_tags_per_file > 20:
            raise ConfigError(
                f"max_tags_per_file must be in [1, 20], got {self.max_tags_per_file}"
            )
        if self.llm_backend not in VALID_BACKENDS:
            raise ConfigError(
                f"llm_backend must be one of {VALID_BACKENDS}, got {self.llm_backend!r}"
            )
        if self.web_provider not in VALID_WEB_PROVIDERS:
            raise ConfigError(
                f"web_provider must be one of {VALID_WEB_PROVIDERS}, "
                f"got {self.web_provider!r}"
            )
        if self.max_parallel < 1 or self.max_parallel > 8:
            raise ConfigError(
                f"max_parallel must be in [1, 8], got {self.max_parallel}"
            )
        if self.files_per_batch < 1 or self.files_per_batch > 16:
            raise ConfigError(
                f"files_per_batch must be in [1, 16], got {self.files_per_batch}"
            )
        if self.llm_backend == "local" and self.max_parallel > 1:
            logger.warning(
                "max_parallel=%d при backend=local: Ollama сериализует запросы, "
                "эффект от параллельности близок к нулю.",
                self.max_parallel,
            )
        if self.llm_backend == "custom" and self.max_parallel > 1:
            logger.info(
                "max_parallel=%d при backend=custom: параллельные чанки "
                "открываются одновременно. Убедись, что это удобно.",
                self.max_parallel,
            )


class RunDir:
    """Хелпер для создания уникальной директории запуска."""

    @staticmethod
    def create(runs_dir: Path) -> Path:
        from datetime import datetime

        runs_dir.mkdir(parents=True, exist_ok=True)
        base = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        candidate = runs_dir / base
        if not candidate.exists():
            candidate.mkdir()
            return candidate
        suffix = 1
        while True:
            candidate = runs_dir / f"{base}-{suffix:02d}"
            if not candidate.exists():
                candidate.mkdir()
                return candidate
            suffix += 1


def load_settings(
    *,
    vault_path: str | None = None,
    runs_dir: str | None = None,
    threshold: int | None = None,
    backend: str | None = None,
    parallel: int | None = None,
    files_per_batch: int | None = None,
    config_path: str | None = None,
) -> Settings:
    """Собирает Settings из CLI-аргументов, env и config.toml."""
    file_config = _read_config_file(config_path)

    final_vault = (
        vault_path
        or os.environ.get("TAG_SUMMARY_VAULT")
        or file_config.get("vault_path")
        or ""
    )
    if not final_vault:
        raise ConfigError(
            "Vault path is required. Set via --vault, TAG_SUMMARY_VAULT, "
            "or [vault] path in config.toml."
        )
    final_vault = str(Path(final_vault).resolve())

    runs_dir_value = (
        runs_dir
        or os.environ.get("TAG_SUMMARY_RUNS_DIR")
        or file_config.get("runs_dir")
    )
    if runs_dir_value:
        final_runs = Path(runs_dir_value).resolve()
    else:
        final_runs = _default_runs_dir()

    final_threshold = (
        threshold
        if threshold is not None
        else int(file_config.get("threshold", DEFAULT_THRESHOLD))
    )

    final_backend = (
        backend
        or os.environ.get("TAG_SUMMARY_BACKEND")
        or file_config.get("llm_backend")
        or DEFAULT_LLM_BACKEND
    )
    final_web_provider = (
        os.environ.get("TAG_SUMMARY_WEB_PROVIDER")
        or file_config.get("web_provider")
        or DEFAULT_WEB_PROVIDER
    )
    final_custom_dir = (
        os.environ.get("TAG_SUMMARY_CUSTOM_DIR")
        or file_config.get("custom_dir")
        or DEFAULT_CUSTOM_DIR
    )
    final_parallel = (
        parallel
        if parallel is not None
        else int(file_config.get("max_parallel", DEFAULT_MAX_PARALLEL))
    )

    batch_size = int(file_config.get("cluster_batch_size", DEFAULT_CLUSTER_BATCH_SIZE))
    max_tags = int(file_config.get("max_tags_per_file", DEFAULT_MAX_TAGS_PER_FILE))
    if files_per_batch is None:
        files_per_batch = int(file_config.get("files_per_batch", DEFAULT_FILES_PER_BATCH))
    validator = file_config.get("validator_script", DEFAULT_VALIDATOR_SCRIPT)
    if validator == "":
        validator = None

    settings = Settings(
        vault_path=final_vault,
        runs_dir=final_runs,
        threshold=final_threshold,
        cluster_batch_size=batch_size,
        max_tags_per_file=max_tags,
        validator_script=validator,
        llm_backend=final_backend,
        web_provider=final_web_provider,
        custom_dir=final_custom_dir,
        max_parallel=final_parallel,
        files_per_batch=files_per_batch,
    )
    logger.info(
        "Settings: vault=%s, runs=%s, backend=%s, provider=%s, "
        "parallel=%d, files_per_batch=%d, cluster_batch=%d, threshold=%d",
        settings.vault_path, settings.runs_dir,
        settings.llm_backend, settings.web_provider,
        settings.max_parallel, settings.files_per_batch,
        settings.cluster_batch_size, settings.threshold,
    )
    return settings


def _default_runs_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "pyproject.toml"
        if candidate.exists() and "tag_summary" in str(parent).lower():
            return parent / DEFAULT_RUNS_DIR_NAME
    return Path.cwd() / DEFAULT_RUNS_DIR_NAME


def _read_config_file(config_path: str | None) -> dict:
    path = _find_config_file(config_path)
    if path is None:
        return {}
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"Failed to read config {path}: {exc}") from exc

    if not isinstance(data, dict):
        return {}
    flat: dict = {}
    vault_section = data.get("vault") or {}
    if isinstance(vault_section, dict):
        flat["vault_path"] = vault_section.get("path", "")
    ts_section = data.get("tag_summary") or {}
    if isinstance(ts_section, dict):
        for key in (
            "runs_dir",
            "threshold",
            "cluster_batch_size",
            "max_tags_per_file",
            "validator_script",
            "llm_backend",
            "web_provider",
            "custom_dir",
            "max_parallel",
            "files_per_batch",
        ):
            if key in ts_section:
                flat[key] = ts_section[key]
    return flat


def _find_config_file(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        return path
    candidates = [
        Path.cwd() / "config.toml",
        _default_runs_dir().parent / "config.toml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
