class AITalkError(Exception):
    """Базовый класс для всех ошибок AI_Talk."""
    pass

class AITalkConnectionError(AITalkError):
    """Ошибка подключения к локальному серверу (Ollama)."""
    pass

class AITalkGenerationError(AITalkError):
    """Ошибка генерации ответа (например, модель не вернула валидный JSON)."""
    pass