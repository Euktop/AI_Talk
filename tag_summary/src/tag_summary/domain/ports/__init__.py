"""Порты Domain-слоя tag_summary."""

from tag_summary.domain.ports.i_cache_store import ICacheStore
from tag_summary.domain.ports.i_file_reader import IFileReader, VaultFile
from tag_summary.domain.ports.i_file_writer import IFileWriter
from tag_summary.domain.ports.i_llm_client import ILLMClient
from tag_summary.domain.ports.i_prompt_provider import IPromptProvider

__all__ = [
    "ICacheStore",
    "IFileReader",
    "IFileWriter",
    "ILLMClient",
    "IPromptProvider",
    "VaultFile",
]
