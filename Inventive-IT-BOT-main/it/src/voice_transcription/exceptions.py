class STTError(Exception):
    """Исключения для ошибок при трансгрибации аудио"""

    def __init__(self, message: str, show_traceback: bool = True):
        self.show_traceback = show_traceback
        super().__init__(message)


class STTTimeoutError(STTError):
    """Исключение для ошибок превышения времени ожидания"""
