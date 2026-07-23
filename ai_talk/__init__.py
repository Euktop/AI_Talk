from .core import AITalk
from .models import ModelRole
from .exceptions import AITalkError, AITalkConnectionError, AITalkGenerationError

__version__ = "1.2.0"
__all__ = [
    "AITalk", 
    "ModelRole",
    "AITalkError", 
    "AITalkConnectionError", 
    "AITalkGenerationError"
]