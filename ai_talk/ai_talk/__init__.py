from ai_talk.adapters.facade import AITalk
from ai_talk.config import AITalkConfig
from ai_talk.config.models import ModelRole
from ai_talk.domain.exceptions import (
    AITalkConfigError,
    AITalkConnectionError,
    AITalkError,
    AITalkFileError,
    AITalkGenerationError,
    AITalkParsingError,
    AITalkTimeoutError,
)
from ai_talk.application.prompts import Prompts
from ai_talk.templates import TemplateRegistry, TemplateSpec, default_registry

__version__ = "2.1.0"
__all__ = [
    "AITalk",
    "AITalkConfig",
    "ModelRole",
    "Prompts",
    "TemplateSpec",
    "TemplateRegistry",
    "default_registry",
    "AITalkError",
    "AITalkConnectionError",
    "AITalkGenerationError",
    "AITalkParsingError",
    "AITalkTimeoutError",
    "AITalkFileError",
    "AITalkConfigError",
]
