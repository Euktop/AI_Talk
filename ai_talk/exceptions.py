class AITalkError(Exception):
    """Базовая ошибка библиотеки."""
    pass

class AITalkConnectionError(AITalkError):
    """Ошибка подключения к Ollama."""
    pass

class AITalkGenerationError(AITalkError):
    """Ошибка при запросе к ИИ."""
    pass