from .client import AITalk
from .exceptions import AITalkError, AITalkConnectionError, AITalkGenerationError
from .prompts import Prompts

__version__ = "1.0.0"
__all__ = ["AITalk", "Prompts", "AITalkError", "AITalkConnectionError", "AITalkGenerationError"]