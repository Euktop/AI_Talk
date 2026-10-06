class ActantAIException(Exception):
    """Базовое исключение для ActantAI."""
    pass


class ProviderNotAvailableError(ActantAIException):
    """Провайдер ИИ недоступен."""
    pass


class ResponseTimeoutError(ActantAIException):
    """Таймаут при ожидании ответа."""
    pass


class SelectorNotFoundError(ActantAIException):
    """Селектор не найден на странице."""
    pass
